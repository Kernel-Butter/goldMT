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
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT    NOT NULL,
            action    TEXT    NOT NULL,
            confidence REAL   NOT NULL,
            reason    TEXT,
            sl_dollars REAL,
            tp_dollars REAL,
            balance   REAL,
            equity    REAL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT  NOT NULL,
            action      TEXT  NOT NULL,
            lot         REAL  NOT NULL,
            entry_price REAL  NOT NULL,
            sl          REAL  NOT NULL,
            tp          REAL  NOT NULL,
            ticket      INTEGER,
            status      TEXT  DEFAULT 'open'
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
    conn.commit()
    conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_decision(action: str, confidence: float, reason: str,
                 sl_dollars: float, tp_dollars: float,
                 balance: float, equity: float):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO decisions (timestamp,action,confidence,reason,sl_dollars,tp_dollars,balance,equity) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (_now(), action, confidence, reason, sl_dollars, tp_dollars, balance, equity)
    )
    conn.commit()
    conn.close()


def log_trade(action: str, lot: float, entry_price: float,
              sl: float, tp: float, ticket: int):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO trades (timestamp,action,lot,entry_price,sl,tp,ticket) "
        "VALUES (?,?,?,?,?,?,?)",
        (_now(), action, lot, entry_price, sl, tp, ticket)
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

    total = c.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    # Win = trade where tp was closer to entry than sl (proxy; real win tracking needs close prices)
    buys  = c.execute("SELECT COUNT(*) FROM trades WHERE action='BUY'").fetchone()[0]
    sells = c.execute("SELECT COUNT(*) FROM trades WHERE action='SELL'").fetchone()[0]

    hold_count = c.execute(
        "SELECT COUNT(*) FROM decisions WHERE action='HOLD'"
    ).fetchone()[0]
    trade_count = c.execute(
        "SELECT COUNT(*) FROM decisions WHERE action!='HOLD'"
    ).fetchone()[0]

    conn.close()
    return {
        "total_trades": total,
        "buys": buys,
        "sells": sells,
        "hold_count": hold_count,
        "trade_count": trade_count,
    }
