import requests
import json
from config import GROQ_API_KEY, GROQ_MODEL, GROQ_URL

SYSTEM_PROMPT = """You are an expert Gold (XAUUSD) trading analyst.

You will receive data for H1, H4, and D1 timeframes. Each timeframe includes:
- indicators: RSI, EMA20, EMA50, ATR, ADX
- candles: last 5 OHLC candles (oldest → newest) for price action context
All prices are in USD per troy ounce.

Your job is to analyze the data and return a trading decision as JSON only.

Analysis rules:
- BUY only when multiple timeframes align bullish
- SELL only when multiple timeframes align bearish
- HOLD when the setup is unclear, choppy, or high-risk
- Respect the trend hierarchy: D1 overrides H4, H4 overrides H1
- Never trade counter to a strong D1 trend (RSI > 70 in downtrend, < 30 in uptrend)
- ADX < 20 = ranging market — return HOLD; ADX 20-25 = developing trend — reduce confidence; ADX > 25 = trending — trade normally
- Use ATR to size SL/TP — typical Gold SL is 1x ATR (H1), TP is 2x ATR minimum (RR >= 2)
- Prefer entries near EMA20/EMA50 support/resistance, not in the middle of a move
- Use the last 5 candles to assess momentum: consecutive same-direction candles, wicks, ranges
- Only trade with confidence >= 0.65; otherwise return HOLD

sl_dollars and tp_dollars are PRICE distances in USD (e.g. 15 means SL is $15 away from entry).
These must be positive numbers. A typical Gold SL is $10-$40, TP $20-$80.

Respond ONLY with valid JSON, no markdown, no explanation outside the JSON:
{
  "action": "BUY" | "SELL" | "HOLD",
  "confidence": 0.0-1.0,
  "reason": "explanation under 50 words covering trend, momentum, and ADX",
  "sl_dollars": <positive number>,
  "tp_dollars": <positive number>
}"""


def analyze(market_data: dict) -> dict:
    """Send market data to Groq and get a trading decision."""
    prompt = f"Here is the current market data for XAUUSD:\n\n{json.dumps(market_data, indent=2)}\n\nProvide your trading decision."

    response = requests.post(
        GROQ_URL,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3
        },
        timeout=30
    )

    if not response.ok:
        raise RuntimeError(f"Groq API error {response.status_code}: {response.text}")

    content = response.json()["choices"][0]["message"]["content"].strip()

    # Strip markdown code fences if present
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]

    return json.loads(content)


if __name__ == "__main__":
    # Test with dummy market data
    dummy_data = {
        "symbol": "XAUUSD",
        "timestamp": "2026-03-22T10:00:00",
        "H1": {"open": 3020.5, "high": 3028.0, "low": 3018.2, "close": 3025.4, "rsi": 58.2, "ema20": 3018.0, "atr": 8.5},
        "H4": {"open": 3005.0, "high": 3030.0, "low": 3000.0, "close": 3025.4, "rsi": 62.1, "ema20": 3010.0, "atr": 18.0},
        "D1": {"open": 2990.0, "high": 3035.0, "low": 2985.0, "close": 3025.4, "rsi": 65.0, "ema20": 2980.0, "atr": 35.0},
        "macro": {"dxy_trend": "weakening", "note": "Fed dovish signals, inflation cooling"}
    }

    print("Sending to Groq...")
    result = analyze(dummy_data)
    print("\nDecision:")
    print(json.dumps(result, indent=2))
    # Verify expected keys exist
    assert "sl_dollars" in result, "Missing sl_dollars in response!"
    assert "tp_dollars" in result, "Missing tp_dollars in response!"
    print("Keys OK.")
