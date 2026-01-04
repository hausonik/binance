from binance.client import Client
import os
from dotenv import load_dotenv
from notifier import send_telegram_message

# Загружаем .env
load_dotenv()

client = Client(
    os.getenv("BINANCE_API_KEY"),
    os.getenv("BINANCE_API_SECRET")
)

def get_balances():
    """
    Получает балансы аккаунта.
    """
    try:
        info = client.get_account()
        balances = {}
        for b in info['balances']:
            free = float(b['free'])
            locked = float(b['locked'])
            if free > 0 or locked > 0:
                balances[b['asset']] = {
                    "free": b['free'],
                    "locked": b['locked']
                }
        return balances
    except Exception as e:
        send_telegram_message(f"❌ Ошибка получения балансов: {e}")
        return {"error": str(e)}
