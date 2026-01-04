import os
import requests
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_ID = os.getenv("TELEGRAM_ID")
API_BASE_URL = os.getenv("API_BASE_URL", "")
ENABLE_ALERTS = os.getenv("ENABLE_TELEGRAM_ALERTS", "True").lower() == "true"

def send_telegram_message(text: str, reply_markup=None):
    """
    Отправляет сообщение в Telegram.
    Если передан reply_markup (кнопки), прикрепляет их.
    """
    if not TELEGRAM_TOKEN or not TELEGRAM_ID:
        print("⚠️ TELEGRAM_TOKEN или TELEGRAM_ID не заданы")
        return

    if not ENABLE_ALERTS:
        print("🔕 Уведомления в Telegram отключены (ENABLE_TELEGRAM_ALERTS=False).")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        requests.post(url, json=payload)
    except Exception as e:
        print("Ошибка Telegram:", e)


def send_trade_recommendation(rec: dict):
    """
    Отправляет в Telegram интерактивное предложение сделки
    """
    symbol = rec["symbol"]
    amount = rec["amount"]
    tp = rec["take_profit_pct"]
    sl = rec["stop_loss_pct"]
    vol = rec["volatility_pct"]

    text = (
        f"📊 *Торговое предложение*\n\n"
        f"Пара: *{symbol}*\n"
        f"USDC сумма: *{amount}*\n"
        f"📈 Take Profit: *{tp}%*\n"
        f"📉 Stop Loss: *{sl}%*\n"
        f"📊 Волатильность: *{vol}%*\n\n"
        "Подтвердить открытие сделки?"
    )

    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "✅ Да", "callback_data": f"trade_yes|{symbol}|{amount}|{tp}|{sl}"},
                {"text": "❌ Нет", "callback_data": f"trade_no|{symbol}"}
            ]
        ]
    }

    send_telegram_message(text, reply_markup)
