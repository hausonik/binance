from flask import Flask, jsonify, request
from balances import get_balances
from open_trades import get_open_trades
from strategy import scan_signals
from telegram_bot import send_telegram_message
from profit_calc import get_profit_by_period

import os
import json

# Импорт функций трейдера
from trader import place_trade_with_tp_sl
from trade_recommender import recommend_trade

app = Flask(__name__)

# === Балансы ===
@app.route("/balances")
def balances():
    return jsonify(get_balances())

# === Открытые сделки ===
@app.route("/open_trades")
def open_trades():
    return jsonify(get_open_trades())

# === Сигналы ===
@app.route("/scan_signals")
def scan_signals_api():
    results = scan_signals()
    return jsonify(results)

# === PnL по периодам ===
@app.route("/profit_calc")
def profit_calc():
    period = request.args.get("period", "all")
    result = get_profit_by_period(period)
    return jsonify({"period": period, "pnl": result})

# === История PnL ===
@app.route("/pnl_history")
def pnl_history():
    try:
        if not os.path.exists("pnl_history.json"):
            return jsonify([])
        with open("pnl_history.json", "r") as f:
            return jsonify(json.load(f))
    except Exception as e:
        return jsonify({"error": str(e)})

# === Рекомендация для одной пары ===
@app.route("/recommend_trade")
def recommend_trade_api():
    symbol = request.args.get("symbol")
    try:
        balance = float(request.args.get("balance", "0"))
    except:
        balance = 0

    if not symbol:
        return jsonify({"error": "symbol required"}), 400

    rec = recommend_trade(symbol.upper(), balance)
    if not rec:
        return jsonify({"error": "not enough data"}), 400

    return jsonify(rec)

# === Все рекомендации ===
@app.route("/recommend_all")
def recommend_all_api():
    try:
        balances = get_balances()
        usdc_balance = float(balances.get("USDC", {}).get("free", 0))

        # Если мало USDC — пустой список
        if usdc_balance <= 0:
            return jsonify({"recommendations": []})

        # Список пар
        PAIRS = [
            "BTCUSDC", "ETHUSDC", "SOLUSDC",
            "BNBUSDC", "XRPUSDC", "ADAUSDC",
            "DOGEUSDC"
        ]

        recs = []
        for pair in PAIRS:
            try:
                rec = recommend_trade(pair, usdc_balance)
                if rec:
                    recs.append(rec)
            except Exception as e:
                print(f"Ошибка recommend_trade({pair}):", e)
                continue

        return jsonify({"recommendations": recs})
    except Exception as e:
        return jsonify({"error": str(e)})

# === Открытие сделки с TP/SL ===
@app.route("/open_trade")
def open_trade_api():
    """
    Открывает сделку и выставляет реальные ордера TP и SL:
    Пример:
    http://server:5000/open_trade?symbol=BTCUSDC&amount=5&tp=1.5&sl=1.0
    """
    symbol = request.args.get("symbol")
    try:
        amount = float(request.args.get("amount", "0"))
        tp = float(request.args.get("tp", "0"))
        sl = float(request.args.get("sl", "0"))
    except:
        return jsonify({"error": "invalid parameters"}), 400

    if not symbol or amount <= 0:
        return jsonify({"error": "missing or invalid parameters"}), 400

    try:
        result = place_trade_with_tp_sl(symbol.upper(), amount, tp, sl)
        # Если сделка прошла — отправляем уведомление в Telegram
        if result.get("message"):
            send_telegram_message(
                f"🟢 Сделка открыта: {symbol}\n"
                f"Сумма: {amount} USDC\n"
                f"TP: {tp}%\n"
                f"SL: {sl}%"
            )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# === Запуск ===
if __name__ == "__main__":
    send_telegram_message("🚀 Binance бот запущен на сервере и работает!")
    app.run(host="0.0.0.0", port=5000)
