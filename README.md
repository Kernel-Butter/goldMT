# GoldBot — XAUUSD AI Trading Bot (MT5)

An AI-powered Gold trading bot for MetaTrader 5 using Groq (LLaMA 3.3 70B) for trade decisions.
Trades XAUUSD on H1/H4/D1 timeframes with built-in risk management.

> Currently in **demo mode**. Validate results before switching to a real account.

---

## How It Works

```
main.py  →  mt5_bridge.py  →  bridge/mt5_server.py  →  MetaTrader 5
                ↑
         groq_analyst.py (AI decision via Groq API)
                ↑
         technical.py (RSI, EMA, ATR indicators)
                ↑
         risk_manager.py (lot sizing, drawdown limits)
```

Every 60 seconds the bot:
1. Reads account balance and open positions (bot-only, ignores manual trades)
2. Checks risk rules (max 2 trades, 3% daily loss limit)
3. Fetches OHLCV candles + computes indicators for H1, H4, D1
4. Sends data to Groq AI → gets BUY / SELL / HOLD decision
5. If confidence ≥ 65% and not HOLD → places order with correct lot size

**Risk:** 1% of balance per trade. For XAUUSD standard lot (100 oz), $1 move = $100/lot.

---

## Requirements

- Windows PC (MetaTrader5 Python package is Windows-only)
- Python 3.10+
- MetaTrader 5 desktop app installed and logged into a demo account
- Free Groq API key → [console.groq.com](https://console.groq.com)

---

## Setup

### 1. Clone the repo

```
git clone https://github.com/Kernel-Butter/goldMT.git
cd goldMT
```

### 2. Create and activate virtual environment

```
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies

```
pip install -r requirements.txt
pip install -r bridge/requirements.txt
```

### 4. Add your Groq API key

Copy `.env.example` to `.env` and fill in your key:

```
copy .env.example .env
```

Edit `.env`:
```
GROQ_API_KEY=your_key_here
```

Get a free key at [console.groq.com](https://console.groq.com) → API Keys → Create API Key.

### 5. Install and open MetaTrader 5

- Download MT5 from your broker (XM, IC Markets, Pepperstone, etc.)
- Open it and log in to a **demo account**
- Keep MT5 open while the bot runs

---

## Running the Bot

You need **two terminals** open at the same time.

### Terminal 1 — Start the MT5 bridge

```
venv\Scripts\activate
python bridge/mt5_server.py
```

Expected output:
```
MT5 bridge server running on port 9999
MT5 version: (500, xxxx, ...)
Waiting for connections...
```

### Terminal 2 — Start the bot

```
venv\Scripts\activate
python main.py
```

Expected output:
```
[2026-03-28 ...] GoldBot started — XAUUSD
[2026-03-28 ...] Balance: $100000.00 | Equity: $100000.00 | Open: 0
  AI: BUY | Confidence: 72% | SL: $18.5 | TP: $37.0
  Reason: D1 bullish trend, H4 pullback to EMA20
  ORDER: BUY 0.05 lots @ 3025.40 | SL 3006.90 | TP 3062.40
```

Or use the one-click batch files:
- `bridge/start_bridge.bat` — starts the bridge
- `run_bot.bat` — starts the bot

---

## Configuration

All settings are in [config.py](config.py):

| Setting | Default | Description |
|---|---|---|
| `RISK_PER_TRADE` | `0.01` | 1% of balance risked per trade |
| `MAX_OPEN_TRADES` | `2` | Max simultaneous bot positions |
| `DAILY_LOSS_LIMIT` | `0.03` | Stop trading after 3% daily drawdown |
| `CHECK_INTERVAL` | `60` | Seconds between analysis cycles |
| `XAUUSD_DOLLAR_PER_LOT` | `100.0` | $1 move = $100/lot (standard lot spec) |

---

## Project Structure

```
goldMT/
├── main.py                 # Bot loop
├── config.py               # All settings
├── groq_analyst.py         # AI trade decisions (Groq API)
├── technical.py            # RSI, EMA, ATR indicators
├── risk_manager.py         # Lot sizing + risk checks
├── mt5_bridge.py           # TCP client → bridge server
├── bridge/
│   ├── mt5_server.py       # TCP server wrapping MT5 Python API
│   ├── start_bridge.bat    # One-click bridge launcher
│   └── requirements.txt    # MetaTrader5 package
├── requirements.txt        # Bot dependencies
├── run_bot.bat             # One-click bot launcher
├── .env                    # Your API key (never commit this)
└── .env.example            # Template
```

---

## Safety

- `.env` is in `.gitignore` — your API key is never committed
- The bot only manages positions it opened itself (magic number 123456), manual trades are ignored
- Demo account only until results are validated
