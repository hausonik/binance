"""
Единственный модуль, который имеет право отправлять ордера в Binance.
Все торговые операции проходят через этот модуль.
"""
import os
from datetime import datetime
from dotenv import load_dotenv
from binance.client import Client
from database import create_trade, create_order, log_event
from risk import check_trade_risk

load_dotenv()

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")

client = Client(
    api_key=BINANCE_API_KEY,
    api_secret=BINANCE_API_SECRET
)

def get_symbol_info(symbol):
    """Получает информацию о символе с Binance."""
    return client.get_symbol_info(symbol)

def round_price(symbol, price):
    """
    Округляет цену в соответствии с PRICE_FILTER.tickSize
    """
    info = get_symbol_info(symbol)
    price_filter = next(f for f in info["filters"] if f["filterType"] == "PRICE_FILTER")
    tick_size = float(price_filter["tickSize"])
    precision = int(round(-1 * (tick_size).as_integer_ratio()[1]).bit_length() - 1)
    return round(price - (price % tick_size), precision)

def round_qty(symbol, qty):
    """
    Округляет количество в соответствии с LOT_SIZE.stepSize
    """
    info = get_symbol_info(symbol)
    lot = next(f for f in info["filters"] if f["filterType"] == "LOT_SIZE")
    step_size = float(lot["stepSize"])
    precision = int(round(-1 * (step_size).as_integer_ratio()[1]).bit_length() - 1)
    return round(qty - (qty % step_size), precision)

def place_market_buy(symbol: str, amount_usdc: float):
    """
    MARKET BUY на сумму USDC.
    Внутренняя функция, не вызывается напрямую извне.
    """
    try:
        order = client.order_market_buy(
            symbol=symbol,
            quoteOrderQty=round(float(amount_usdc), 2)
        )
        fills = order.get("fills", [])
        if not fills:
            return {"status": "error", "error": "No fills returned"}

        total_cost = sum(float(f["price"]) * float(f["qty"]) for f in fills)
        total_qty = sum(float(f["qty"]) for f in fills)
        avg_price = round(total_cost / total_qty, 8)

        return {
            "status": "ok",
            "symbol": symbol,
            "spent_usdc": amount_usdc,
            "avg_price": avg_price,
            "executed_qty": total_qty,
            "order_id": order.get("orderId")
        }

    except Exception as e:
        log_event("ERROR", "trader", f"Ошибка MARKET BUY {symbol}: {str(e)}")
        return {"status": "error", "error": str(e)}

def place_market_sell(symbol: str, quantity: float):
    """
    MARKET SELL указанного количества.
    Используется для закрытия позиций.
    """
    try:
        order = client.order_market_sell(
            symbol=symbol,
            quantity=f"{round_qty(symbol, quantity):.8f}"
        )
        
        fills = order.get("fills", [])
        if not fills:
            return {"status": "error", "error": "No fills returned"}
        
        total_cost = sum(float(f["price"]) * float(f["qty"]) for f in fills)
        total_qty = sum(float(f["qty"]) for f in fills)
        avg_price = round(total_cost / total_qty, 8)
        
        log_event("INFO", "trader", f"MARKET SELL выполнен: {symbol}, qty: {total_qty}, price: {avg_price}")
        
        return {
            "status": "ok",
            "symbol": symbol,
            "executed_qty": total_qty,
            "avg_price": avg_price,
            "order_id": order.get("orderId")
        }
    except Exception as e:
        log_event("ERROR", "trader", f"Ошибка MARKET SELL {symbol}: {str(e)}")
        return {"status": "error", "error": str(e)}

def place_trade_with_tp_sl(
    symbol: str, 
    amount_usdc: float, 
    tp_pct: float, 
    sl_pct: float,
    volatility_pct: float = 0.0,
    skip_risk_check: bool = False
):
    """
    MARKET BUY + выставление ордеров TP и SL.
    ЕДИНСТВЕННАЯ функция для открытия новых сделок.
    
    Args:
        symbol: Торговая пара
        amount_usdc: Сумма в USDC
        tp_pct: Take Profit в процентах
        sl_pct: Stop Loss в процентах
        volatility_pct: Волатильность для проверки риска
        skip_risk_check: Пропустить проверку риска (только для ручных сделок)
    
    Returns:
        dict с результатом операции
    """
    # Проверка риска (если не пропущена)
    if not skip_risk_check:
        risk_check = check_trade_risk(symbol, amount_usdc, sl_pct, volatility_pct)
        if not risk_check:
            log_event("WARNING", "trader", f"Риск отклонен: {symbol} - {risk_check.reason}")
            return {"status": "error", "error": risk_check.reason}
    
    # Выполняем покупку
    result = place_market_buy(symbol, amount_usdc)
    if result.get("status") != "ok":
        return result

    qty = result["executed_qty"]
    avg_price = result["avg_price"]
    buy_order_id = result.get("order_id")

    try:
        # Рассчитываем необработанные TP/SL
        raw_tp = avg_price * (1 + tp_pct/100)
        raw_sl_stop = avg_price * (1 - sl_pct/100)

        # Округляем в соответствии с tickSize
        tp_price = round_price(symbol, raw_tp)
        sl_stop = round_price(symbol, raw_sl_stop)

        # Для stop-limit цена limit чуть ниже stop
        sl_limit = round_price(symbol, sl_stop * 0.995)

        # --- TP LIMIT SELL ---
        tp_order = client.create_order(
            symbol=symbol,
            side="SELL",
            type="LIMIT",
            quantity=f"{round_qty(symbol, qty):.8f}",
            price=f"{tp_price:.8f}",
            timeInForce="GTC"
        )
        tp_order_id = tp_order.get("orderId")

        # --- SL STOP-LOSS LIMIT SELL ---
        sl_order = client.create_order(
            symbol=symbol,
            side="SELL",
            type="STOP_LOSS_LIMIT",
            quantity=f"{round_qty(symbol, qty):.8f}",
            price=f"{sl_limit:.8f}",
            stopPrice=f"{sl_stop:.8f}",
            timeInForce="GTC"
        )
        sl_order_id = sl_order.get("orderId")

        # Сохраняем в БД
        trade_id = create_trade({
            "symbol": symbol,
            "side": "BUY",
            "avg_price": avg_price,
            "quantity": qty,
            "spent_usdc": amount_usdc,
            "take_profit_pct": tp_pct,
            "stop_loss_pct": sl_pct,
            "tp_price": tp_price,
            "sl_stop": sl_stop,
            "sl_limit": sl_limit,
            "tp_order_id": tp_order_id,
            "sl_order_id": sl_order_id,
            "status": "OPEN_SL_TP"
        })

        # Сохраняем ордера в БД
        if buy_order_id:
            create_order({
                "trade_id": trade_id,
                "order_id": buy_order_id,
                "symbol": symbol,
                "side": "BUY",
                "type": "MARKET",
                "quantity": qty,
                "status": "FILLED"
            })
        
        create_order({
            "trade_id": trade_id,
            "order_id": tp_order_id,
            "symbol": symbol,
            "side": "SELL",
            "type": "LIMIT",
            "quantity": qty,
            "price": tp_price,
            "status": "NEW"
        })
        
        create_order({
            "trade_id": trade_id,
            "order_id": sl_order_id,
            "symbol": symbol,
            "side": "SELL",
            "type": "STOP_LOSS_LIMIT",
            "quantity": qty,
            "price": sl_limit,
            "stop_price": sl_stop,
            "status": "NEW"
        })

        log_event("INFO", "trader", f"Сделка открыта: {symbol}, trade_id: {trade_id}, amount: {amount_usdc} USDC")

        return {
            "message": "BUY EXECUTED",
            "trade_id": trade_id,
            "symbol": symbol,
            "avg_price": avg_price,
            "qty": qty,
            "tp_price": tp_price,
            "sl_stop": sl_stop,
            "sl_limit": sl_limit
        }

    except Exception as e:
        log_event("ERROR", "trader", f"Ошибка при выставлении TP/SL для {symbol}: {str(e)}")
        return {"status": "error", "error": str(e)}

def close_trade_manually(trade_id: int):
    """
    Ручное закрытие позиции по trade_id.
    Отменяет TP/SL ордера и выполняет market sell.
    """
    from database import get_trade_by_id, update_trade_status, get_orders_by_trade
    
    trade = get_trade_by_id(trade_id)
    if not trade:
        return {"status": "error", "error": "Trade not found"}
    
    if trade["status"] not in ["OPEN", "OPEN_SL_TP"]:
        return {"status": "error", "error": f"Trade already closed: {trade['status']}"}
    
    symbol = trade["symbol"]
    quantity = float(trade["quantity"])
    
    try:
        # Отменяем TP/SL ордера
        orders = get_orders_by_trade(trade_id)
        for order in orders:
            if order["status"] == "NEW" and order["order_id"]:
                try:
                    client.cancel_order(symbol=symbol, orderId=order["order_id"])
                    from database import update_order_status
                    update_order_status(order["order_id"], "CANCELLED")
                except Exception as e:
                    log_event("WARNING", "trader", f"Не удалось отменить ордер {order['order_id']}: {str(e)}")
        
        # Выполняем market sell
        sell_result = place_market_sell(symbol, quantity)
        if sell_result.get("status") != "ok":
            return sell_result
        
        # Рассчитываем PnL
        entry_price = float(trade["avg_price"])
        exit_price = sell_result["avg_price"]
        pnl = (exit_price - entry_price) * quantity
        
        # Обновляем статус в БД
        update_trade_status(trade_id, "CLOSED_MANUAL", exit_price, pnl)
        
        log_event("INFO", "trader", f"Позиция закрыта вручную: {symbol}, trade_id: {trade_id}, PnL: {pnl:.6f}")
        
        return {
            "status": "ok",
            "message": "Position closed",
            "trade_id": trade_id,
            "pnl": pnl,
            "exit_price": exit_price
        }
        
    except Exception as e:
        log_event("ERROR", "trader", f"Ошибка ручного закрытия trade_id {trade_id}: {str(e)}")
        return {"status": "error", "error": str(e)}

def update_tp_sl(trade_id: int, new_tp_pct: float = None, new_sl_pct: float = None):
    """
    Обновляет TP/SL для открытой позиции.
    Отменяет старые ордера и выставляет новые.
    """
    from database import get_trade_by_id, get_orders_by_trade, update_trade_status
    
    trade = get_trade_by_id(trade_id)
    if not trade:
        return {"status": "error", "error": "Trade not found"}
    
    if trade["status"] not in ["OPEN", "OPEN_SL_TP"]:
        return {"status": "error", "error": f"Cannot update TP/SL for closed trade"}
    
    symbol = trade["symbol"]
    quantity = float(trade["quantity"])
    avg_price = float(trade["avg_price"])
    
    # Используем новые значения или старые
    tp_pct = new_tp_pct if new_tp_pct is not None else trade["take_profit_pct"]
    sl_pct = new_sl_pct if new_sl_pct is not None else trade["stop_loss_pct"]
    
    try:
        # Отменяем старые TP/SL ордера
        orders = get_orders_by_trade(trade_id)
        for order in orders:
            if order["type"] in ["LIMIT", "STOP_LOSS_LIMIT"] and order["status"] == "NEW":
                try:
                    client.cancel_order(symbol=symbol, orderId=order["order_id"])
                    from database import update_order_status
                    update_order_status(order["order_id"], "CANCELLED")
                except Exception as e:
                    log_event("WARNING", "trader", f"Не удалось отменить ордер {order['order_id']}: {str(e)}")
        
        # Рассчитываем новые цены
        raw_tp = avg_price * (1 + tp_pct/100)
        raw_sl_stop = avg_price * (1 - sl_pct/100)
        tp_price = round_price(symbol, raw_tp)
        sl_stop = round_price(symbol, raw_sl_stop)
        sl_limit = round_price(symbol, sl_stop * 0.995)
        
        # Выставляем новые ордера
        tp_order = client.create_order(
            symbol=symbol,
            side="SELL",
            type="LIMIT",
            quantity=f"{round_qty(symbol, quantity):.8f}",
            price=f"{tp_price:.8f}",
            timeInForce="GTC"
        )
        
        sl_order = client.create_order(
            symbol=symbol,
            side="SELL",
            type="STOP_LOSS_LIMIT",
            quantity=f"{round_qty(symbol, quantity):.8f}",
            price=f"{sl_limit:.8f}",
            stopPrice=f"{sl_stop:.8f}",
            timeInForce="GTC"
        )
        
        # Обновляем в БД
        from database import get_db
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE trades SET 
                    take_profit_pct = ?,
                    stop_loss_pct = ?,
                    tp_price = ?,
                    sl_stop = ?,
                    sl_limit = ?,
                    tp_order_id = ?,
                    sl_order_id = ?
                WHERE id = ?
            """, (tp_pct, sl_pct, tp_price, sl_stop, sl_limit, 
                  tp_order.get("orderId"), sl_order.get("orderId"), trade_id))
        
        # Сохраняем новые ордера
        create_order({
            "trade_id": trade_id,
            "order_id": tp_order.get("orderId"),
            "symbol": symbol,
            "side": "SELL",
            "type": "LIMIT",
            "quantity": quantity,
            "price": tp_price,
            "status": "NEW"
        })
        
        create_order({
            "trade_id": trade_id,
            "order_id": sl_order.get("orderId"),
            "symbol": symbol,
            "side": "SELL",
            "type": "STOP_LOSS_LIMIT",
            "quantity": quantity,
            "price": sl_limit,
            "stop_price": sl_stop,
            "status": "NEW"
        })
        
        log_event("INFO", "trader", f"TP/SL обновлены: trade_id {trade_id}, TP: {tp_pct}%, SL: {sl_pct}%")
        
        return {
            "status": "ok",
            "message": "TP/SL updated",
            "trade_id": trade_id,
            "tp_price": tp_price,
            "sl_stop": sl_stop
        }
        
    except Exception as e:
        log_event("ERROR", "trader", f"Ошибка обновления TP/SL для trade_id {trade_id}: {str(e)}")
        return {"status": "error", "error": str(e)}
