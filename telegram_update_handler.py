import os
import requests
import json
import time
from telegram_bot import send_telegram_message

from dotenv import load_dotenv
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_ID")
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

def handle_updates():
    offset = None
    while True:
        url = f"{BASE_URL}/getUpdates?timeout=30"
        if offset:
            url += f"&offset={offset+1}"
        res = requests.get(url).json()

        for update in res.get("result", []):
            update_id = update["update_id"]
            offset = update_id

            if "callback_query" in update:
                callback = update["callback_query"]
                handle_callback(callback)

        time.sleep(1)


def handle_callback(callback):
    data = callback.get("data", "")
    parts = data.split("|")

    action = parts[0]
    symbol = parts[1]

    if action == "trade_yes":
        try:
            amount = float(parts[2])
            tp_pct = float(parts[3])
            sl_pct = float(parts[4])
        except:
            send_telegram_message(f"❌ Ошибка в данных: {data}")
            return

        from trader import place_trade_confirmed

        result = place_trade_confirmed(symbol, amount, tp_pct, sl_pct)

        if result.get("message"):
            msg = (
                f"✅ Сделка ОТКРЫТА: {symbol}\n"
                f"Сумма: {amount} USDC\n"
                f"TP: {tp_pct}%\n"
                f"SL: {sl_pct}%\n"
                f"Цена входа: {result.get('price')}\n"
                f"Кол-во: {result.get('qty')}"
            )
        else:
            msg = f"❌ Не удалось открыть сделку: {result}"

        send_telegram_message(msg)

    elif action == "trade_no":
        send_telegram_message(f"❌ Отменена рекомендация для {symbol}")
