"""
Flask API сервер для Binance Auto Trading Bot.
"""
from flask import Flask, jsonify, request
from balances import get_balances
from database import (
    get_open_trades, get_all_trades, get_pnl_history,
    export_trades_to_json, log_event
)
from strategy import scan_signals
from telegram_bot import send_telegram_message
from trader import place_trade_with_tp_sl, close_trade_manually, update_tp_sl
from trade_recommender import recommend_trade
from trading_mode import get_trading_mode, requires_confirmation, can_auto_trade
import os

app = Flask(__name__)

# === Балансы ===
@app.route("/balances")
def balances():
    return jsonify(get_balances())

# === Открытые сделки ===
@app.route("/open_trades")
def open_trades():
    trades = get_open_trades()
    return jsonify(trades)

# === Все сделки ===
@app.route("/all_trades")
def all_trades():
    limit = request.args.get("limit", type=int)
    trades = get_all_trades(limit=limit)
    return jsonify(trades)

# === Сигналы ===
@app.route("/scan_signals")
def scan_signals_api():
    results = scan_signals()
    return jsonify(results)

# === PnL по периодам ===
@app.route("/profit_calc")
def profit_calc():
    period = request.args.get("period", "all")
    from profit_calc import get_profit_by_period
    result = get_profit_by_period(period)
    return jsonify({"period": period, "pnl": result})

# === История PnL ===
@app.route("/pnl_history")
def pnl_history():
    try:
        period = request.args.get("period", "all")
        history = get_pnl_history(period)
        return jsonify(history)
    except Exception as e:
        log_event("ERROR", "app", f"Ошибка получения PnL истории: {str(e)}")
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
                log_event("WARNING", "app", f"Ошибка recommend_trade({pair}): {str(e)}")
                continue

        return jsonify({"recommendations": recs})
    except Exception as e:
        log_event("ERROR", "app", f"Ошибка recommend_all: {str(e)}")
        return jsonify({"error": str(e)})

# === Открытие сделки с TP/SL ===
@app.route("/open_trade")
def open_trade_api():
    """
    Открывает сделку и выставляет реальные ордера TP и SL.
    Проверяет режим торговли и риски.
    Пример:
    http://server:5000/open_trade?symbol=BTCUSDC&amount=5&tp=1.5&sl=1.0
    """
    symbol = request.args.get("symbol")
    try:
        amount = float(request.args.get("amount", "0"))
        tp = float(request.args.get("tp", "0"))
        sl = float(request.args.get("sl", "0"))
        volatility = float(request.args.get("volatility", "0"))
        skip_risk = request.args.get("skip_risk", "false").lower() == "true"
    except:
        return jsonify({"error": "invalid parameters"}), 400

    if not symbol or amount <= 0:
        return jsonify({"error": "missing or invalid parameters"}), 400

    # Проверка режима торговли
    if requires_confirmation():
        return jsonify({
            "error": "CONFIRM_REQUIRED",
            "message": "Требуется подтверждение. Режим: CONFIRM_ALL"
        }), 403

    try:
        result = place_trade_with_tp_sl(
            symbol.upper(), 
            amount, 
            tp, 
            sl,
            volatility_pct=volatility,
            skip_risk_check=skip_risk
        )
        
        # Если сделка прошла — отправляем уведомление в Telegram
        if result.get("message") == "BUY EXECUTED":
            send_telegram_message(
                f"🟢 Сделка открыта: {symbol}\n"
                f"Сумма: {amount} USDC\n"
                f"TP: {tp}%\n"
                f"SL: {sl}%"
            )
            log_event("INFO", "app", f"Сделка открыта через API: {symbol}, amount: {amount}")
        
        return jsonify(result)
    except Exception as e:
        log_event("ERROR", "app", f"Ошибка открытия сделки: {str(e)}")
        return jsonify({"error": str(e)}), 500

# === Закрытие позиции вручную ===
@app.route("/close_trade", methods=["POST"])
def close_trade_api():
    """Закрывает позицию вручную по trade_id."""
    data = request.get_json() or {}
    trade_id = data.get("trade_id") or request.args.get("trade_id", type=int)
    
    if not trade_id:
        return jsonify({"error": "trade_id required"}), 400
    
    try:
        result = close_trade_manually(trade_id)
        if result.get("status") == "ok":
            send_telegram_message(
                f"🔴 Позиция закрыта вручную\n"
                f"Trade ID: {trade_id}\n"
                f"PnL: {result.get('pnl', 0):.6f} USDC"
            )
        return jsonify(result)
    except Exception as e:
        log_event("ERROR", "app", f"Ошибка закрытия позиции: {str(e)}")
        return jsonify({"error": str(e)}), 500

# === Обновление TP/SL ===
@app.route("/update_tp_sl", methods=["POST"])
def update_tp_sl_api():
    """Обновляет TP/SL для открытой позиции."""
    data = request.get_json() or {}
    trade_id = data.get("trade_id") or request.args.get("trade_id", type=int)
    new_tp = data.get("tp_pct")
    new_sl = data.get("sl_pct")
    
    if not trade_id:
        return jsonify({"error": "trade_id required"}), 400
    
    try:
        result = update_tp_sl(trade_id, new_tp, new_sl)
        return jsonify(result)
    except Exception as e:
        log_event("ERROR", "app", f"Ошибка обновления TP/SL: {str(e)}")
        return jsonify({"error": str(e)}), 500

# === Режим торговли ===
@app.route("/trading_mode")
def trading_mode_api():
    """Возвращает текущий режим торговли."""
    mode = get_trading_mode()
    return jsonify({
        "mode": mode,
        "requires_confirmation": requires_confirmation(),
        "can_auto_trade": can_auto_trade()
    })

@app.route("/trading_mode", methods=["POST"])
def set_trading_mode_api():
    """Устанавливает режим торговли."""
    from trading_mode import set_trading_mode
    data = request.get_json() or {}
    mode = data.get("mode") or request.args.get("mode")
    
    if not mode:
        return jsonify({"error": "mode required"}), 400
    
    try:
        set_trading_mode(mode)
        log_event("INFO", "app", f"Режим торговли изменен: {mode}")
        return jsonify({"status": "ok", "mode": mode})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# === Риски ===
@app.route("/risk_summary")
def risk_summary_api():
    """Возвращает сводку по рискам."""
    try:
        from risk import get_risk_summary
        summary = get_risk_summary()
        return jsonify(summary)
    except Exception as e:
        log_event("ERROR", "app", f"Ошибка получения сводки рисков: {str(e)}")
        return jsonify({"error": str(e)}), 500

# === Экспорт для обратной совместимости ===
@app.route("/trades_export")
def trades_export_api():
    """Экспорт сделок в JSON формате (для GUI)."""
    trades = export_trades_to_json()
    return jsonify(trades)

# === Запуск ===
if __name__ == "__main__":
    log_event("INFO", "app", "Flask сервер запущен")
    send_telegram_message("🚀 Binance бот запущен на сервере и работает!")
    app.run(host="0.0.0.0", port=5000)
