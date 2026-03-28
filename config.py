import os
from dotenv import load_dotenv

load_dotenv()

# --- Groq / AI ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# --- Instrument ---
SYMBOL = "XAUUSD"
TIMEFRAMES = ["H1", "H4", "D1"]  # entry, trend, macro

# --- MT5 Bridge ---
BRIDGE_HOST = "127.0.0.1"  # change to Windows VPS IP when ready
BRIDGE_PORT = 9999

# --- Risk ---
RISK_PER_TRADE = 0.01      # 1% of account per trade
MAX_OPEN_TRADES = 2
DAILY_LOSS_LIMIT = 0.03    # 3% daily drawdown limit

# --- XAUUSD Contract Spec ---
# Standard lot = 100 oz. A $1 move = $100 P&L per lot.
# Holds for IC Markets, XM, Pepperstone, most MT5 brokers.
XAUUSD_DOLLAR_PER_LOT = 100.0

# --- Bot Loop ---
CHECK_INTERVAL = 60        # seconds between each analysis cycle
