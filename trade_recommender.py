import statistics
from utils import get_klines
from binance.client import Client

client = Client()

def recommend_trade(symbol: str, usdc_balance: float):
    """
    Выдаёт рекомендацию для сделки по заданной паре:
    - сколько USDC потратить
    - take profit % 
    - stop loss %
    """

    # Получаем последние цены (1h свечи за 48 периодов)
    klines = get_klines(symbol, interval=Client.KLINE_INTERVAL_1HOUR, limit=48)
    closes = [float(k[4]) for k in klines]

    if not closes:
        return None

    avg_price = statistics.mean(closes)
    std = statistics.stdev(closes) if len(closes) > 1 else 0
    volatility_pct = (std / avg_price) * 100 if avg_price > 0 else 0

    # Take profit и stop loss на основе волатильности
    take_profit_pct = round(min(max(volatility_pct * 1.2, 1.5), 6), 2)
    stop_loss_pct = round(min(max(volatility_pct * 0.8, 1.0), 4), 2)

    # Размер позиции — 5% баланса, минимум 5 USDC
    base_amount = usdc_balance * 0.05
    amount = round(max(5.0, base_amount), 2)

    return {
        "symbol": symbol,
        "amount": amount,
        "take_profit_pct": take_profit_pct,
        "stop_loss_pct": stop_loss_pct,
        "volatility_pct": round(volatility_pct, 2)
    }
