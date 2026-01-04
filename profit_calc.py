"""
Расчет прибыли по периодам.
Работает с БД вместо JSON.
"""
from datetime import datetime, timedelta
from database import get_all_trades

def filter_trades_by_period(trades, period):
    """
    Фильтрация сделок по периоду:
    - day: сегодня
    - week: текущая неделя
    - month: текущий месяц
    - year: текущий год
    - all: всё
    """
    now = datetime.utcnow()

    if period == "day":
        since = now - timedelta(days=1)
    elif period == "week":
        since = now - timedelta(weeks=1)
    elif period == "month":
        since = now.replace(day=1)
    elif period == "year":
        since = now.replace(month=1, day=1)
    else:
        return trades

    filtered = []
    for t in trades:
        try:
            t_time = datetime.fromisoformat(t["created_at"].replace("Z", "+00:00"))
            if t_time >= since:
                filtered.append(t)
        except:
            continue
    return filtered

def calculate_profit(trades):
    """
    Реализованный PnL по закрытым сделкам.
    Использует поле pnl из БД для закрытых сделок.
    """
    pnl_result = {}
    total_pnl = 0.0
    
    for t in trades:
        # Учитываем только закрытые сделки с рассчитанным PnL
        if t.get("status") in ["CLOSED_TP", "CLOSED_SL", "CLOSED_MANUAL"]:
            symbol = t["symbol"]
            pnl = float(t.get("pnl", 0))
            
            if symbol not in pnl_result:
                pnl_result[symbol] = 0.0
            
            pnl_result[symbol] += pnl
            total_pnl += pnl
    
    # Округляем результаты
    for symbol in pnl_result:
        pnl_result[symbol] = round(pnl_result[symbol], 8)
    
    # Добавляем общий PnL
    pnl_result["TOTAL"] = round(total_pnl, 8)
    
    return pnl_result

def get_profit_by_period(period="all"):
    """
    Возвращает прибыль по периодам.
    Работает с БД.
    """
    trades = get_all_trades()
    filtered = filter_trades_by_period(trades, period)
    return calculate_profit(filtered)
