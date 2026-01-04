from binance.client import Client
import os

client = Client(os.getenv("BINANCE_API_KEY"),
                os.getenv("BINANCE_API_SECRET"))

def get_open_trades():
    orders = client.get_open_orders()
    return orders
