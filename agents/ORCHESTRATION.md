# ORCHESTRATION — GoldBot Agent Workflow
> How agents work together. Every task follows this flow.

---

## The 9 Agents

| Agent | Simple Role |
|-------|-------------|
| **Reader** *(Analyst)* | Understands what you want |
| **Planner** *(Architect)* | Decides how to build it |
| **Boss** *(Orchestrator)* | Splits work, assigns to others |
| **Screen** *(UI Agent)* | Builds dashboards and visuals |
| **Store** *(Data Agent)* | Handles database and logs |
| **Trader** *(Strategy Agent)* | Trading logic, signals, AI decisions |
| **Bridge** *(MT5 Agent)* | MT5 connection and orders |
| **Guard** *(Inspector)* | Checks code quality |
| **Map** *(Context Agent)* | Knows where everything is, guides others |

---

## Standard Task Flow

```
User Request
     ↓
  Reader          ← understands the request, writes SPEC
     ↓
  Planner         ← reads SPEC, writes PLAN with tasks assigned to agents
     ↓
   Boss           ← reads PLAN, spawns specialist agents
     ↓
┌────┬────┬────┐
Screen Store Trader Bridge   ← run in parallel where possible
└────┴────┴────┘
     ↓
  Guard           ← reviews all changes, pass/fail
     ↓
  Map             ← updates CODEBASE_MAP.md if structure changed
     ↓
  Done ✓
```

---

## Fast Path (small changes)
For simple, single-file changes where the request is unambiguous:

```
User Request → Boss → [Single Agent] → Guard → Done
```

Examples:
- "Fix the typo in dashboard.py" → Boss → Screen → Guard → Done
- "Add a new config constant" → Boss → Trader → Guard → Done

---

## When to Use Map
Map is called when:
- Any agent is unsure where a file or function lives
- Starting work on an unfamiliar module
- After any structural change to update CODEBASE_MAP.md

Map reads:
- `agents/context/CODEBASE_MAP.md`

---

## Agent Domain Boundaries (strict)

| File | Owner | Others must not touch |
|------|-------|-----------------------|
| `dashboard.py` | Screen | ✗ |
| `db.py` | Store | ✗ |
| `main.py` | Trader | ✗ |
| `config.py` | Trader | ✗ |
| `groq_analyst.py` | Trader | ✗ |
| `technical.py` | Trader | ✗ |
| `risk_manager.py` | Trader | ✗ |
| `mt5_bridge.py` | Bridge | ✗ |
| `bridge/mt5_server.py` | Bridge | ✗ |
| `agents/context/CODEBASE_MAP.md` | Map | ✗ |
| `agents/GUARD_RULES.md` | Guard | ✗ |

If a task requires touching multiple domains, Boss splits it into subtasks — one per domain agent.

---

## Cross-Domain Requests
Example: "Add a new metric to the dashboard that reads from the DB"
1. Boss splits into 2 tasks:
   - Store: add retrieval function to `db.py`
   - Screen: add metric display to `dashboard.py` using the new function
2. Store task runs first (Screen depends on it)
3. Both go to Guard for review

---

## Guard is Mandatory
No change is done until Guard reviews it.
- Guard PASS → task complete
- Guard FAIL (critical) → responsible agent fixes, re-submits to Guard
- Guard FAIL (warning only) → user decides

---

## Communication Protocol Between Agents
When one agent produces output for another:
1. Use labeled blocks: `SPEC`, `PLAN`, `WORK ORDERS`, `GUARD REVIEW`, `MAP RESPONSE`
2. Always state which agent is receiving
3. Include only what the receiving agent needs — no noise

---

## Scaling Rules
As the project grows:
- New files → Map updates CODEBASE_MAP.md
- New domains → new agent role file in `agents/roles/`
- New rules → Guard adds to GUARD_RULES.md
- Boss routing table updated when new agents are added

---

## Starting a New Task (checklist)
- [ ] Read `agents/context/CODEBASE_MAP.md` first
- [ ] Read your own role file in `agents/roles/` (e.g. `requirement_analyst.md`, `trading_strategy_engine.md`, etc.)
- [ ] Read `agents/GUARD_RULES.md` (all agents)
- [ ] Read the files you will touch before touching them
- [ ] Stay within your domain
- [ ] Submit to Guard when done
