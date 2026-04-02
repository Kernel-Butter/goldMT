---
name: Dashboard stack
description: The dashboard uses FastAPI + SSE, not Streamlit. Do not suggest Streamlit changes.
type: feedback
---

The dashboard was replaced in Phase 4. It is now `dashboard_api.py` (FastAPI) serving `static/index.html`.

**Why:** Streamlit fought custom layouts. FastAPI + SSE + Alpine.js + TradingView Lightweight Charts gives full design control and real-time push without polling.

**How to apply:**
- Dashboard work → edit `dashboard_api.py` and/or `static/index.html`
- Do not suggest `streamlit run` or edit `dashboard.py` (kept only as reference)
- Real-time data comes via SSE at `/stream` (60s push) and initial load from `/api/snapshot`
- Strategy info served from `/api/strategy` reading `strategy_info.json` live
