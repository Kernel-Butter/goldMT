# GoldBot MT5 — AI Working Guide
> Read this first. Always. Every session. Every agent.

---

## Resuming on a New Machine

Memory and project context are stored **inside the repo** at `.claude/memory/`.
On a fresh clone, read these files at the start of every session:

```
.claude/memory/MEMORY.md              ← index of all memories
.claude/memory/project_goldbot.md     ← project goals, architecture, critical rules
.claude/memory/feedback_*.md          ← user preferences and workflow feedback
```

Also read:
- `agents/context/CODEBASE_MAP.md` — full map of every file and function
- `strategy_info.json` — current strategy state, future plans, change history

---

## What This Project Is

GoldBot is an AI-powered XAUUSD (Gold) trading bot for MetaTrader 5.
It uses Groq (LLaMA 3.3 70B) to decide BUY / SELL / HOLD every 60 seconds.
It runs entirely on Windows (MT5 is Windows-only).
Current phase: **demo account testing** — not live yet.

---

## Before You Touch Anything

1. Read `agents/context/CODEBASE_MAP.md` — full map of every file, function, and dependency
2. Read `agents/GUARD_RULES.md` — non-negotiable code standards
3. Read the relevant agent role file in `agents/roles/` for the work you are about to do

This takes 2 minutes and saves hours of mistakes.

---

## The 9 Agents

This project uses a structured multi-agent system. Every task is routed through the right specialist.

| Agent | File | Does |
|-------|------|------|
| **Reader** *(Analyst)* | `agents/roles/requirement_analyst.md` | Understands what you want |
| **Planner** *(Architect)* | `agents/roles/implementation_planner.md` | Decides how to build it |
| **Boss** *(Orchestrator)* | `agents/roles/task_orchestrator.md` | Splits work, assigns to others |
| **Screen** *(UI Agent)* | `agents/roles/ui_dashboard_builder.md` | Builds dashboards and visuals |
| **Store** *(Data Agent)* | `agents/roles/database_manager.md` | Handles database and logs |
| **Trader** *(Strategy Agent)* | `agents/roles/trading_strategy_engine.md` | Trading logic, signals, AI decisions |
| **Bridge** *(MT5 Agent)* | `agents/roles/mt5_connection_handler.md` | MT5 connection and orders |
| **Guard** *(Inspector)* | `agents/roles/code_quality_inspector.md` | Checks code quality |
| **Map** *(Context Agent)* | `agents/roles/codebase_context_tracker.md` | Knows where everything is |

### How tasks flow:
```
User request → Reader → Planner → Boss → Specialists (parallel) → Guard → Map → Done
```
For small changes: `Boss → Specialist → Guard → Done`

Full workflow details: `agents/ORCHESTRATION.md`

---

## File Ownership (strict — do not cross boundaries)

| File | Owner Agent |
|------|-------------|
| `dashboard.py` | Screen |
| `db.py` | Store |
| `main.py`, `config.py`, `groq_analyst.py`, `technical.py`, `risk_manager.py` | Trader |
| `mt5_bridge.py`, `bridge/mt5_server.py` | Bridge |
| `agents/context/CODEBASE_MAP.md` | Map |
| `agents/GUARD_RULES.md` | Guard |

---

## Critical Rules — Never Break These

### 1. Contract spec
`XAUUSD_DOLLAR_PER_LOT = 100.0` — 1 lot = 100 oz gold. $1 price move = $100 P&L per lot.
This was a critical bug that was fixed. Do not change this value without explicit user approval.

### 2. SL/TP are dollar distances
`sl_dollars` and `tp_dollars` are the dollar distance from entry price — NOT pips, NOT absolute prices.
If you see `sl_pips` or `tp_pips` anywhere, rename it.

### 3. Magic number
All bot orders use `magic=123456`. This is how the bot identifies its own trades.
Changing this breaks position tracking.

### 4. Risk constants
- `RISK_PER_TRADE = 0.01` (1% per trade)
- `MAX_OPEN_TRADES = 2`
- `DAILY_LOSS_LIMIT = 0.03` (3% drawdown cutoff)
Do not change without explicit user approval.

### 5. No blue in terminal output
User preference. Use white, green, yellow, red, or plain text only.

### 6. Guard always runs last
No change is done until Guard reviews it. No exceptions.

### 7. Demo first
This bot is in demo testing. Prioritize stability and capital preservation over profit optimization.

---

## How to Start the Bot

```
# Step 1 — first time only
copy .env.example .env
# add your GROQ_API_KEY to .env

# Step 2 — run setup (first time only, or after clone)
setup.bat

# Step 3 — start everything
start_all.bat
```

`start_all.bat` launches:
1. MT5 bridge server (port 9999) — requires MetaTrader 5 open with demo account
2. Bot (main.py)
3. Dashboard (Streamlit on http://localhost:8501)

---

## Architecture in One Diagram

```
MetaTrader 5 (Windows app)
        ↕  MT5 Python API
bridge/mt5_server.py  [TCP :9999]
        ↕  JSON over TCP
mt5_bridge.py
        ↕
main.py  ←→  technical.py      (RSI, EMA, ATR)
         ←→  groq_analyst.py   (Groq AI → BUY/SELL/HOLD)
         ←→  risk_manager.py   (lot size, max trades, drawdown)
         ↓
        db.py  →  goldbot.db   (SQLite: decisions, trades, equity)
         ↑
dashboard.py  →  browser :8501  (Streamlit monitoring)
```

---

## Key Files at a Glance

| File | What it does |
|------|-------------|
| `main.py` | 60s loop: fetch → AI → risk → order |
| `config.py` | All settings — single source of truth |
| `groq_analyst.py` | Sends market data to Groq, returns action |
| `technical.py` | RSI, EMA20, EMA50, ATR |
| `risk_manager.py` | calc_lot(), can_trade() |
| `mt5_bridge.py` | TCP client to MT5 |
| `bridge/mt5_server.py` | TCP server wrapping MT5 API |
| `db.py` | SQLite logging |
| `dashboard.py` | Streamlit UI |

---

## Environment Variables

Only one required: `GROQ_API_KEY` in `.env`
Template: `.env.example`

---

## After Cloning to a New Machine

1. `setup.bat` — installs deps, creates venv, generates MCP config for this machine
2. Open MetaTrader 5, log into demo account
3. `start_all.bat`

That's it.
