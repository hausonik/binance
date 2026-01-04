import os
import json
from datetime import datetime
from dotenv import load_dotenv
from binance.client import Client

load_dotenv()

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")

client = Client(
    api_key=BINANCE_API_KEY,
    api_secret=BINANCE_API_SECRET
)

TRADES_LOG = "trades_log.json"

def _ensure_log_file():
    if not os.path.exists(TRADES_LOG):
        with open(TRADES_LOG, "w") as f:
            json.dump([], f)

def log_trade(entry: dict):
    _ensure_log_file()
    with open(TRADES_LOG, "r+") as f:
        data = json.load(f)
        data.append(entry)
        f.seek(0)
        json.dump(data, f, indent=2)

def get_symbol_info(symbol):
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
    MARKET BUY на сумму USDC
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
        return {"status": "error", "error": str(e)}

def place_trade_with_tp_sl(symbol: str, amount_usdc: float, tp_pct: float, sl_pct: float):
    """
    MARKET BUY + выставление ордеров TP и SL
    """
    result = place_market_buy(symbol, amount_usdc)
    if result.get("status") != "ok":
        return result

    qty = result["executed_qty"]
    avg_price = result["avg_price"]

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

        # Логируем сделку
        trade_entry = {
            "symbol": symbol,
            "side": "BUY",
            "avg_price": avg_price,
            "quantity": f"{qty:.8f}",
            "take_profit_pct": tp_pct,
            "stop_loss_pct": sl_pct,
            "tp_order_id": tp_order.get("orderId"),
            "sl_order_id": sl_order.get("orderId"),
            "tp_price": tp_price,
            "sl_stop": sl_stop,
            "sl_limit": sl_limit,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "OPEN_SL_TP"
        }

        log_trade(trade_entry)

        return {
            "message": "BUY with TP/SL placed",
            "symbol": symbol,
            "avg_price": avg_price,
            "qty": qty,
            "tp_price": tp_price,
            "sl_stop": sl_stop,
            "sl_limit": sl_limit
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}
