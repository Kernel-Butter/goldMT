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


def adx(highs: list, lows: list, closes: list, period: int = 14) -> float:
    """Average Directional Index — returns 0-100 trend strength.
    < 20 = ranging/choppy, 20-25 = developing, > 25 = trending."""
    if len(highs) < period * 2:
        return 0.0

    plus_dm_list, minus_dm_list, tr_list = [], [], []
    for i in range(1, len(highs)):
        up   = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        plus_dm_list.append(up   if (up > down and up > 0)   else 0)
        minus_dm_list.append(down if (down > up and down > 0) else 0)
        tr_list.append(max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i]  - closes[i - 1])
        ))

    def wilder(data):
        val = sum(data[:period])
        result = [val]
        for x in data[period:]:
            val = val - val / period + x
            result.append(val)
        return result

    sm_plus  = wilder(plus_dm_list)
    sm_minus = wilder(minus_dm_list)
    sm_tr    = wilder(tr_list)

    dx_list = []
    for p, m, t in zip(sm_plus, sm_minus, sm_tr):
        if t == 0:
            continue
        plus_di  = 100 * p / t
        minus_di = 100 * m / t
        di_sum   = plus_di + minus_di
        if di_sum == 0:
            continue
        dx_list.append(100 * abs(plus_di - minus_di) / di_sum)

    if not dx_list:
        return 0.0
    if len(dx_list) < period:
        return round(sum(dx_list) / len(dx_list), 2)

    adx_val = sum(dx_list[:period]) / period
    for dx in dx_list[period:]:
        adx_val = (adx_val * (period - 1) + dx) / period
    return round(adx_val, 2)


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
        "atr":   atr(highs, lows, closes),
        "adx":   adx(highs, lows, closes),
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
