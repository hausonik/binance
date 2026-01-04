from dotenv import load_dotenv
from binance.client import Client

client = Client()

def load_env():
    """
    Загружает .env переменные.
    """
    load_dotenv()

def get_klines(symbol, interval="1h", limit=100):
    """
    Получает исторические свечи (OHLC) с Binance.

    :param symbol: торговая пара (например, BTCUSDC)
    :param interval: интервал свечей ("1h", "5m", и т.д.)
    :param limit: сколько свечей взять (макс 1000)
    :return: список свечей
    """
    return client.get_klines(symbol=symbol, interval=interval, limit=limit)
