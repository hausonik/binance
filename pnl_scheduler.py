import json
from datetime import datetime
from profit_calc import get_profit_by_period

PNL_FILE = "pnl_history.json"

def add_daily_pnl():
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    pnl_all = get_profit_by_period("all")
    entry = {"date": date_str, "pnl": pnl_all}

    # Читаем старую историю
    try:
        with open(PNL_FILE, "r") as f:
            data = json.load(f)
    except:
        data = []

    # Записываем новую запись
    data.append(entry)
    with open(PNL_FILE, "w") as f:
        json.dump(data, f, indent=2)
