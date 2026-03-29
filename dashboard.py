import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import time
from datetime import datetime, timezone

import mt5_bridge as bridge
from config import SYMBOL
from db import (
    init_db, get_decisions, get_trades, get_chart_trades,
    get_equity_history, get_stats, get_session_stats,
)

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
  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
  .block-container { padding: 1.5rem 2rem 2rem 2rem; }
  #MainMenu, footer, header { visibility: hidden; }

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

  .section-header {
    color: #8b8fa8;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin-bottom: 0.5rem;
    margin-top: 1.2rem;
  }

  .badge-buy  { background:#0d2b1e; color:#00e676; border:1px solid #00e676;
                padding:2px 10px; border-radius:20px; font-size:0.75rem; font-weight:600; }
  .badge-sell { background:#2b0d0d; color:#ff5252; border:1px solid #ff5252;
                padding:2px 10px; border-radius:20px; font-size:0.75rem; font-weight:600; }
  .badge-hold { background:#1e1e2e; color:#8b8fa8; border:1px solid #3a3d52;
                padding:2px 10px; border-radius:20px; font-size:0.75rem; }

  [data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }

  .status-live  { color:#00e676; font-size:0.8rem; }
  .status-error { color:#ff5252; font-size:0.8rem; }

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


# ── Indicator series helpers (full rolling series for chart) ──

def _ema_series(closes: list, period: int) -> list:
    """Full EMA series — first (period-1) values are None."""
    if len(closes) < period:
        return [None] * len(closes)
    k = 2.0 / (period + 1)
    result = [None] * (period - 1)
    val = sum(closes[:period]) / period
    result.append(val)
    for price in closes[period:]:
        val = price * k + val * (1 - k)
        result.append(val)
    return result


def _rsi_series(closes: list, period: int = 14) -> list:
    """Full RSI series using Wilder's smoothing — first period values are None."""
    if len(closes) < period + 1:
        return [None] * len(closes)

    result = [None] * period
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains  = [max(d, 0.0) for d in deltas]
    losses = [abs(min(d, 0.0)) for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    def _to_rsi(ag, al):
        return 100.0 if al == 0 else round(100.0 - 100.0 / (1.0 + ag / al), 2)

    result.append(_to_rsi(avg_gain, avg_loss))
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        result.append(_to_rsi(avg_gain, avg_loss))

    return result


# ── Live data fetch ───────────────────────────────────────

@st.cache_data(ttl=15)
def fetch_live():
    try:
        account   = bridge.get_account()
        positions = bridge.get_positions()
        return account, positions, True
    except Exception:
        return {"balance": 0, "equity": 0}, [], False


@st.cache_data(ttl=30)
def fetch_chart_candles(timeframe: str, count: int):
    try:
        candles = bridge.get_candles(SYMBOL, timeframe, count=count)
        if not candles or isinstance(candles, dict):
            return [], False
        return candles, True
    except Exception:
        return [], False


# ── Formatting helpers ────────────────────────────────────

def format_pnl(val):
    sign  = "+" if val >= 0 else ""
    color = "pos-profit-pos" if val >= 0 else "pos-profit-neg"
    return f'<span class="{color}">{sign}${val:,.2f}</span>'


def action_badge(action):
    cls = {"BUY": "badge-buy", "SELL": "badge-sell"}.get(action, "badge-hold")
    return f'<span class="{cls}">{action}</span>'


def _parse_utc(ts_str):
    """Parse ISO timestamp string to UTC-aware datetime. Returns None on failure."""
    if not ts_str or (isinstance(ts_str, float) and pd.isna(ts_str)):
        return None
    try:
        dt = pd.to_datetime(ts_str, utc=True)
        return dt.to_pydatetime()
    except Exception:
        return None


# ── Data load ─────────────────────────────────────────────
account, positions, connected = fetch_live()
balance      = account.get("balance", 0)
equity       = account.get("equity", 0)
pnl          = equity - balance
eq_hist      = get_equity_history()
stats        = get_stats()
decisions_df = get_decisions(50)
trades_df    = get_trades(50)
chart_trades = get_chart_trades(200)
session_df   = get_session_stats()

# ── Header ────────────────────────────────────────────────
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

# ── Live Gold Chart ───────────────────────────────────────
st.markdown('<p class="section-header">Live Chart — XAUUSD</p>', unsafe_allow_html=True)

ctrl_tf, ctrl_count, _ = st.columns([2, 3, 5])
with ctrl_tf:
    tf = st.radio("Timeframe", ["H1", "H4", "D1"], horizontal=True, index=0,
                  label_visibility="collapsed")
with ctrl_count:
    candle_count = st.select_slider("Candles", options=[50, 100, 200], value=100,
                                    label_visibility="collapsed")

candles, chart_ok = fetch_chart_candles(tf, candle_count)

if not chart_ok or not candles:
    st.info("Chart unavailable — MT5 bridge is offline.")
else:
    # Build series
    times  = [datetime.fromtimestamp(c["time"], tz=timezone.utc) for c in candles]
    opens  = [c["open"]  for c in candles]
    highs  = [c["high"]  for c in candles]
    lows   = [c["low"]   for c in candles]
    closes = [c["close"] for c in candles]

    ema20 = _ema_series(closes, 20)
    ema50 = _ema_series(closes, 50)
    rsi_vals = _rsi_series(closes, 14)

    # Filter chart_trades to only show within visible candle window
    chart_start = times[0]
    chart_end   = times[-1]

    def _in_window(ts_str):
        dt = _parse_utc(ts_str)
        return dt is not None and chart_start <= dt <= chart_end

    ct = chart_trades.copy() if not chart_trades.empty else pd.DataFrame()
    if not ct.empty:
        ct = ct[ct["entry_time"].apply(_in_window)]

    # Build figure
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.70, 0.30],
        vertical_spacing=0.03,
    )

    # ── Row 1: Price ──────────────────────────────────────
    fig.add_trace(go.Candlestick(
        x=times, open=opens, high=highs, low=lows, close=closes,
        name="XAUUSD",
        increasing_line_color="#00e676",
        decreasing_line_color="#ff5252",
        increasing_fillcolor="#1a4d2e",
        decreasing_fillcolor="#4d1a1a",
        line=dict(width=1),
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=times, y=ema20,
        mode="lines", name="EMA20",
        line=dict(color="#ffd700", width=1.4),
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=times, y=ema50,
        mode="lines", name="EMA50",
        line=dict(color="#ff8c00", width=1.4),
    ), row=1, col=1)

    # Trade entry markers
    if not ct.empty:
        buys  = ct[ct["action"] == "BUY"]
        sells = ct[ct["action"] == "SELL"]

        def _entry_tooltip(row):
            rsi_str   = f"{row['h1_rsi']:.1f}" if pd.notna(row.get("h1_rsi")) else "—"
            conf_str  = f"{row['confidence']:.0%}" if pd.notna(row.get("confidence")) else "—"
            pnl_str   = (f"+${row['pnl_dollars']:.2f}" if row["pnl_dollars"] > 0
                         else f"${row['pnl_dollars']:.2f}") if pd.notna(row.get("pnl_dollars")) else "open"
            reason    = str(row.get("reason") or "")
            return (
                f"<b>{row['action']}</b>  conf {conf_str}<br>"
                f"Entry ${row['entry_price']:.2f}  SL ${row['sl']:.2f}  TP ${row['tp']:.2f}<br>"
                f"RSI(H1) {rsi_str}<br>"
                f"P&L {pnl_str}<br>"
                f"<i>{reason}</i>"
            )

        if not buys.empty:
            fig.add_trace(go.Scatter(
                x=[_parse_utc(r["entry_time"]) for _, r in buys.iterrows()],
                y=list(buys["entry_price"]),
                mode="markers", name="BUY",
                marker=dict(symbol="triangle-up", size=12, color="#00e676",
                            line=dict(color="#004d20", width=1)),
                text=[_entry_tooltip(r) for _, r in buys.iterrows()],
                hoverinfo="text",
            ), row=1, col=1)

        if not sells.empty:
            fig.add_trace(go.Scatter(
                x=[_parse_utc(r["entry_time"]) for _, r in sells.iterrows()],
                y=list(sells["entry_price"]),
                mode="markers", name="SELL",
                marker=dict(symbol="triangle-down", size=12, color="#ff5252",
                            line=dict(color="#4d0000", width=1)),
                text=[_entry_tooltip(r) for _, r in sells.iterrows()],
                hoverinfo="text",
            ), row=1, col=1)

        # Exit markers for closed trades
        closed = ct[ct["exit_price"].notna() & ct["exit_time"].apply(
            lambda t: _in_window(t) if t else False)]
        if not closed.empty:
            wins   = closed[closed["pnl_dollars"] > 0]
            losses = closed[closed["pnl_dollars"] <= 0]

            for subset, color, label in [
                (wins,   "#00e676", "Exit ✓"),
                (losses, "#ff5252", "Exit ✗"),
            ]:
                if not subset.empty:
                    def _exit_tooltip(row):
                        pnl_str = (f"+${row['pnl_dollars']:.2f}"
                                   if row['pnl_dollars'] > 0
                                   else f"${row['pnl_dollars']:.2f}")
                        reason  = row.get("close_reason") or "closed"
                        return f"<b>Exit</b>  ${row['exit_price']:.2f}<br>P&L {pnl_str}<br>{reason}"

                    fig.add_trace(go.Scatter(
                        x=[_parse_utc(r["exit_time"]) for _, r in subset.iterrows()],
                        y=list(subset["exit_price"]),
                        mode="markers", name=label,
                        marker=dict(symbol="x", size=10, color=color,
                                    line=dict(width=2)),
                        text=[_exit_tooltip(r) for _, r in subset.iterrows()],
                        hoverinfo="text",
                    ), row=1, col=1)

    # ── Row 2: RSI ────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=times, y=rsi_vals,
        mode="lines", name="RSI(14)",
        line=dict(color="#7c6af7", width=1.5),
    ), row=2, col=1)

    # RSI reference lines as filled bands
    fig.add_trace(go.Scatter(
        x=[times[0], times[-1]], y=[70, 70],
        mode="lines", name="OB 70",
        line=dict(color="#ff5252", width=1, dash="dot"),
        showlegend=False,
    ), row=2, col=1)
    fig.add_trace(go.Scatter(
        x=[times[0], times[-1]], y=[50, 50],
        mode="lines", name="Mid 50",
        line=dict(color="#5a5d72", width=1, dash="dot"),
        showlegend=False,
    ), row=2, col=1)
    fig.add_trace(go.Scatter(
        x=[times[0], times[-1]], y=[30, 30],
        mode="lines", name="OS 30",
        line=dict(color="#00e676", width=1, dash="dot"),
        showlegend=False,
    ), row=2, col=1)

    # ── Layout ────────────────────────────────────────────
    fig.update_layout(
        height=600,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#12141f",
        font=dict(color="#8b8fa8", size=11),
        margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, x=0,
            bgcolor="rgba(0,0,0,0)", font=dict(color="#8b8fa8", size=10),
        ),
        hovermode="x unified",
        xaxis=dict(
            gridcolor="#1e2030", showgrid=True, zeroline=False,
            rangeslider=dict(visible=False),
        ),
        yaxis=dict(
            gridcolor="#1e2030", showgrid=True, zeroline=False,
            title=dict(text="Price (USD)", font=dict(size=10)),
        ),
        xaxis2=dict(gridcolor="#1e2030", showgrid=True, zeroline=False),
        yaxis2=dict(
            gridcolor="#1e2030", showgrid=True, zeroline=False,
            range=[0, 100],
            title=dict(text="RSI", font=dict(size=10)),
            tickvals=[30, 50, 70],
        ),
    )

    st.plotly_chart(fig, use_container_width=True)

# ── Equity Curve ──────────────────────────────────────────
st.markdown('<p class="section-header">Equity Curve</p>', unsafe_allow_html=True)

if not eq_hist.empty:
    fig_eq = go.Figure()
    fig_eq.add_trace(go.Scatter(
        x=eq_hist["timestamp"], y=eq_hist["equity"],
        mode="lines", name="Equity",
        line=dict(color="#7c6af7", width=2),
        fill="tozeroy",
        fillcolor="rgba(124,106,247,0.07)"
    ))
    fig_eq.add_trace(go.Scatter(
        x=eq_hist["timestamp"], y=eq_hist["balance"],
        mode="lines", name="Balance",
        line=dict(color="#2a2d3e", width=1.5, dash="dot")
    ))
    fig_eq.update_layout(
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
    st.plotly_chart(fig_eq, use_container_width=True)
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
            ts    = row["timestamp"][:16].replace("T", " ")
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
    cols = ["timestamp", "action", "lot", "entry_price", "exit_price",
            "pnl_dollars", "close_reason", "duration_minutes", "ticket"]
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
