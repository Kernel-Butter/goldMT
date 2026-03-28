import requests
import json
from config import GROQ_API_KEY, GROQ_MODEL, GROQ_URL

SYSTEM_PROMPT = """You are an expert Gold (XAUUSD) trading analyst.

You will receive market data including OHLCV candles for H1, H4, and D1 timeframes,
along with technical indicators (RSI, EMA, ATR).

Your job is to analyze the data and return a trading decision as JSON only.

Rules:
- BUY if Gold is likely to rise
- SELL if Gold is likely to fall
- HOLD if the setup is unclear or risky
- Consider USD strength (DXY inverse correlation with Gold)
- Respect the trend: D1 > H4 > H1
- Never trade against a strong D1 trend

Respond ONLY with valid JSON in this exact format:
{
  "action": "BUY" | "SELL" | "HOLD",
  "confidence": 0.0-1.0,
  "reason": "brief explanation",
  "sl_pips": <number>,
  "tp_pips": <number>
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
