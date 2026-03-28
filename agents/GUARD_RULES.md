# GUARD RULES — Industrial-Grade Code Standards
> Enforced by Guard (Inspector) on every code change. Non-negotiable.

---

## 1. Security Rules

### SQL — Always Parameterized
```python
# WRONG — never do this
cursor.execute(f"SELECT * FROM trades WHERE action = '{action}'")

# RIGHT
cursor.execute("SELECT * FROM trades WHERE action = ?", (action,))
```

### No Secrets in Code
- API keys, passwords, tokens — always in `.env`, never hardcoded
- `.env` is gitignored — verify before committing

### No Command Injection
- Never pass user input directly to shell commands
- If shell calls are needed, use `subprocess` with a list, not a string

---

## 2. Naming Conventions

| Thing | Style | Example |
|-------|-------|---------|
| Functions | `snake_case` | `calc_lot()`, `get_positions()` |
| Variables | `snake_case` | `sl_dollars`, `open_positions` |
| Constants | `UPPER_SNAKE_CASE` | `RISK_PER_TRADE`, `BRIDGE_PORT` |
| Classes | `PascalCase` | `RiskManager` (if ever added) |
| Files | `snake_case.py` | `risk_manager.py` |

---

## 3. Critical Constants — Protected

These values must NEVER change without explicit user approval:

| Constant | File | Value | Why |
|----------|------|-------|-----|
| `XAUUSD_DOLLAR_PER_LOT` | `config.py` | `100.0` | Contract spec — wrong value = wrong lot sizing |
| `MAGIC_NUMBER` | `bridge/mt5_server.py` | `123456` | Trade identifier — changing breaks position tracking |
| `RISK_PER_TRADE` | `config.py` | `0.01` | Core risk rule |
| `MAX_OPEN_TRADES` | `config.py` | `2` | Hard position cap |
| `DAILY_LOSS_LIMIT` | `config.py` | `0.03` | Drawdown cutoff |

Guard must check these constants have not changed in any review touching `config.py` or `bridge/mt5_server.py`.

---

## 4. SL/TP Contract

`sl_dollars` and `tp_dollars` are always:
- Dollar distance from entry price
- NOT pips
- NOT absolute price levels

If any code uses `sl_pips` or `tp_pips`, it is a naming violation — rename immediately.

---

## 5. Code Structure Rules

### One Job Per Function
Each function does one thing. If a function has two `and`-connected responsibilities, split it.

### No Magic Numbers
```python
# WRONG
lot = min(max(lot, 0.01), 5.0)  # where do 0.01 and 5.0 come from?

# RIGHT — define in config.py
MIN_LOT = 0.01
MAX_LOT = 5.0
lot = min(max(lot, MIN_LOT), MAX_LOT)
```

### No Duplicate Logic
If the same logic exists in two places, extract it into a shared function.

### No Speculative Code
Do not write code for hypothetical future features. Build what was asked.

### No Dead Code
Remove unused variables, commented-out code blocks, and unreachable branches.

---

## 6. Error Handling Rules

### Bridge Protocol — Always Return Error Dict
```python
# Bridge server errors must return this shape
return {"error": "description of what went wrong"}
```

### Fail Loudly at Boundaries
Validate inputs at system boundaries (user input, API responses, socket data).
Do not validate internally — trust your own code.

### No Silent Failures
```python
# WRONG
try:
    place_order(...)
except:
    pass  # never swallow exceptions silently

# RIGHT
try:
    place_order(...)
except Exception as e:
    print(f"[ERROR] Order placement failed: {e}")
    return {"error": str(e)}
```

---

## 7. Import Order
```python
# 1. Standard library
import os
import json
import socket

# 2. Third-party
import requests
import pandas as pd

# 3. Local modules
from config import SYMBOL, BRIDGE_HOST
from db import log_trade
```

---

## 8. Terminal / CLI Output
- No blue color (`\033[34m`, `\033[94m`, `Fore.BLUE`, `chalk.blue`)
- Allowed colors: white, green, yellow, red, or plain text
- Log levels: `[INFO]`, `[WARNING]`, `[ERROR]` prefix recommended

---

## 9. Domain Boundaries (enforced)
Each agent owns specific files. No agent may modify another's files.
See `ORCHESTRATION.md` domain boundary table.

Violation = Guard FAIL (critical).

---

## 10. Readability Standard
Every function must pass this test:
> Can a developer who has never seen this codebase understand what this function does in 30 seconds?

If no: add a single-line comment above the function explaining *why* it does what it does (not *what* — the code shows the what).

```python
# Clamp lot size to broker minimum/maximum after 1% risk calculation
lot = min(max(raw_lot, MIN_LOT), MAX_LOT)
```

---

## Guard Review Severity

| Severity | Meaning | Required action |
|----------|---------|-----------------|
| critical | Logic bug, security hole, broken contract, domain violation | Must fix before done |
| warning | Quality issue, inconsistency, minor readability | Fix recommended; user can accept |
