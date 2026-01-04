from binance.client import Client
import pandas as pd
import ta
import os

client = Client(os.getenv("BINANCE_API_KEY"),
                os.getenv("BINANCE_API_SECRET"))

def get_klines(symbol, interval="1h", limit=100):
    klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
    df = pd.DataFrame(klines, columns=[
        'timestamp','open','high','low','close','volume',
        'close_time','quote_asset_volume','trades',
        'taker_buy_base','taker_buy_quote','ignore'
    ])
    df['close'] = pd.to_numeric(df['close'])
    return df

def check_signal(symbol):
    df = get_klines(symbol)
    df['rsi'] = ta.momentum.RSIIndicator(df['close'],window=14).rsi()
    df['ma7'] = df['close'].rolling(7).mean()
    df['ma25'] = df['close'].rolling(25).mean()
    if df['ma7'].iloc[-1] > df['ma25'].iloc[-1] and df['rsi'].iloc[-1] < 40:
        return True
    return False

def scan_signals():
    symbols = ["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","BNBUSDT"]
    found = []
    for s in symbols:
        signal = check_signal(s)
        if signal:
            found.append(s)
    return {"signals": found}
