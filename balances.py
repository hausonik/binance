from binance.client import Client
import os

client = Client(os.getenv("BINANCE_API_KEY"),
                os.getenv("BINANCE_API_SECRET"))

def get_balances():
    info = client.get_account()
    balances = {}
    for b in info['balances']:
        if float(b['free']) > 0 or float(b['locked']) > 0:
            balances[b['asset']] = {
                "free": b['free'],
                "locked": b['locked']
            }
    return balances
