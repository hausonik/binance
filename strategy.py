from utils import get_klines
from binance.client import Client
import pandas as pd
import numpy as np

def calc_rsi(prices, period=14):
    delta = prices.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ma_up = up.rolling(period).mean()
    ma_down = down.rolling(period).mean()
    rs = ma_up / ma_down
    return 100 - (100 / (1 + rs))

def calc_ema(prices, period):
    return prices.ewm(span=period, adjust=False).mean()

def scan_signals():
    """
    Возвращает список сигналов по стратегии
    """
    signals = []
    # Список пар для сканирования
    PAIRS = ["BTCUSDC", "ETHUSDC", "SOLUSDC", "BNBUSDC", "ADAUSDC", "XRPUSDC"]

    for sym in PAIRS:
        try:
            klines = get_klines(sym, interval=Client.KLINE_INTERVAL_5MINUTE, limit=100)
            df = pd.DataFrame(klines, columns=[
                "open_time", "open", "high", "low", "close",
                "volume", "close_time", "quote_asset_volume",
                "trades", "taker_buy_base", "taker_buy_quote", "ignore"
            ])
            df["close"] = df["close"].astype(float)
            close = df["close"]

            # RSI сигнал
            rsi = calc_rsi(close)
            if rsi.iloc[-1] < 30:  # перепродано
                signals.append({"symbol": sym, "type": "RSI BUY"})
            elif rsi.iloc[-1] > 70:  # перекуплено
                signals.append({"symbol": sym, "type": "RSI SELL"})

            # EMA‑пересечение
            ema_short = calc_ema(close, 8)
            ema_long = calc_ema(close, 21)
            if ema_short.iloc[-1] > ema_long.iloc[-1]:
                signals.append({"symbol": sym, "type": "EMA CROSS BUY"})
            elif ema_short.iloc[-1] < ema_long.iloc[-1]:
                signals.append({"symbol": sym, "type": "EMA CROSS SELL"})

        except Exception as e:
            print("Ошибка сигналов:", e)
            continue

    return {"signals": signals}
