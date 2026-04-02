"""
GoldBot Dashboard API
FastAPI + SSE backend serving the live HTML dashboard.
Replaces the old Streamlit dashboard.py.
"""

import asyncio
import json
import sqlite3
import sys
import os
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, os.path.dirname(__file__))

import db as golddb
import mt5_bridge as bridge
from config import SYMBOL
from db import DB_PATH

# ── App ───────────────────────────────────────────────────
app = FastAPI(title="GoldBot Dashboard", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ── Routes ────────────────────────────────────────────────

@app.get("/")
async def root():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/snapshot")
async def snapshot():
    return build_snapshot()


@app.get("/api/strategy")
async def strategy():
    path = os.path.join(os.path.dirname(__file__), "strategy_info.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"error": "strategy_info.json not found"}


@app.get("/stream")
async def stream():
    async def event_generator():
        heartbeat_count = 0
        while True:
            # Push heartbeat comment every 15s (4 × 15s = 60s full cycle)
            for _ in range(4):
                await asyncio.sleep(15)
                heartbeat_count += 1
                yield f": heartbeat {heartbeat_count}\n\n"

            data = build_snapshot()
            yield f"data: {json.dumps(data, default=str)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Snapshot builder ──────────────────────────────────────

def build_snapshot() -> dict:
    # ── Live MT5 data ──────────────────────────────────────
    balance: float = 0.0
    equity: float = 0.0
    open_positions: list = []

    try:
        account = bridge.get_account()
        balance = float(account.get("balance", 0))
        equity = float(account.get("equity", 0))
    except Exception:
        pass

    try:
        raw_positions = bridge.get_positions()
        open_positions = _map_positions(raw_positions)
    except Exception:
        pass

    try:
        candles_raw = bridge.get_candles(SYMBOL, "H1", 200)
        candles = _map_candles(candles_raw)
    except Exception:
        candles = []

    # ── DB data ────────────────────────────────────────────
    stats: dict = {}
    try:
        stats = golddb.get_stats()
    except Exception:
        pass

    decisions: list = []
    try:
        df = golddb.get_decisions(limit=20)
        if not df.empty:
            decisions = _map_decisions(df)
    except Exception:
        pass

    trade_history: list = []
    try:
        df = golddb.get_trade_history(limit=50)
        if not df.empty:
            trade_history = df.to_dict(orient="records")
    except Exception:
        pass

    equity_history: list = []
    try:
        df = golddb.get_equity_history()
        if not df.empty:
            equity_history = df[["timestamp", "balance", "equity"]].to_dict(orient="records")
    except Exception:
        pass

    chart_trades: list = []
    try:
        df = golddb.get_chart_trades(limit=200)
        if not df.empty:
            chart_trades = df.to_dict(orient="records")
    except Exception:
        pass

    session_stats: list = []
    try:
        df = golddb.get_session_stats()
        if not df.empty:
            session_stats = df.to_dict(orient="records")
    except Exception:
        pass

    diagnostics = _build_diagnostics(stats)

    return {
        "balance": balance,
        "equity": equity,
        "equity_change": round(equity - balance, 2),
        "open_count": len(open_positions),
        "stats": stats,
        "decisions": decisions,
        "open_positions": open_positions,
        "trade_history": trade_history,
        "equity_history": equity_history,
        "candles": candles,
        "chart_trades": chart_trades,
        "session_stats": session_stats,
        "diagnostics": diagnostics,
    }


# ── Field mappers ─────────────────────────────────────────

def _map_positions(raw: list) -> list:
    """Normalise MT5 position fields to dashboard contract."""
    out = []
    for p in raw:
        action = "BUY" if p.get("type", 0) == 0 else "SELL"
        out.append({
            "ticket":      p.get("ticket"),
            "action":      action,
            "lot":         p.get("volume", p.get("lot", 0)),
            "entry_price": p.get("price_open", p.get("entry_price", 0)),
            "sl":          p.get("sl", 0),
            "tp":          p.get("tp", 0),
            "pnl":         round(float(p.get("profit", p.get("pnl", 0))), 2),
        })
    return out


def _map_candles(raw: list) -> list:
    """Convert candle time strings to Unix timestamps."""
    out = []
    for c in raw:
        t = c.get("time", 0)
        if isinstance(t, str):
            # MT5 format: "2024.01.15 10:00" or ISO
            for fmt in ("%Y.%m.%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                try:
                    dt = datetime.strptime(t, fmt).replace(tzinfo=timezone.utc)
                    t = int(dt.timestamp())
                    break
                except ValueError:
                    continue
            else:
                t = 0
        out.append({
            "time":  int(t),
            "open":  c.get("open", 0),
            "high":  c.get("high", 0),
            "low":   c.get("low", 0),
            "close": c.get("close", 0),
        })
    return [c for c in out if c["time"] > 0]


def _map_decisions(df) -> list:
    """Format decision rows for the AI decisions feed."""
    out = []
    for _, row in df.iterrows():
        ts = row.get("timestamp", "")
        if isinstance(ts, str) and "T" in ts:
            try:
                ts = ts[11:16]  # "HH:MM" from ISO
            except Exception:
                pass
        out.append({
            "timestamp":  ts,
            "action":     row.get("action", ""),
            "confidence": int(float(row.get("confidence", 0) or 0)),
            "reason":     row.get("reason", ""),
        })
    return out


def _build_diagnostics(stats: dict) -> dict:
    """Build diagnostics section from raw DB queries."""
    ai_cycles       = 0
    passed_filter   = 0
    executed_trades = int(stats.get("total_trades", 0))
    conf_buckets    = []
    exit_reasons    = []

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        ai_cycles     = c.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
        passed_filter = c.execute(
            "SELECT COUNT(*) FROM decisions WHERE action != 'HOLD'"
        ).fetchone()[0]

        # Confidence buckets → win rate per band
        for lo, hi, label in [(65, 75, "65-75%"), (75, 85, "75-85%"), (85, 101, "85-100%")]:
            rows = c.execute("""
                SELECT COUNT(*) AS total,
                       SUM(CASE WHEN t.pnl_dollars > 0 THEN 1 ELSE 0 END) AS wins
                FROM decisions d
                JOIN trades t ON t.decision_id = d.id
                WHERE d.confidence >= ? AND d.confidence < ?
                  AND t.pnl_dollars IS NOT NULL
            """, (lo, hi)).fetchone()
            total, wins = rows
            wr = round((wins / total * 100), 1) if total and total > 0 else 0.0
            conf_buckets.append({"range": label, "win_rate": wr, "total": total or 0})

        # Exit reasons
        rows = c.execute("""
            SELECT close_reason,
                   COUNT(*) AS cnt,
                   SUM(CASE WHEN pnl_dollars > 0 THEN 1 ELSE 0 END) AS wins
            FROM trades
            WHERE close_reason IS NOT NULL
            GROUP BY close_reason
            ORDER BY cnt DESC
        """).fetchall()
        for reason, cnt, wins in rows:
            wr = round((wins / cnt * 100), 0) if cnt > 0 else 0
            exit_reasons.append({
                "reason":   reason,
                "count":    cnt,
                "win_rate": int(wr),
            })

        conn.close()
    except Exception:
        pass

    return {
        "ai_cycles":         ai_cycles,
        "passed_prefilter":  passed_filter,
        "executed_trades":   executed_trades,
        "confidence_buckets": conf_buckets,
        "exit_reasons":      exit_reasons,
    }


# ── Entry point ───────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    golddb.init_db()

    print(" ================================================")
    print("   GoldBot Dashboard | http://localhost:8501")
    print(" ================================================")

    uvicorn.run(app, host="0.0.0.0", port=8501, log_level="warning")
