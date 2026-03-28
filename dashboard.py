import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import time
from datetime import datetime, timezone

import mt5_bridge as bridge
from db import init_db, get_decisions, get_trades, get_equity_history, get_stats, get_session_stats

# ── Page config ───────────────────────────────────────────
st.set_page_config(
    page_title="GoldBot",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Styling ───────────────────────────────────────────────
st.markdown("""
<style>
  /* Base */
  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
  .block-container { padding: 1.5rem 2rem 2rem 2rem; }

  /* Hide Streamlit chrome */
  #MainMenu, footer, header { visibility: hidden; }

  /* Metric cards */
  [data-testid="metric-container"] {
    background: #1a1d27;
    border: 1px solid #2a2d3e;
    border-radius: 12px;
    padding: 1rem 1.2rem;
  }
  [data-testid="metric-container"] label {
    color: #8b8fa8 !important;
    font-size: 0.75rem !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  [data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #e8eaf6 !important;
    font-size: 1.6rem !important;
    font-weight: 600;
  }
  [data-testid="stMetricDelta"] { font-size: 0.85rem !important; }

  /* Section headers */
  .section-header {
    color: #8b8fa8;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin-bottom: 0.5rem;
    margin-top: 1.2rem;
  }

  /* Decision badges */
  .badge-buy  { background:#0d2b1e; color:#00e676; border:1px solid #00e676;
                padding:2px 10px; border-radius:20px; font-size:0.75rem; font-weight:600; }
  .badge-sell { background:#2b0d0d; color:#ff5252; border:1px solid #ff5252;
                padding:2px 10px; border-radius:20px; font-size:0.75rem; font-weight:600; }
  .badge-hold { background:#1e1e2e; color:#8b8fa8; border:1px solid #3a3d52;
                padding:2px 10px; border-radius:20px; font-size:0.75rem; }

  /* Table */
  [data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }

  /* Status dot */
  .status-live  { color:#00e676; font-size:0.8rem; }
  .status-error { color:#ff5252; font-size:0.8rem; }

  /* Position card */
  .pos-card {
    background:#1a1d27; border:1px solid #2a2d3e; border-radius:10px;
    padding:0.8rem 1rem; margin-bottom:0.5rem;
  }
  .pos-profit-pos { color:#00e676; font-weight:600; }
  .pos-profit-neg { color:#ff5252; font-weight:600; }
</style>
""", unsafe_allow_html=True)

# ── Init DB ───────────────────────────────────────────────
init_db()

# ── Live data fetch ───────────────────────────────────────
@st.cache_data(ttl=15)
def fetch_live():
    try:
        account   = bridge.get_account()
        positions = bridge.get_positions()
        return account, positions, True
    except Exception as e:
        return {"balance": 0, "equity": 0}, [], False


def format_pnl(val):
    sign = "+" if val >= 0 else ""
    color = "pos-profit-pos" if val >= 0 else "pos-profit-neg"
    return f'<span class="{color}">{sign}${val:,.2f}</span>'


def action_badge(action):
    cls = {"BUY": "badge-buy", "SELL": "badge-sell"}.get(action, "badge-hold")
    return f'<span class="{cls}">{action}</span>'


# ── Layout ────────────────────────────────────────────────
account, positions, connected = fetch_live()
balance  = account.get("balance", 0)
equity   = account.get("equity", 0)
pnl      = equity - balance
eq_hist      = get_equity_history()
stats        = get_stats()
decisions_df = get_decisions(50)
trades_df    = get_trades(50)
session_df   = get_session_stats()

# Header row
col_title, col_status, col_refresh = st.columns([4, 1, 1])
with col_title:
    st.markdown("## 📈 GoldBot Dashboard")
with col_status:
    st.markdown("")
    if connected:
        st.markdown('<p class="status-live">● LIVE</p>', unsafe_allow_html=True)
    else:
        st.markdown('<p class="status-error">● OFFLINE</p>', unsafe_allow_html=True)
with col_refresh:
    st.markdown("")
    st.caption(f"Updated {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC")

st.divider()

# ── Metrics ───────────────────────────────────────────────
m1, m2, m3, m4, m5, m6 = st.columns(6)
with m1:
    st.metric("Balance", f"${balance:,.2f}")
with m2:
    st.metric("Equity", f"${equity:,.2f}", delta=f"{'+' if pnl>=0 else ''}{pnl:,.2f}")
with m3:
    st.metric("Open Trades", len(positions))
with m4:
    st.metric("Total Orders", stats["total_trades"])
with m5:
    wr = stats["win_rate"]
    st.metric("Win Rate", f"{wr:.1f}%",
              help=f"{stats['wins']} wins from {stats['closed_trades']} closed trades")
with m6:
    total_pnl = stats["total_pnl"]
    st.metric("Total P&L", f"${total_pnl:+,.2f}",
              help=f"Avg per trade: ${stats['avg_pnl']:+.2f}")

# ── Equity Curve ──────────────────────────────────────────
st.markdown('<p class="section-header">Equity Curve</p>', unsafe_allow_html=True)

if not eq_hist.empty:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=eq_hist["timestamp"], y=eq_hist["equity"],
        mode="lines", name="Equity",
        line=dict(color="#7c6af7", width=2),
        fill="tozeroy",
        fillcolor="rgba(124,106,247,0.07)"
    ))
    fig.add_trace(go.Scatter(
        x=eq_hist["timestamp"], y=eq_hist["balance"],
        mode="lines", name="Balance",
        line=dict(color="#2a2d3e", width=1.5, dash="dot")
    ))
    fig.update_layout(
        height=280,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#12141f",
        font=dict(color="#8b8fa8", size=11),
        margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1, x=0,
                    bgcolor="rgba(0,0,0,0)", font=dict(color="#8b8fa8")),
        xaxis=dict(gridcolor="#1e2030", showgrid=True, zeroline=False),
        yaxis=dict(gridcolor="#1e2030", showgrid=True, zeroline=False),
        hovermode="x unified"
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Equity history will appear after the first bot cycle.")

# ── Open Positions + Recent Decisions ────────────────────
col_pos, col_dec = st.columns([1, 1])

with col_pos:
    st.markdown('<p class="section-header">Open Positions</p>', unsafe_allow_html=True)
    if positions:
        for p in positions:
            profit = p.get("profit", 0)
            pnl_html = format_pnl(profit)
            direction_icon = "▲" if p["type"] == "BUY" else "▼"
            color = "#00e676" if p["type"] == "BUY" else "#ff5252"
            st.markdown(f"""
            <div class="pos-card">
              <span style="color:{color};font-weight:600">{direction_icon} {p['type']}</span>
              &nbsp;&nbsp;{p['lot']} lots &nbsp;|&nbsp; Entry: <b>${p['open_price']:,.2f}</b>
              &nbsp;&nbsp; P&L: {pnl_html}
              <br><small style="color:#5a5d72">SL {p['sl']:,.2f} &nbsp;·&nbsp; TP {p['tp']:,.2f}
              &nbsp;·&nbsp; #{p['ticket']}</small>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown('<div class="pos-card"><span style="color:#5a5d72">No open positions</span></div>',
                    unsafe_allow_html=True)

with col_dec:
    st.markdown('<p class="section-header">Recent AI Decisions</p>', unsafe_allow_html=True)
    if not decisions_df.empty:
        for _, row in decisions_df.head(8).iterrows():
            ts = row["timestamp"][:16].replace("T", " ")
            badge = action_badge(row["action"])
            conf  = f"{row['confidence']:.0%}"
            reason = row["reason"] or ""
            st.markdown(f"""
            <div class="pos-card">
              <span style="color:#5a5d72;font-size:0.75rem">{ts}</span>
              &nbsp;&nbsp;{badge}&nbsp;&nbsp;
              <span style="color:#8b8fa8;font-size:0.8rem">{conf}</span>
              <br><small style="color:#5a5d72">{reason}</small>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Decisions will appear after the first bot cycle.")

# ── Trade History ─────────────────────────────────────────
st.markdown('<p class="section-header">Trade History</p>', unsafe_allow_html=True)
if not trades_df.empty:
    cols = ["timestamp", "action", "lot", "entry_price", "exit_price", "pnl_dollars", "close_reason", "duration_minutes", "ticket"]
    available = [c for c in cols if c in trades_df.columns]
    display = trades_df[available].copy()
    display.rename(columns={
        "timestamp": "Time", "action": "Action", "lot": "Lot",
        "entry_price": "Entry", "exit_price": "Exit", "pnl_dollars": "P&L",
        "close_reason": "Reason", "duration_minutes": "Mins", "ticket": "Ticket"
    }, inplace=True)
    display["Time"] = display["Time"].str[:16].str.replace("T", " ")
    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Action": st.column_config.TextColumn("Action", width="small"),
            "Lot":    st.column_config.NumberColumn("Lot",    format="%.2f"),
            "Entry":  st.column_config.NumberColumn("Entry",  format="$%.2f"),
            "Exit":   st.column_config.NumberColumn("Exit",   format="$%.2f"),
            "P&L":    st.column_config.NumberColumn("P&L",    format="$%+.2f"),
            "Mins":   st.column_config.NumberColumn("Mins",   format="%.0f"),
        }
    )
else:
    st.info("Trade history will appear after the first order is placed.")

# ── Session Performance ───────────────────────────────────
if not session_df.empty:
    st.markdown('<p class="section-header">Performance by Session</p>', unsafe_allow_html=True)
    st.dataframe(
        session_df[["session", "trades", "wins", "win_rate", "avg_pnl", "total_pnl"]].rename(columns={
            "session": "Session", "trades": "Trades", "wins": "Wins",
            "win_rate": "Win %", "avg_pnl": "Avg P&L", "total_pnl": "Total P&L"
        }),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Win %":     st.column_config.NumberColumn("Win %",    format="%.1f%%"),
            "Avg P&L":   st.column_config.NumberColumn("Avg P&L",  format="$%+.2f"),
            "Total P&L": st.column_config.NumberColumn("Total P&L", format="$%+.2f"),
        }
    )

# ── Auto-refresh every 30s ────────────────────────────────
time.sleep(30)
st.rerun()
