import time
from datetime import datetime, timezone

import mt5_bridge as bridge
import groq_analyst as analyst
import risk_manager as risk
from technical import get_indicators
from config import SYMBOL, TIMEFRAMES, CHECK_INTERVAL, BE_TRIGGER_R, TRAIL_ATR_MULT, ATR_SANITY_MIN, MIN_SL_DIST
from db import init_db, log_decision, log_decision_context, log_trade, log_trade_event, log_equity, update_trade_exit


def get_session() -> str:
    """Return the current trading session based on UTC hour."""
    hour = datetime.utcnow().hour
    if 13 <= hour < 16:
        return "overlap"      # London + New York — highest volume
    elif 8 <= hour < 13:
        return "london"
    elif 16 <= hour < 21:
        return "new_york"
    elif 0 <= hour < 8:
        return "asian"
    else:
        return "dead"         # 21:00–00:00 UTC — low liquidity


def build_market_data() -> dict:
    """Fetch candles for all timeframes and compute indicators."""
    data = {"symbol": SYMBOL, "timestamp": datetime.utcnow().isoformat()}
    for tf in TIMEFRAMES:
        candles = bridge.get_candles(SYMBOL, tf, count=60)
        indicators = get_indicators(candles)
        last = candles[-1]
        recent_5 = [
            {"o": round(c["open"], 2), "h": round(c["high"], 2),
             "l": round(c["low"], 2),  "c": round(c["close"], 2)}
            for c in candles[-5:]
        ]
        data[tf] = {
            "open":    last["open"],
            "high":    last["high"],
            "low":     last["low"],
            "close":   last["close"],
            **indicators,
            "candles": recent_5,
        }
    return data


def check_closed_positions(prev_tickets: set, current_tickets: set, open_since: dict):
    """Detect positions that closed since last cycle and record exit data."""
    closed = prev_tickets - current_tickets
    if not closed:
        return

    # Fetch closing deals from the last 24 hours
    from_ts = int(time.time()) - 86400
    try:
        deals = bridge.get_closed_deals(from_ts)
    except Exception as e:
        print(f"  [WARNING] Could not fetch closed deals: {e}")
        return

    deals_by_ticket = {d["ticket"]: d for d in deals}

    for ticket in closed:
        deal = deals_by_ticket.get(ticket)
        if not deal:
            continue

        open_time = open_since.get(ticket)
        duration = None
        if open_time:
            duration = (time.time() - open_time) / 60  # minutes

        exit_time = datetime.fromtimestamp(deal["time"], tz=timezone.utc).isoformat()
        pnl = deal["profit"]

        # Determine how the trade closed (SL, TP, or manual)
        if pnl < 0:
            close_reason = "sl_hit"
        elif pnl > 0:
            close_reason = "tp_hit"
        else:
            close_reason = "manual"

        update_trade_exit(
            ticket=ticket,
            exit_price=deal["price"],
            exit_time=exit_time,
            pnl_dollars=pnl,
            close_reason=close_reason,
            duration_minutes=round(duration, 1) if duration else None,
        )
        print(f"  CLOSED ticket #{ticket} | P&L: ${pnl:+.2f} | Reason: {close_reason}")


def manage_open_positions(positions: list, tick: dict, atr: float, trade_state: dict):
    """
    Apply break-even stop and ATR trailing stop to every open position.

    Phase 1 — Break-even: when unrealised profit >= 1× original SL distance,
    move SL to entry price.  Worst case becomes zero loss.

    Phase 2 — ATR trail: once break-even is set, trail SL at 1× ATR behind
    the current price so profits are locked as price extends.
    """
    if atr <= ATR_SANITY_MIN:
        return

    for pos in positions:
        ticket     = pos["ticket"]
        open_price = pos["open_price"]
        current_sl = pos["sl"]
        direction  = pos["type"]   # "BUY" or "SELL"

        # Use ask for BUY (cost to exit), bid for SELL
        price = tick["ask"] if direction == "BUY" else tick["bid"]

        # First time we see this ticket — snapshot the original SL distance
        if ticket not in trade_state:
            sl_dist = abs(open_price - current_sl)
            if sl_dist < MIN_SL_DIST:
                continue   # no meaningful SL set, skip
            trade_state[ticket] = {"original_sl_dist": sl_dist, "be_triggered": False}

        state            = trade_state[ticket]
        orig_sl_dist     = state["original_sl_dist"]
        new_sl           = current_sl
        event_type       = None   # tracks which phase moved the SL

        # Dollar profit from entry in the direction of the trade
        profit_dist = (price - open_price) if direction == "BUY" else (open_price - price)

        # --- Phase 1: Break-even ---
        if not state["be_triggered"] and profit_dist >= orig_sl_dist * BE_TRIGGER_R:
            new_sl = open_price
            state["be_triggered"] = True
            event_type = "be_triggered"
            print(f"  BE: #{ticket} SL → entry {open_price:.2f} (profit locked: $0 floor)")

        # --- Phase 2: ATR trailing stop (activates once break-even fires) ---
        if state["be_triggered"]:
            trail_dist = round(atr * TRAIL_ATR_MULT, 2)
            if direction == "BUY":
                trail_sl = round(price - trail_dist, 2)
                if trail_sl > new_sl:
                    new_sl = trail_sl
                    if event_type is None:
                        event_type = "trail_moved"
            else:
                trail_sl = round(price + trail_dist, 2)
                if trail_sl < new_sl:
                    new_sl = trail_sl
                    if event_type is None:
                        event_type = "trail_moved"

        # Only send modify if SL has actually improved (never move SL against the trade)
        improved = (new_sl > current_sl) if direction == "BUY" else (new_sl < current_sl)
        if improved:
            try:
                result = bridge.modify_position(ticket, new_sl)
                if "error" not in result:
                    log_trade_event(ticket, event_type, current_sl, new_sl, price)
                    print(f"  TRAIL: #{ticket} SL {current_sl:.2f} → {new_sl:.2f} [{event_type}]")
                else:
                    print(f"  TRAIL ERROR: #{ticket} {result['error']}")
            except Exception as e:
                print(f"  TRAIL ERROR: #{ticket} {e}")


def run():
    init_db()
    print(f"[{datetime.now(timezone.utc)}] GoldBot started — {SYMBOL}")

    prev_tickets: set    = set()
    open_since: dict     = {}     # ticket → unix timestamp of when we first saw it open
    trade_state: dict    = {}     # ticket → {original_sl_dist, be_triggered}
    last_ai_price: float = 0.0   # price at last AI call — for change-gate
    last_trade_time: float = 0.0  # unix time of last placed order — for cooldown

    while True:
        try:
            # 1. Get account state
            account   = bridge.get_account()
            positions = bridge.get_positions()
            balance   = account["balance"]
            equity    = account["equity"]

            log_equity(balance, equity)

            session = get_session()
            print(f"\n[{datetime.now(timezone.utc)}] Balance: ${balance:.2f} | Equity: ${equity:.2f} | Open: {len(positions)} | Session: {session}")

            # 2. Detect and record any positions that closed since last cycle
            current_tickets = {p["ticket"] for p in positions}
            check_closed_positions(prev_tickets, current_tickets, open_since)

            # Track open time for new positions
            for p in positions:
                if p["ticket"] not in open_since:
                    open_since[p["ticket"]] = time.time()

            # Clean up closed tickets from open_since and trade_state
            for ticket in list(open_since):
                if ticket not in current_tickets:
                    del open_since[ticket]
                    trade_state.pop(ticket, None)

            prev_tickets = current_tickets

            # 3. Fetch market data + tick (always — needed for position management)
            market_data = build_market_data()
            h1      = market_data.get("H1", {})
            h1_atr  = h1.get("atr", 0)
            h1_adx  = h1.get("adx", 0)

            try:
                tick = bridge.get_tick(SYMBOL)
                spread = round(tick["ask"] - tick["bid"], 2)
            except Exception:
                tick = None
                spread = None

            # 4. Manage open positions (break-even + ATR trail) — runs every cycle
            if positions and tick:
                manage_open_positions(positions, tick, h1_atr, trade_state)

            # 5. Risk check for new trades
            allowed, risk_reason = risk.can_trade(positions, balance, equity)
            if not allowed:
                print(f"  SKIP — {risk_reason}")
                time.sleep(CHECK_INTERVAL)
                continue

            # ── Pre-filters: local checks before spending an API call ─────

            # Filter 1 — Session gate (eliminates ~67% of cycles)
            if session not in ("london", "overlap"):
                print(f"  SKIP — session '{session}' (london/overlap only)")
                time.sleep(CHECK_INTERVAL)
                continue

            # Filter 2 — ADX gate: don't trade ranging markets
            if h1_adx < 20:
                print(f"  SKIP — H1 ADX {h1_adx:.1f} < 20 (ranging, no trend)")
                time.sleep(CHECK_INTERVAL)
                continue

            # Filter 3 — EMA alignment gate: both H1 and H4 must agree
            h1_ema20 = h1.get("ema20", 0)
            h1_ema50 = h1.get("ema50", 0)
            h4       = market_data.get("H4", {})
            h4_ema20 = h4.get("ema20", 0)
            h4_ema50 = h4.get("ema50", 0)
            h1_bull  = h1_ema20 > h1_ema50
            h4_bull  = h4_ema20 > h4_ema50
            if h1_bull and h4_bull:
                ema_aligned = 1
            elif not h1_bull and not h4_bull:
                ema_aligned = -1
            else:
                ema_aligned = 0

            if ema_aligned == 0:
                print(f"  SKIP — EMA misaligned (H1/H4 mixed, no consensus direction)")
                time.sleep(CHECK_INTERVAL)
                continue

            # Filter 4 — Price change gate: skip if price barely moved since last AI call
            current_price = tick["bid"] if tick else 0.0
            if h1_atr > 0 and last_ai_price > 0 and current_price > 0:
                moved = abs(current_price - last_ai_price)
                threshold = h1_atr * 0.3
                if moved < threshold:
                    print(f"  SKIP — price unchanged (moved ${moved:.2f}, need ${threshold:.2f})")
                    time.sleep(CHECK_INTERVAL)
                    continue

            # Filter 5 — Post-trade cooldown: 5 min after any order
            cooldown_remaining = 300 - (time.time() - last_trade_time)
            if cooldown_remaining > 0:
                print(f"  SKIP — post-trade cooldown ({int(cooldown_remaining)}s remaining)")
                time.sleep(CHECK_INTERVAL)
                continue

            # ── All filters passed — call AI ──────────────────────────────

            # 6. AI analysis
            last_ai_price = current_price
            decision   = analyst.analyze(market_data)
            action     = decision["action"]
            confidence = decision["confidence"]
            sl_dist    = decision["sl_dollars"]   # dollar distance from entry
            tp_dist    = decision["tp_dollars"]   # dollar distance from entry

            decision_id = log_decision(action, confidence, decision["reason"], sl_dist, tp_dist, balance, equity)
            print(f"  AI: {action} | Confidence: {confidence:.0%} | SL: ${sl_dist} | TP: ${tp_dist}")
            print(f"  Reason: {decision['reason']}")

            # 7. Log indicator snapshot + session for this decision
            h4_atr = h4.get("atr", 0)
            log_decision_context(
                decision_id=decision_id,
                session=session,
                indicators={
                    "h1_rsi":      h1.get("rsi"),
                    "h4_rsi":      h4.get("rsi"),
                    "d1_rsi":      market_data.get("D1", {}).get("rsi"),
                    "h1_ema20":    h1_ema20,
                    "h4_ema20":    h4_ema20,
                    "h1_atr":      h1_atr,
                    "h4_atr":      h4_atr,
                    "ema_aligned": ema_aligned,
                },
                spread=spread,
            )

            # 8. Execute if not HOLD and confidence is high enough
            if action in ("BUY", "SELL") and confidence >= 0.65:
                # ── ATR-locked SL/TP (enforces minimum 2:1 RR) ──────────
                if h1_atr > ATR_SANITY_MIN:
                    sl_dist = round(h1_atr * 1.0, 2)
                    tp_dist = round(h1_atr * 2.0, 2)
                    print(f"  ATR-locked: SL=${sl_dist} TP=${tp_dist} (H1 ATR={h1_atr:.2f})")

                if tick is None:
                    tick = bridge.get_tick(SYMBOL)
                    spread = round(tick["ask"] - tick["bid"], 2)
                price = tick["ask"] if action == "BUY" else tick["bid"]

                if action == "BUY":
                    sl = round(price - sl_dist, 2)
                    tp = round(price + tp_dist, 2)
                else:
                    sl = round(price + sl_dist, 2)
                    tp = round(price - tp_dist, 2)

                lot    = risk.calc_lot(balance, sl_dist)
                result = bridge.place_order(SYMBOL, action, lot, sl, tp)
                if "ticket" in result:
                    log_trade(action, lot, price, sl, tp, result["ticket"], decision_id,
                              sl_dollars=sl_dist, tp_dollars=tp_dist)
                    open_since[result["ticket"]] = time.time()
                    last_trade_time = time.time()
                print(f"  ORDER: {action} {lot} lots @ {price} | SL {sl} | TP {tp}")
                print(f"  Result: {result}")
            else:
                print(f"  No trade — action={action}, confidence={confidence:.0%}")

        except KeyboardInterrupt:
            print("\nBot stopped.")
            break
        except Exception as e:
            print(f"  ERROR: {e}")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    run()
