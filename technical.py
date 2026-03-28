def ema(prices: list, period: int) -> float:
    """Exponential Moving Average — returns latest value."""
    if len(prices) < period:
        return sum(prices) / len(prices)
    k = 2 / (period + 1)
    val = sum(prices[:period]) / period
    for price in prices[period:]:
        val = price * k + val * (1 - k)
    return round(val, 5)


def rsi(prices: list, period: int = 14) -> float:
    """Relative Strength Index — returns value 0-100."""
    if len(prices) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, period + 1):
        delta = prices[-period - 1 + i] - prices[-period - 2 + i]
        (gains if delta > 0 else losses).append(abs(delta))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def atr(highs: list, lows: list, closes: list, period: int = 14) -> float:
    """Average True Range — returns latest value."""
    if len(highs) < period + 1:
        return 0.0
    true_ranges = []
    for i in range(1, len(highs)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1])
        )
        true_ranges.append(tr)
    return round(sum(true_ranges[-period:]) / period, 5)


def get_indicators(candles: list) -> dict:
    """
    Takes a list of OHLCV dicts and returns indicators.
    Each candle: {"open": x, "high": x, "low": x, "close": x, "volume": x}
    """
    closes = [c["close"] for c in candles]
    highs  = [c["high"]  for c in candles]
    lows   = [c["low"]   for c in candles]
    return {
        "rsi":   rsi(closes),
        "ema20": ema(closes, 20),
        "ema50": ema(closes, 50),
        "atr":   atr(highs, lows, closes)
    }


if __name__ == "__main__":
    # Test with dummy candles
    import random
    random.seed(42)
    base = 3000.0
    candles = []
    for _ in range(60):
        o = base + random.uniform(-10, 10)
        h = o + random.uniform(0, 15)
        l = o - random.uniform(0, 15)
        c = o + random.uniform(-8, 8)
        candles.append({"open": o, "high": h, "low": l, "close": c, "volume": 100})
        base = c

    indicators = get_indicators(candles)
    print("Indicators:", indicators)
