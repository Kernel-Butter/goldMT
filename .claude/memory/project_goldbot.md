---
name: GoldBot MT5 Project
description: AI trading bot for XAUUSD (Gold) on MetaTrader 5, running on user's local Windows PC
type: project
---

GoldBot is an AI-powered XAUUSD trading bot in `H:/code/goldMT/`. Everything runs locally on the user's Windows PC — MT5 bridge server and bot are on the same machine (BRIDGE_HOST = 127.0.0.1).

**Goal:** Run profitably on MT5 demo first, validate results, then move to real account.

**Architecture:**
- `main.py` — main loop: fetch data → AI decision → risk check → place order
- `groq_analyst.py` — sends OHLCV + indicators to Groq (LLaMA 3.3 70B) for BUY/SELL/HOLD
- `technical.py` — pure Python EMA, RSI, ATR, ADX calculation
- `risk_manager.py` — lot sizing (1% risk/trade), max 2 open trades, 3% daily loss limit
- `mt5_bridge.py` — TCP client that talks to the bridge server
- `bridge/mt5_server.py` — TCP server wrapping MetaTrader5 Python API, listens on port 9999
- `dashboard_api.py` — FastAPI server replacing Streamlit; serves `static/index.html` on port 8501
- `static/index.html` — full dashboard: Monitor, Diagnostics, Simple View, Strategy tabs
- `strategy_info.json` — single source of truth for strategy state (current, future plans, history)
- `agents/strategy_tracker.py` — CLI agent to log strategy changes

**Contract spec (critical):** XAUUSD standard lot = 100 oz. $1 price move = $100 P&L per lot. `XAUUSD_DOLLAR_PER_LOT = 100.0` in config.py. Fixed critical bug — do not change.

**SL/TP keys:** `sl_dollars` and `tp_dollars` are dollar distances from entry price — NOT pips, NOT absolute prices.

**Startup:**
1. Copy `.env.example` → `.env`, add GROQ_API_KEY
2. Run `setup.bat` (first time or after clone)
3. Open MetaTrader 5, log into demo account
4. Run `start_all.bat`

**Current phase:** Demo account testing. Not yet live.

**Why:** User wants to validate the strategy on demo before risking real money.

**How to apply:** Prioritise stability and capital preservation over profit maximisation. Keep changes demo-safe first.
