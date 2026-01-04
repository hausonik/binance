"""
Автоматическое сканирование и открытие сделок.
Учитывает режим торговли и проверяет риски.
"""
import time
from trade_recommender import recommend_trade
from telegram_bot import send_trade_recommendation
from balances import get_balances
from trading_mode import can_auto_trade, is_auto_gated
from trader import place_trade_with_tp_sl
from database import log_event

PAIRS = [
    "BTCUSDC", "ETHUSDC", "SOLUSDC", "BNBUSDC", "XRPUSDC", "ADAUSDC", "DOGEUSDC"
]

def scalper_loop():
    """Основной цикл скальпера."""
    while True:
        print("🔁 Запуск скальпера...")

        try:
            # Проверяем режим торговли
            if not can_auto_trade():
                log_event("INFO", "scalper", "Автоторговля отключена, пропуск цикла")
                time.sleep(60)
                continue

            balances = get_balances()
            if "error" in balances:
                log_event("WARNING", "scalper", "Ошибка получения балансов")
                time.sleep(60)
                continue

            usdc = float(balances.get("USDC", {}).get("free", 0))

            if usdc < 5:
                log_event("INFO", "scalper", f"Недостаточно USDC: {usdc}")
                time.sleep(60)
                continue

            for pair in PAIRS:
                try:
                    rec = recommend_trade(pair, usdc)
                    if not rec:
                        continue

                    print(f"📈 Рекомендация: {rec}")

                    # Если режим AUTO_GATED - проверяем риски и открываем автоматически
                    if is_auto_gated():
                        # Открываем сделку с проверкой риска
                        result = place_trade_with_tp_sl(
                            rec["symbol"],
                            rec["amount"],
                            rec["take_profit_pct"],
                            rec["stop_loss_pct"],
                            volatility_pct=rec.get("volatility_pct", 0),
                            skip_risk_check=False
                        )

                        if result.get("message") == "BUY EXECUTED":
                            log_event("INFO", "scalper", 
                                f"Автосделка открыта: {rec['symbol']}, amount: {rec['amount']}")
                        else:
                            log_event("WARNING", "scalper",
                                f"Не удалось открыть автосделку {rec['symbol']}: {result.get('error')}")
                    else:
                        # Режим AUTO_ALL - отправляем в Telegram для подтверждения
                        send_trade_recommendation(rec)

                except Exception as e:
                    log_event("ERROR", "scalper", f"Ошибка обработки пары {pair}: {str(e)}")
                    continue

        except Exception as e:
            log_event("ERROR", "scalper", f"Критическая ошибка в скальпере: {str(e)}")

        time.sleep(60)  # ждем 60 секунд

if __name__ == "__main__":
    print("🚀 Scalper started")
    scalper_loop()
