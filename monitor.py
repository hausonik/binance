import os
import time
import json
from datetime import datetime
from dotenv import load_dotenv
from binance.client import Client
from telegram_bot import send_telegram_message

load_dotenv()

client = Client(
    os.getenv("BINANCE_API_KEY"),
    os.getenv("BINANCE_API_SECRET")
)

TRADES_LOG = "trades_log.json"
PNL_FILE = "pnl_history.json"

def load_trades():
    if not os.path.exists(TRADES_LOG):
        return []
    with open(TRADES_LOG, "r") as f:
        try:
            return json.load(f)
        except:
            return []

def save_trades(trades):
    with open(TRADES_LOG, "w") as f:
        json.dump(trades, f, indent=2)

def append_pnl(value: float):
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "pnl": round(value, 8)
    }
    if not os.path.exists(PNL_FILE):
        with open(PNL_FILE, "w") as f:
            json.dump([], f)
    with open(PNL_FILE, "r+") as f:
        try:
            data = json.load(f)
        except:
            data = []
        data.append(entry)
        f.seek(0)
        json.dump(data, f, indent=2)

def get_current_price(symbol):
    try:
        ticker = client.get_symbol_ticker(symbol=symbol)
        return float(ticker["price"])
    except Exception as e:
        print("Ошибка получения цены:", e)
        return None

def place_market_sell(symbol, qty):
    try:
        return client.order_market_sell(symbol=symbol, quantity=qty)
    except Exception as e:
        print("Ошибка SELL:", e)
        return None

def check_and_close_trades():
    trades = load_trades()
    updated_trades = []

    for trade in trades:
        if trade.get("status") != "OPEN":
            updated_trades.append(trade)
            continue

        try:
            symbol = trade["symbol"]
            entry_price = float(trade["avg_price"])
            qty = float(trade["quantity"])
            tp_pct = float(trade["take_profit_pct"])
            sl_pct = float(trade["stop_loss_pct"])

            current_price = get_current_price(symbol)
            if current_price is None:
                updated_trades.append(trade)
                continue

            change_pct = (current_price - entry_price) / entry_price * 100

            if change_pct >= tp_pct:
                place_market_sell(symbol, qty)
                pnl = (current_price - entry_price) * qty
                append_pnl(pnl)
                trade["status"] = "CLOSED_TP"
                send_telegram_message(
                    f"💰 TP закрыта\n{symbol}\nВход: {entry_price}\nВыход: {current_price}\nPnL: {pnl:.6f} USDC"
                )
                continue

            if change_pct <= -sl_pct:
                place_market_sell(symbol, qty)
                pnl = (current_price - entry_price) * qty
                append_pnl(pnl)
                trade["status"] = "CLOSED_SL"
                send_telegram_message(
                    f"❌ SL сработал\n{symbol}\nВход: {entry_price}\nВыход: {current_price}\nPnL: {pnl:.6f} USDC"
                )
                continue

            updated_trades.append(trade)

        except Exception as e:
            print("Ошибка обработки сделки:", e)
            updated_trades.append(trade)

    save_trades(updated_trades)

if __name__ == "__main__":
    print("🚀 Monitor started")
    while True:
        try:
            check_and_close_trades()
        except Exception as e:
            print("Monitor error:", e)
        time.sleep(30)
