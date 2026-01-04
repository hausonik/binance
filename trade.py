from binance.client import Client
import os

client = Client(os.getenv("BINANCE_API_KEY"),
                os.getenv("BINANCE_API_SECRET"))

def place_market_buy(symbol, qty):
    try:
        order = client.order_market_buy(symbol=symbol, quantity=qty)
        return {"result": "success", "order": order}
    except Exception as e:
        return {"result": "error", "msg": str(e)}
