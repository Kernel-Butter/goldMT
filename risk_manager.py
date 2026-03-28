from config import RISK_PER_TRADE, MAX_OPEN_TRADES, DAILY_LOSS_LIMIT, XAUUSD_DOLLAR_PER_LOT


def calc_lot(balance: float, sl_dollars: float) -> float:
    """
    Calculate lot size based on risk %.
    sl_dollars: SL distance in price dollars (e.g. 20 means price moves $20 against you).
    XAUUSD: 1 standard lot = 100 oz, so $1 move = $100 P&L per lot.
    Formula: lot = risk_amount / (sl_dollars * XAUUSD_DOLLAR_PER_LOT)
    Example: $10k balance, 1% risk = $100 budget, $20 SL → lot = 100 / (20*100) = 0.05
    """
    if sl_dollars <= 0:
        return 0.01
    risk_amount = balance * RISK_PER_TRADE
    lot = risk_amount / (sl_dollars * XAUUSD_DOLLAR_PER_LOT)
    lot = round(lot, 2)
    # Clamp between 0.01 and 5.0 lots
    return max(0.01, min(lot, 5.0))


def can_trade(open_positions: list, balance: float, equity: float) -> tuple[bool, str]:
    """
    Check if a new trade is allowed.
    Returns (True, "") or (False, reason).
    """
    if len(open_positions) >= MAX_OPEN_TRADES:
        return False, f"Max open trades reached ({MAX_OPEN_TRADES})"

    drawdown = (balance - equity) / balance if balance > 0 else 0
    if drawdown >= DAILY_LOSS_LIMIT:
        return False, f"Daily loss limit hit ({drawdown:.1%})"

    return True, ""


if __name__ == "__main__":
    # Test
    balance = 10000.0
    equity  = 9800.0
    positions = []

    lot = calc_lot(balance, sl_dollars=20)
    print(f"Lot size for $10k balance, $20 SL: {lot}  (expect ~0.05)")

    allowed, reason = can_trade(positions, balance, equity)
    print(f"Can trade: {allowed} {reason or ''}")

    # Simulate daily loss limit hit
    allowed, reason = can_trade(positions, balance, equity=9650.0)
    print(f"Can trade (equity $9650): {allowed} — {reason}")

    # Simulate max trades
    allowed, reason = can_trade([1, 2], balance, equity)
    print(f"Can trade (2 open): {allowed} — {reason}")
