import socket
import json
from config import BRIDGE_HOST, BRIDGE_PORT


def _send(command: dict) -> dict:
    """Send a JSON command to the MT5 bridge server and return the response."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(10)
        s.connect((BRIDGE_HOST, BRIDGE_PORT))
        s.sendall(json.dumps(command).encode() + b"\n")

        data = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
            if b"\n" in data:
                break

    return json.loads(data.strip())


def get_candles(symbol: str, timeframe: str, count: int = 100) -> list:
    """Get OHLCV candles. Returns list of dicts."""
    return _send({"cmd": "get_candles", "symbol": symbol, "timeframe": timeframe, "count": count})


def get_tick(symbol: str) -> dict:
    """Get current bid/ask. Returns {"bid": x, "ask": x}."""
    return _send({"cmd": "get_tick", "symbol": symbol})


def get_account() -> dict:
    """Get account info. Returns {"balance": x, "equity": x, "margin": x}."""
    return _send({"cmd": "get_account"})


def get_positions() -> list:
    """Get open positions. Returns list of position dicts."""
    return _send({"cmd": "get_positions"})


def place_order(symbol: str, action: str, lot: float, sl: float, tp: float) -> dict:
    """
    Place a market order.
    action: "BUY" or "SELL"
    sl/tp: absolute price levels
    """
    return _send({
        "cmd": "place_order",
        "symbol": symbol,
        "action": action,
        "lot": lot,
        "sl": sl,
        "tp": tp
    })


def modify_position(ticket: int, sl: float) -> dict:
    """Move the stop loss of an open position to a new absolute price level."""
    return _send({"cmd": "modify_position", "ticket": ticket, "sl": sl})


def close_position(ticket: int) -> dict:
    """Close a position by ticket number."""
    return _send({"cmd": "close_position", "ticket": ticket})


def get_closed_deals(from_timestamp: int) -> list:
    """Fetch GoldBot closing deals since from_timestamp (unix seconds)."""
    return _send({"cmd": "get_closed_deals", "from_timestamp": from_timestamp})


if __name__ == "__main__":
    # Connectivity test — will fail if Windows bridge isn't running (expected for now)
    print(f"Attempting to connect to MT5 bridge at {BRIDGE_HOST}:{BRIDGE_PORT}...")
    try:
        account = get_account()
        print("Connected! Account:", account)
    except ConnectionRefusedError:
        print("Connection refused — MT5 bridge server is not running yet (expected).")
    except TimeoutError:
        print("Timeout — check BRIDGE_HOST/BRIDGE_PORT in config.py.")
    except Exception as e:
        print(f"Error: {e}")
