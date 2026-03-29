import time
from datetime import datetime, timezone

import mt5_bridge as bridge
import groq_analyst as analyst
import risk_manager as risk
from technical import get_indicators
from config import SYMBOL, TIMEFRAMES, CHECK_INTERVAL
from db import init_db, log_decision, log_decision_context, log_trade, log_equity, update_trade_exit


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
        data[tf] = {
            "open":  last["open"],
            "high":  last["high"],
            "low":   last["low"],
            "close": last["close"],
            **indicators
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


def run():
    init_db()
    print(f"[{datetime.now(timezone.utc)}] GoldBot started — {SYMBOL}")

    prev_tickets: set = set()
    open_since: dict  = {}   # ticket → unix timestamp of when we first saw it open

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

            # Clean up closed tickets from open_since
            for ticket in list(open_since):
                if ticket not in current_tickets:
                    del open_since[ticket]

            prev_tickets = current_tickets

            # 3. Risk check
            allowed, reason = risk.can_trade(positions, balance, equity)
            if not allowed:
                print(f"  SKIP — {reason}")
                time.sleep(CHECK_INTERVAL)
                continue

            # 4. Fetch market data + indicators
            market_data = build_market_data()

            # 5. AI analysis
            decision   = analyst.analyze(market_data)
            action     = decision["action"]
            confidence = decision["confidence"]
            sl_dist    = decision["sl_dollars"]   # dollar distance from entry
            tp_dist    = decision["tp_dollars"]   # dollar distance from entry

            decision_id = log_decision(action, confidence, decision["reason"], sl_dist, tp_dist, balance, equity)
            print(f"  AI: {action} | Confidence: {confidence:.0%} | SL: ${sl_dist} | TP: ${tp_dist}")
            print(f"  Reason: {decision['reason']}")

            # 6. Log indicator snapshot + session for this decision
            try:
                tick = bridge.get_tick(SYMBOL)
                spread = round(tick["ask"] - tick["bid"], 2)
            except Exception:
                spread = None

            log_decision_context(
                decision_id=decision_id,
                session=session,
                indicators={
                    "h1_rsi":  market_data.get("H1", {}).get("rsi"),
                    "h4_rsi":  market_data.get("H4", {}).get("rsi"),
                    "d1_rsi":  market_data.get("D1", {}).get("rsi"),
                    "h1_ema20": market_data.get("H1", {}).get("ema20"),
                    "h4_ema20": market_data.get("H4", {}).get("ema20"),
                    "h1_atr":  market_data.get("H1", {}).get("atr"),
                },
                spread=spread,
            )

            # 7. Execute if not HOLD and confidence is high enough
            if action in ("BUY", "SELL") and confidence >= 0.65:
                # ── Session filter: only trade London + Overlap ──────────────
                if session not in ("london", "overlap"):
                    print(f"  SKIP — session '{session}' not tradeable (london/overlap only)")
                else:
                    # ── ATR-locked SL/TP (enforces minimum 2:1 RR) ──────────
                    h1_atr = market_data.get("H1", {}).get("atr", 0)
                    if h1_atr > 2:  # sanity check — XAUUSD ATR should always be > $2
                        sl_dist = round(h1_atr * 1.0, 2)
                        tp_dist = round(h1_atr * 2.0, 2)
                        print(f"  ATR-locked: SL=${sl_dist} TP=${tp_dist} (H1 ATR=${h1_atr:.2f})")

                    if spread is None:
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
                        log_trade(action, lot, price, sl, tp, result["ticket"], decision_id)
                        open_since[result["ticket"]] = time.time()
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
