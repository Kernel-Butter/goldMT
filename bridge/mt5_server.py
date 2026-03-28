"""
MT5 Bridge Server — runs on Windows machine with MetaTrader 5 installed.

Setup:
1. Copy this file to your Windows machine
2. Install: pip install MetaTrader5
3. Open MetaTrader 5 and log in to your demo account
4. Run: python mt5_server.py
5. Update BRIDGE_HOST in config.py on Mac to point to this machine's IP
"""

import socket
import json
import threading
import MetaTrader5 as mt5

HOST = "0.0.0.0"   # listen on all interfaces
PORT = 9999

TIMEFRAME_MAP = {
    "M1":  mt5.TIMEFRAME_M1,
    "M5":  mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "H1":  mt5.TIMEFRAME_H1,
    "H4":  mt5.TIMEFRAME_H4,
    "D1":  mt5.TIMEFRAME_D1,
}


def handle_command(cmd: dict) -> dict:
    action = cmd.get("cmd")

    if action == "get_candles":
        tf = TIMEFRAME_MAP.get(cmd["timeframe"], mt5.TIMEFRAME_H1)
        rates = mt5.copy_rates_from_pos(cmd["symbol"], tf, 0, cmd.get("count", 100))
        if rates is None:
            return {"error": "Failed to get candles"}
        return [
            {"time": int(r["time"]), "open": r["open"], "high": r["high"],
             "low": r["low"], "close": r["close"], "volume": int(r["tick_volume"])}
            for r in rates
        ]

    elif action == "get_tick":
        tick = mt5.symbol_info_tick(cmd["symbol"])
        if tick is None:
            return {"error": "Failed to get tick"}
        return {"bid": tick.bid, "ask": tick.ask}

    elif action == "get_account":
        info = mt5.account_info()
        if info is None:
            return {"error": "Failed to get account"}
        return {"balance": info.balance, "equity": info.equity, "margin": info.margin}

    elif action == "get_positions":
        positions = mt5.positions_get()
        if positions is None:
            return []
        return [
            {"ticket": p.ticket, "symbol": p.symbol, "type": "BUY" if p.type == 0 else "SELL",
             "lot": p.volume, "open_price": p.price_open, "sl": p.sl, "tp": p.tp, "profit": p.profit}
            for p in positions
        ]

    elif action == "place_order":
        order_type = mt5.ORDER_TYPE_BUY if cmd["action"] == "BUY" else mt5.ORDER_TYPE_SELL
        request = {
            "action":   mt5.TRADE_ACTION_DEAL,
            "symbol":   cmd["symbol"],
            "volume":   cmd["lot"],
            "type":     order_type,
            "sl":       cmd["sl"],
            "tp":       cmd["tp"],
            "deviation": 20,
            "magic":    123456,
            "comment":  "GoldBot",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return {"error": f"Order failed: {result.comment}", "retcode": result.retcode}
        return {"ticket": result.order, "status": "ok"}

    elif action == "close_position":
        positions = mt5.positions_get(ticket=cmd["ticket"])
        if not positions:
            return {"error": "Position not found"}
        pos = positions[0]
        close_type = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
        tick = mt5.symbol_info_tick(pos.symbol)
        price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask
        request = {
            "action":   mt5.TRADE_ACTION_DEAL,
            "symbol":   pos.symbol,
            "volume":   pos.volume,
            "type":     close_type,
            "position": pos.ticket,
            "price":    price,
            "deviation": 20,
            "magic":    123456,
            "comment":  "GoldBot close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return {"error": f"Close failed: {result.comment}"}
        return {"status": "closed", "ticket": cmd["ticket"]}

    else:
        return {"error": f"Unknown command: {action}"}


def handle_client(conn, addr):
    print(f"[+] Connection from {addr}")
    try:
        data = b""
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk
            if b"\n" in data:
                break
        cmd = json.loads(data.strip())
        response = handle_command(cmd)
        conn.sendall(json.dumps(response).encode() + b"\n")
    except Exception as e:
        conn.sendall(json.dumps({"error": str(e)}).encode() + b"\n")
    finally:
        conn.close()


def main():
    if not mt5.initialize():
        print("Failed to initialize MT5:", mt5.last_error())
        return

    print(f"MT5 bridge server running on port {PORT}")
    print(f"MT5 version: {mt5.version()}")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen(5)
        print("Waiting for connections...")
        while True:
            conn, addr = server.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()


if __name__ == "__main__":
    main()
