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
            spread      REAL
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
            duration_minutes REAL
        )
    """)

    # Migrate existing trades table if columns are missing
    existing = {row[1] for row in c.execute("PRAGMA table_info(trades)")}
    for col, definition in [
        ("decision_id",      "INTEGER"),
        ("exit_price",       "REAL"),
        ("exit_time",        "TEXT"),
        ("pnl_dollars",      "REAL"),
        ("close_reason",     "TEXT"),
        ("duration_minutes", "REAL"),
    ]:
        if col not in existing:
            c.execute(f"ALTER TABLE trades ADD COLUMN {col} {definition}")

    c.execute("""
        CREATE TABLE IF NOT EXISTS equity_history (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT  NOT NULL,
            balance   REAL  NOT NULL,
            equity    REAL  NOT NULL
        )
    """)

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
        "(decision_id,session,h1_rsi,h4_rsi,d1_rsi,h1_ema20,h4_ema20,h1_atr,spread) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
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
        )
    )
    conn.commit()
    conn.close()


def log_trade(action: str, lot: float, entry_price: float,
              sl: float, tp: float, ticket: int, decision_id: int = None):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO trades (timestamp,action,lot,entry_price,sl,tp,ticket,decision_id) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (_now(), action, lot, entry_price, sl, tp, ticket, decision_id)
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
