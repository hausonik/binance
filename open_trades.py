from binance.client import Client
import os
from dotenv import load_dotenv

load_dotenv()

client = Client(
    os.getenv("BINANCE_API_KEY"),
    os.getenv("BINANCE_API_SECRET")
)

def get_open_trades():
    """
    Возвращает список открытых ордеров.
    """
    try:
        orders = client.get_open_orders()
        return orders
    except Exception as e:
        return {"error": str(e)}
