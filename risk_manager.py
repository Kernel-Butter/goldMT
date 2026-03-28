from config import RISK_PER_TRADE, MAX_OPEN_TRADES, DAILY_LOSS_LIMIT


def calc_lot(balance: float, sl_pips: float, pip_value: float = 1.0) -> float:
    """
    Calculate lot size based on risk %.
    For XAUUSD: 1 pip = $0.01 per 0.01 lot (micro) — pip_value per lot ~ $1 for standard.
    Default pip_value=1.0 (adjust per broker).
    """
    if sl_pips <= 0:
        return 0.01
    risk_amount = balance * RISK_PER_TRADE
    lot = risk_amount / (sl_pips * pip_value)
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

    lot = calc_lot(balance, sl_pips=25)
    print(f"Lot size for $10k balance, 25 pip SL: {lot}")

    allowed, reason = can_trade(positions, balance, equity)
    print(f"Can trade: {allowed} {reason or ''}")

    # Simulate daily loss limit hit
    allowed, reason = can_trade(positions, balance, equity=9650.0)
    print(f"Can trade (equity $9650): {allowed} — {reason}")

    # Simulate max trades
    allowed, reason = can_trade([1, 2], balance, equity)
    print(f"Can trade (2 open): {allowed} — {reason}")
