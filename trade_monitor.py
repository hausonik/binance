from binance.client import Client
import json

client = Client()

def monitor_open_orders():
    orders = client.get_open_orders()
    for o in orders:
        # получить цену и TP/SL из trades_log
        pass
