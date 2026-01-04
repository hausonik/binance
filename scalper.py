import time
from strategy import scan_signals
from trade_recommender import recommend_trade
from telegram_bot import send_trade_recommendation
from balances import get_balances

PAIRS = [
    "BTCUSDC", "ETHUSDC", "SOLUSDC", "BNBUSDC", "XRPUSDC", "ADAUSDC", "DOGEUSDC"
]

while True:
    print("🔁 Запуск скальпера...")

    try:
        balances = get_balances()
        usdc = float(balances.get("USDC", {}).get("free", 0))

        if usdc >= 5:
            for pair in PAIRS:
                rec = recommend_trade(pair, usdc)
                if rec:
                    print(f"📈 Рекомендация: {rec}")
                    send_trade_recommendation(rec)

    except Exception as e:
        print(f"❌ Ошибка в скальпере: {e}")

    time.sleep(60)  # ждем 60 секунд
