import json
from collections import deque
from datetime import datetime, timedelta

LOG_FILE = "trades_log.json"

def load_trades():
    with open(LOG_FILE, "r") as f:
        return json.load(f)

def filter_trades_by_period(trades, period):
    """
    Фильтрация сделок по периоду:
    - day: сегодня
    - week: текущая неделя
    - month: текущий месяц
    - year: текущий год
    - none: всё
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
        t_time = datetime.fromisoformat(t["timestamp"])
        if t_time >= since:
            filtered.append(t)
    return filtered

def calculate_profit(trades):
    """
    Реализованный PnL по FIFO
    """
    trades_by_symbol = {}
    for t in trades:
        sym = t["symbol"]
        trades_by_symbol.setdefault(sym, []).append(t)

    pnl_result = {}
    for sym, trs in trades_by_symbol.items():
        buy_queue = deque()
        realized_pnl = 0

        for t in trs:
            side = t["side"]
            price = t["price"]
            qty = t["quantity"]
            fee = t["fee"]

            if side == "BUY":
                buy_queue.append({"price": price, "qty": qty})
            elif side == "SELL":
                remaining = qty
                while remaining > 0 and buy_queue:
                    lot = buy_queue[0]
                    buy_price = lot["price"]
                    buy_qty = lot["qty"]

                    matched = min(remaining, buy_qty)
                    pnl = (price - buy_price) * matched
                    realized_pnl += pnl

                    lot["qty"] -= matched
                    remaining -= matched

                    if lot["qty"] == 0:
                        buy_queue.popleft()

        pnl_result[sym] = round(realized_pnl, 8)

    return pnl_result

def get_profit_by_period(period="all"):
    trades = load_trades()
    filtered = filter_trades_by_period(trades, period)
    return calculate_profit(filtered)
