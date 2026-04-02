Run the full multi-agent workflow for this task: $ARGUMENTS

Follow this pipeline strictly:

---

## Step 1 — Reader (Requirement Analyst)
Read `agents/roles/requirement_analyst.md` and `agents/context/CODEBASE_MAP.md`.
Produce a SPEC block: what to do, what not to do, files affected, acceptance criteria.

---

## Step 2 — Planner (Implementation Planner)
Read `agents/roles/implementation_planner.md` and `agents/GUARD_RULES.md`.
Produce a PLAN block: approach, task list with agent assignments, dependencies, risks.

---

## Step 3 — Boss (Task Orchestrator)
Read `agents/roles/task_orchestrator.md`.
Produce WORK ORDERS: assign each task to the right specialist, identify what runs in parallel vs sequential.

---

## Step 4 — Specialists
Execute each work order using the correct agent role:
- UI / dashboard → `agents/roles/ui_dashboard_builder.md`
- Database / logging → `agents/roles/database_manager.md`
- Trading logic / AI / config → `agents/roles/trading_strategy_engine.md`
- MT5 / bridge / orders → `agents/roles/mt5_connection_handler.md`

Read the relevant files before touching them. Stay within domain boundaries.

---

## Step 5 — Guard (Code Quality Inspector)
Read `agents/roles/code_quality_inspector.md` and `agents/GUARD_RULES.md`.
Review all changes. Produce a GUARD REVIEW block: PASS or FAIL with specific issues.
If FAIL on critical issues — fix and re-review before proceeding.

---

## Step 6 — Map (Codebase Context Tracker)
Read `agents/roles/codebase_context_tracker.md`.
If any files were added, removed, renamed, or functions changed — update `agents/context/CODEBASE_MAP.md`.
