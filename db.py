import sqlite3
import os
import pandas as pd
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "goldbot.db")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp  TEXT  NOT NULL,
            action     TEXT  NOT NULL,
            confidence REAL  NOT NULL,
            reason     TEXT,
            sl_dollars REAL,
            tp_dollars REAL,
            balance    REAL,
            equity     REAL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS decision_context (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            decision_id INTEGER NOT NULL,
            session     TEXT,
            h1_rsi      REAL,
            h4_rsi      REAL,
            d1_rsi      REAL,
            h1_ema20    REAL,
            h4_ema20    REAL,
            h1_atr      REAL,
            spread      REAL,
            h4_atr      REAL,
            ema_aligned INTEGER
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp        TEXT  NOT NULL,
            action           TEXT  NOT NULL,
            lot              REAL  NOT NULL,
            entry_price      REAL  NOT NULL,
            sl               REAL  NOT NULL,
            tp               REAL  NOT NULL,
            ticket           INTEGER,
            decision_id      INTEGER,
            status           TEXT  DEFAULT 'open',
            exit_price       REAL,
            exit_time        TEXT,
            pnl_dollars      REAL,
            close_reason     TEXT,
            duration_minutes REAL,
            sl_dollars       REAL,
            tp_dollars       REAL,
            planned_rr       REAL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS equity_history (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT  NOT NULL,
            balance   REAL  NOT NULL,
            equity    REAL  NOT NULL
        )
    """)

    # SL modification events — every break-even and trail step is logged here
    c.execute("""
        CREATE TABLE IF NOT EXISTS trade_events (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp     TEXT    NOT NULL,
            ticket        INTEGER NOT NULL,
            event_type    TEXT    NOT NULL,
            old_sl        REAL,
            new_sl        REAL,
            current_price REAL
        )
    """)

    # Migrate trades table — add strategy-analysis columns if missing
    existing_trades = {row[1] for row in c.execute("PRAGMA table_info(trades)")}
    for col, definition in [
        ("decision_id",      "INTEGER"),
        ("exit_price",       "REAL"),
        ("exit_time",        "TEXT"),
        ("pnl_dollars",      "REAL"),
        ("close_reason",     "TEXT"),
        ("duration_minutes", "REAL"),
        ("sl_dollars",       "REAL"),
        ("tp_dollars",       "REAL"),
        ("planned_rr",       "REAL"),
    ]:
        if col not in existing_trades:
            c.execute(f"ALTER TABLE trades ADD COLUMN {col} {definition}")

    # Migrate decision_context — add richer market context columns if missing
    existing_ctx = {row[1] for row in c.execute("PRAGMA table_info(decision_context)")}
    for col, definition in [
        ("h4_atr",     "REAL"),
        ("ema_aligned", "INTEGER"),
    ]:
        if col not in existing_ctx:
            c.execute(f"ALTER TABLE decision_context ADD COLUMN {col} {definition}")

    conn.commit()
    conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Write helpers ─────────────────────────────────────────

def log_decision(action: str, confidence: float, reason: str,
                 sl_dollars: float, tp_dollars: float,
                 balance: float, equity: float) -> int:
    """Insert an AI decision record. Returns the new row ID."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO decisions (timestamp,action,confidence,reason,sl_dollars,tp_dollars,balance,equity) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (_now(), action, confidence, reason, sl_dollars, tp_dollars, balance, equity)
    )
    decision_id = c.lastrowid
    conn.commit()
    conn.close()
    return decision_id


def log_decision_context(decision_id: int, session: str, indicators: dict, spread: float):
    """Store indicator values and session at the moment of a decision."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO decision_context "
        "(decision_id,session,h1_rsi,h4_rsi,d1_rsi,h1_ema20,h4_ema20,h1_atr,spread,h4_atr,ema_aligned) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            decision_id,
            session,
            indicators.get("h1_rsi"),
            indicators.get("h4_rsi"),
            indicators.get("d1_rsi"),
            indicators.get("h1_ema20"),
            indicators.get("h4_ema20"),
            indicators.get("h1_atr"),
            spread,
            indicators.get("h4_atr"),
            indicators.get("ema_aligned"),
        )
    )
    conn.commit()
    conn.close()


def log_trade(action: str, lot: float, entry_price: float,
              sl: float, tp: float, ticket: int, decision_id: int = None,
              sl_dollars: float = None, tp_dollars: float = None):
    planned_rr = (round(tp_dollars / sl_dollars, 2)
                  if sl_dollars and tp_dollars and sl_dollars > 0 else None)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO trades "
        "(timestamp,action,lot,entry_price,sl,tp,ticket,decision_id,sl_dollars,tp_dollars,planned_rr) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (_now(), action, lot, entry_price, sl, tp, ticket, decision_id,
         sl_dollars, tp_dollars, planned_rr)
    )
    conn.commit()
    conn.close()


def update_trade_exit(ticket: int, exit_price: float, exit_time: str,
                      pnl_dollars: float, close_reason: str, duration_minutes: float):
    """Fill in exit data when a trade closes."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE trades SET exit_price=?, exit_time=?, pnl_dollars=?, "
        "close_reason=?, duration_minutes=?, status='closed' "
        "WHERE ticket=?",
        (exit_price, exit_time, pnl_dollars, close_reason, duration_minutes, ticket)
    )
    conn.commit()
    conn.close()


def log_equity(balance: float, equity: float):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO equity_history (timestamp,balance,equity) VALUES (?,?,?)",
        (_now(), balance, equity)
    )
    conn.commit()
    conn.close()


def log_trade_event(ticket: int, event_type: str, old_sl: float,
                    new_sl: float, current_price: float):
    """Log a SL modification event (be_triggered or trail_moved) for post-trade analysis."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO trade_events (timestamp,ticket,event_type,old_sl,new_sl,current_price) "
        "VALUES (?,?,?,?,?,?)",
        (_now(), ticket, event_type, old_sl, new_sl, current_price)
    )
    conn.commit()
    conn.close()


# ── Read helpers ──────────────────────────────────────────

def get_decisions(limit: int = 100) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(
        "SELECT * FROM decisions ORDER BY id DESC LIMIT ?", conn, params=(limit,)
    )
    conn.close()
    return df


def get_trades(limit: int = 100) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(
        "SELECT * FROM trades ORDER BY id DESC LIMIT ?", conn, params=(limit,)
    )
    conn.close()
    return df


def get_trade_history(limit: int = 100) -> pd.DataFrame:
    """
    Trades joined with AI reason and market context — used for the dashboard trade history table.
    Includes every column needed to review and improve the strategy.
    """
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("""
        SELECT
            t.timestamp        AS entry_time,
            t.action,
            t.lot,
            t.entry_price,
            t.sl_dollars,
            t.tp_dollars,
            t.planned_rr,
            t.exit_price,
            t.exit_time,
            t.pnl_dollars,
            t.close_reason,
            t.duration_minutes,
            t.status,
            t.ticket,
            d.reason           AS ai_reason,
            d.confidence,
            dc.session,
            dc.h1_rsi,
            dc.h1_atr,
            dc.h4_atr,
            dc.ema_aligned
        FROM trades t
        LEFT JOIN decisions d         ON t.decision_id = d.id
        LEFT JOIN decision_context dc ON t.decision_id = dc.decision_id
        ORDER BY t.id DESC
        LIMIT ?
    """, conn, params=(limit,))
    conn.close()
    return df


def get_equity_history() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM equity_history ORDER BY id ASC", conn)
    conn.close()
    return df


def get_stats() -> dict:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    total_trades  = c.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    closed_trades = c.execute("SELECT COUNT(*) FROM trades WHERE pnl_dollars IS NOT NULL").fetchone()[0]
    wins          = c.execute("SELECT COUNT(*) FROM trades WHERE pnl_dollars > 0").fetchone()[0]
    total_pnl     = c.execute("SELECT COALESCE(SUM(pnl_dollars),0) FROM trades").fetchone()[0]
    avg_pnl       = c.execute("SELECT COALESCE(AVG(pnl_dollars),0) FROM trades WHERE pnl_dollars IS NOT NULL").fetchone()[0]
    buys          = c.execute("SELECT COUNT(*) FROM trades WHERE action='BUY'").fetchone()[0]
    sells         = c.execute("SELECT COUNT(*) FROM trades WHERE action='SELL'").fetchone()[0]
    hold_count    = c.execute("SELECT COUNT(*) FROM decisions WHERE action='HOLD'").fetchone()[0]
    trade_count   = c.execute("SELECT COUNT(*) FROM decisions WHERE action!='HOLD'").fetchone()[0]

    conn.close()

    win_rate = (wins / closed_trades * 100) if closed_trades > 0 else 0
    return {
        "total_trades":  total_trades,
        "closed_trades": closed_trades,
        "wins":          wins,
        "win_rate":      win_rate,
        "total_pnl":     total_pnl,
        "avg_pnl":       avg_pnl,
        "buys":          buys,
        "sells":         sells,
        "hold_count":    hold_count,
        "trade_count":   trade_count,
    }


def get_chart_trades(limit: int = 200) -> pd.DataFrame:
    """Trades joined with decision context — used for chart overlays."""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("""
        SELECT
            t.action,
            t.entry_price,
            t.timestamp   AS entry_time,
            t.sl,
            t.tp,
            t.exit_price,
            t.exit_time,
            t.pnl_dollars,
            t.close_reason,
            t.status,
            dc.h1_rsi,
            dc.h4_rsi,
            dc.h1_atr,
            d.confidence,
            d.reason
        FROM trades t
        LEFT JOIN decision_context dc ON t.decision_id = dc.decision_id
        LEFT JOIN decisions d          ON t.decision_id = d.id
        ORDER BY t.id DESC
        LIMIT ?
    """, conn, params=(limit,))
    conn.close()
    return df


def get_session_stats() -> pd.DataFrame:
    """Win rate and avg P&L broken down by trading session."""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("""
        SELECT
            dc.session,
            COUNT(*)                                          AS trades,
            SUM(CASE WHEN t.pnl_dollars > 0 THEN 1 ELSE 0 END) AS wins,
            ROUND(AVG(t.pnl_dollars), 2)                      AS avg_pnl,
            ROUND(SUM(t.pnl_dollars), 2)                      AS total_pnl
        FROM trades t
        JOIN decision_context dc ON t.decision_id = dc.decision_id
        WHERE t.pnl_dollars IS NOT NULL
        GROUP BY dc.session
        ORDER BY total_pnl DESC
    """, conn)
    conn.close()
    if not df.empty:
        df["win_rate"] = (df["wins"] / df["trades"] * 100).round(1)
    return df
