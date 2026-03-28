import time
from datetime import datetime, timezone

import mt5_bridge as bridge
import groq_analyst as analyst
import risk_manager as risk
from technical import get_indicators
from config import SYMBOL, TIMEFRAMES, CHECK_INTERVAL
from db import init_db, log_decision, log_trade, log_equity


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


def run():
    init_db()
    print(f"[{datetime.now(timezone.utc)}] GoldBot started — {SYMBOL}")

    while True:
        try:
            # 1. Get account state
            account   = bridge.get_account()
            positions = bridge.get_positions()
            balance   = account["balance"]
            equity    = account["equity"]

            log_equity(balance, equity)
            print(f"\n[{datetime.now(timezone.utc)}] Balance: ${balance:.2f} | Equity: ${equity:.2f} | Open: {len(positions)}")

            # 2. Risk check
            allowed, reason = risk.can_trade(positions, balance, equity)
            if not allowed:
                print(f"  SKIP — {reason}")
                time.sleep(CHECK_INTERVAL)
                continue

            # 3. Fetch market data + indicators
            market_data = build_market_data()

            # 4. AI analysis
            decision   = analyst.analyze(market_data)
            action     = decision["action"]
            confidence = decision["confidence"]
            sl_dist    = decision["sl_dollars"]   # dollar distance from entry
            tp_dist    = decision["tp_dollars"]   # dollar distance from entry
            log_decision(action, confidence, decision["reason"], sl_dist, tp_dist, balance, equity)
            print(f"  AI: {action} | Confidence: {confidence:.0%} | SL: ${sl_dist} | TP: ${tp_dist}")
            print(f"  Reason: {decision['reason']}")

            # 5. Execute if not HOLD and confidence is high enough
            if action in ("BUY", "SELL") and confidence >= 0.65:
                tick  = bridge.get_tick(SYMBOL)
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
                    log_trade(action, lot, price, sl, tp, result["ticket"])
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
