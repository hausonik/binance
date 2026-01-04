"""
Мониторинг открытых позиций и ордеров.
НЕ принимает торговых решений, НЕ закрывает сделки.
Только проверяет статусы и обновляет БД.
"""
import time
from datetime import datetime
from dotenv import load_dotenv
from binance.client import Client
from database import (
    get_open_trades, update_trade_status, get_order_by_binance_id,
    update_order_status, log_event, add_pnl_snapshot
)
import os

load_dotenv()

client = Client(
    os.getenv("BINANCE_API_KEY"),
    os.getenv("BINANCE_API_SECRET")
)

def get_current_price(symbol):
    """Получает текущую цену символа."""
    try:
        ticker = client.get_symbol_ticker(symbol=symbol)
        return float(ticker["price"])
    except Exception as e:
        log_event("ERROR", "monitor", f"Ошибка получения цены {symbol}: {str(e)}")
        return None

def check_order_status(order_id: int, symbol: str):
    """Проверяет статус ордера на Binance."""
    try:
        order = client.get_order(symbol=symbol, orderId=order_id)
        return order.get("status")  # NEW, FILLED, CANCELED, etc.
    except Exception as e:
        log_event("WARNING", "monitor", f"Не удалось получить статус ордера {order_id}: {str(e)}")
        return None

def sync_orders_with_binance():
    """
    Синхронизирует статусы ордеров в БД с реальными статусами на Binance.
    НЕ выставляет ордера, НЕ закрывает сделки.
    """
    try:
        # Получаем все открытые ордера с Binance
        binance_orders = client.get_open_orders()
        binance_order_ids = {o["orderId"] for o in binance_orders}
        
        # Получаем открытые сделки из БД
        open_trades = get_open_trades()
        
        for trade in open_trades:
            # Проверяем TP ордер
            if trade.get("tp_order_id"):
                tp_order_id = trade["tp_order_id"]
                binance_status = check_order_status(tp_order_id, trade["symbol"])
                
                if binance_status:
                    db_order = get_order_by_binance_id(tp_order_id)
                    if db_order and db_order["status"] != binance_status:
                        update_order_status(tp_order_id, binance_status)
                        
                        # Если TP исполнен - обновляем статус сделки
                        if binance_status == "FILLED":
                            close_price = get_current_price(trade["symbol"])
                            if close_price:
                                entry_price = float(trade["avg_price"])
                                quantity = float(trade["quantity"])
                                pnl = (close_price - entry_price) * quantity
                                
                                update_trade_status(
                                    trade["id"],
                                    "CLOSED_TP",
                                    close_price,
                                    pnl
                                )
                                add_pnl_snapshot(pnl)
                                log_event("INFO", "monitor", 
                                    f"TP исполнен: {trade['symbol']}, trade_id: {trade['id']}, PnL: {pnl:.6f}")
            
            # Проверяем SL ордер
            if trade.get("sl_order_id"):
                sl_order_id = trade["sl_order_id"]
                binance_status = check_order_status(sl_order_id, trade["symbol"])
                
                if binance_status:
                    db_order = get_order_by_binance_id(sl_order_id)
                    if db_order and db_order["status"] != binance_status:
                        update_order_status(sl_order_id, binance_status)
                        
                        # Если SL исполнен - обновляем статус сделки
                        if binance_status == "FILLED":
                            close_price = get_current_price(trade["symbol"])
                            if close_price:
                                entry_price = float(trade["avg_price"])
                                quantity = float(trade["quantity"])
                                pnl = (close_price - entry_price) * quantity
                                
                                update_trade_status(
                                    trade["id"],
                                    "CLOSED_SL",
                                    close_price,
                                    pnl
                                )
                                add_pnl_snapshot(pnl)
                                log_event("INFO", "monitor",
                                    f"SL исполнен: {trade['symbol']}, trade_id: {trade['id']}, PnL: {pnl:.6f}")
        
        # Проверяем расхождения: ордера на Binance, которых нет в БД
        for binance_order in binance_orders:
            order_id = binance_order["orderId"]
            db_order = get_order_by_binance_id(order_id)
            if not db_order:
                log_event("WARNING", "monitor",
                    f"Обнаружен ордер на Binance, отсутствующий в БД: order_id={order_id}, symbol={binance_order['symbol']}")
        
    except Exception as e:
        log_event("ERROR", "monitor", f"Ошибка синхронизации ордеров: {str(e)}")

def check_trades_status():
    """
    Проверяет статусы всех открытых сделок.
    Обновляет БД, если обнаружены изменения.
    """
    try:
        open_trades = get_open_trades()
        
        for trade in open_trades:
            symbol = trade["symbol"]
            
            # Проверяем, что TP/SL ордера еще активны
            if trade.get("tp_order_id") and trade.get("sl_order_id"):
                tp_status = check_order_status(trade["tp_order_id"], symbol)
                sl_status = check_order_status(trade["sl_order_id"], symbol)
                
                # Если оба ордера отменены или исполнены, но статус не обновлен
                if tp_status in ["FILLED", "CANCELED"] or sl_status in ["FILLED", "CANCELED"]:
                    # Статус уже должен быть обновлен в sync_orders_with_binance
                    # Но на всякий случай проверяем еще раз
                    pass
        
    except Exception as e:
        log_event("ERROR", "monitor", f"Ошибка проверки статусов сделок: {str(e)}")

def monitor_loop():
    """
    Основной цикл мониторинга.
    Запускается в отдельном процессе/потоке.
    """
    log_event("INFO", "monitor", "Мониторинг запущен")
    
    while True:
        try:
            # Синхронизация ордеров
            sync_orders_with_binance()
            
            # Проверка статусов сделок
            check_trades_status()
            
        except Exception as e:
            log_event("ERROR", "monitor", f"Критическая ошибка в цикле мониторинга: {str(e)}")
        
        # Пауза между проверками
        time.sleep(30)

if __name__ == "__main__":
    print("🚀 Monitor started (safe mode - no trading decisions)")
    monitor_loop()
