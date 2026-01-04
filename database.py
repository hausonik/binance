"""
SQLite database для хранения состояния торговой системы.
Единственный источник истины для всех торговых данных.
"""
import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
import threading

DB_PATH = "trades.db"
_lock = threading.Lock()

@contextmanager
def get_db():
    """Thread-safe контекстный менеджер для работы с БД."""
    with _lock:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

def init_db():
    """Инициализация БД и создание таблиц."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Таблица сделок
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                avg_price REAL NOT NULL,
                quantity REAL NOT NULL,
                spent_usdc REAL,
                take_profit_pct REAL,
                stop_loss_pct REAL,
                tp_price REAL,
                sl_stop REAL,
                sl_limit REAL,
                tp_order_id INTEGER,
                sl_order_id INTEGER,
                status TEXT NOT NULL DEFAULT 'OPEN',
                created_at TEXT NOT NULL,
                closed_at TEXT,
                pnl REAL DEFAULT 0,
                close_price REAL
            )
        """)
        
        # Таблица ордеров
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id INTEGER,
                order_id INTEGER UNIQUE NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                type TEXT NOT NULL,
                quantity REAL NOT NULL,
                price REAL,
                stop_price REAL,
                status TEXT NOT NULL DEFAULT 'NEW',
                created_at TEXT NOT NULL,
                executed_at TEXT,
                FOREIGN KEY (trade_id) REFERENCES trades(id)
            )
        """)
        
        # Таблица снимков PnL
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pnl_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                pnl REAL NOT NULL,
                equity REAL,
                drawdown REAL,
                daily_pnl REAL
            )
        """)
        
        # Таблица событий (логи)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                level TEXT NOT NULL,
                module TEXT NOT NULL,
                message TEXT NOT NULL,
                data TEXT
            )
        """)
        
        # Индексы для производительности
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_created ON trades(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_trade_id ON orders(trade_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_order_id ON orders(order_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pnl_timestamp ON pnl_snapshots(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)")
        
        conn.commit()

# ========== TRADES ==========

def create_trade(trade_data: Dict[str, Any]) -> int:
    """Создает новую сделку в БД. Возвращает ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO trades (
                symbol, side, avg_price, quantity, spent_usdc,
                take_profit_pct, stop_loss_pct, tp_price, sl_stop, sl_limit,
                tp_order_id, sl_order_id, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade_data['symbol'],
            trade_data['side'],
            trade_data['avg_price'],
            trade_data['quantity'],
            trade_data.get('spent_usdc'),
            trade_data.get('take_profit_pct'),
            trade_data.get('stop_loss_pct'),
            trade_data.get('tp_price'),
            trade_data.get('sl_stop'),
            trade_data.get('sl_limit'),
            trade_data.get('tp_order_id'),
            trade_data.get('sl_order_id'),
            trade_data.get('status', 'OPEN'),
            datetime.utcnow().isoformat()
        ))
        return cursor.lastrowid

def update_trade_status(trade_id: int, status: str, close_price: Optional[float] = None, pnl: Optional[float] = None):
    """Обновляет статус сделки."""
    with get_db() as conn:
        cursor = conn.cursor()
        updates = ["status = ?"]
        params = [status]
        
        if close_price is not None:
            updates.append("close_price = ?")
            params.append(close_price)
        
        if pnl is not None:
            updates.append("pnl = ?")
            params.append(pnl)
        
        if status in ['CLOSED_TP', 'CLOSED_SL', 'CLOSED_MANUAL']:
            updates.append("closed_at = ?")
            params.append(datetime.utcnow().isoformat())
        
        params.append(trade_id)
        cursor.execute(f"UPDATE trades SET {', '.join(updates)} WHERE id = ?", params)

def get_open_trades() -> List[Dict[str, Any]]:
    """Возвращает все открытые сделки."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trades WHERE status IN ('OPEN', 'OPEN_SL_TP') ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]

def get_all_trades(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Возвращает все сделки."""
    with get_db() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM trades ORDER BY created_at DESC"
        if limit:
            query += f" LIMIT {limit}"
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]

def get_trade_by_id(trade_id: int) -> Optional[Dict[str, Any]]:
    """Возвращает сделку по ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trades WHERE id = ?", (trade_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

# ========== ORDERS ==========

def create_order(order_data: Dict[str, Any]) -> int:
    """Создает запись об ордере."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO orders (
                trade_id, order_id, symbol, side, type,
                quantity, price, stop_price, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            order_data.get('trade_id'),
            order_data['order_id'],
            order_data['symbol'],
            order_data['side'],
            order_data['type'],
            order_data['quantity'],
            order_data.get('price'),
            order_data.get('stop_price'),
            order_data.get('status', 'NEW'),
            datetime.utcnow().isoformat()
        ))
        return cursor.lastrowid

def update_order_status(order_id: int, status: str):
    """Обновляет статус ордера."""
    with get_db() as conn:
        cursor = conn.cursor()
        executed_at = datetime.utcnow().isoformat() if status == 'FILLED' else None
        cursor.execute("""
            UPDATE orders SET status = ?, executed_at = ? WHERE order_id = ?
        """, (status, executed_at, order_id))

def get_order_by_binance_id(binance_order_id: int) -> Optional[Dict[str, Any]]:
    """Находит ордер по Binance order_id."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE order_id = ?", (binance_order_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_orders_by_trade(trade_id: int) -> List[Dict[str, Any]]:
    """Возвращает все ордера для сделки."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE trade_id = ?", (trade_id,))
        return [dict(row) for row in cursor.fetchall()]

# ========== PNL SNAPSHOTS ==========

def add_pnl_snapshot(pnl: float, equity: Optional[float] = None, drawdown: Optional[float] = None, daily_pnl: Optional[float] = None):
    """Добавляет снимок PnL."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO pnl_snapshots (timestamp, pnl, equity, drawdown, daily_pnl)
            VALUES (?, ?, ?, ?, ?)
        """, (
            datetime.utcnow().isoformat(),
            pnl,
            equity,
            drawdown,
            daily_pnl
        ))

def get_pnl_history(period: str = "all") -> List[Dict[str, Any]]:
    """Возвращает историю PnL для графика."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        if period == "all":
            cursor.execute("SELECT timestamp, pnl FROM pnl_snapshots ORDER BY timestamp")
        else:
            # Фильтрация по периоду
            from datetime import timedelta
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
                since = now - timedelta(days=1)
            
            cursor.execute("""
                SELECT timestamp, pnl FROM pnl_snapshots 
                WHERE timestamp >= ? ORDER BY timestamp
            """, (since.isoformat(),))
        
        return [dict(row) for row in cursor.fetchall()]

# ========== EVENTS ==========

def log_event(level: str, module: str, message: str, data: Optional[Dict] = None):
    """Логирует событие в БД."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO events (timestamp, level, module, message, data)
            VALUES (?, ?, ?, ?, ?)
        """, (
            datetime.utcnow().isoformat(),
            level,
            module,
            message,
            json.dumps(data) if data else None
        ))

def get_recent_events(limit: int = 100) -> List[Dict[str, Any]]:
    """Возвращает последние события."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM events ORDER BY timestamp DESC LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

# ========== UTILITY ==========

def export_trades_to_json() -> List[Dict]:
    """Экспорт сделок в JSON формат (для обратной совместимости с GUI)."""
    trades = get_all_trades()
    result = []
    for trade in trades:
        result.append({
            "id": trade["id"],
            "symbol": trade["symbol"],
            "side": trade["side"],
            "price": trade["avg_price"],
            "quantity": trade["quantity"],
            "take_profit_pct": trade["take_profit_pct"],
            "stop_loss_pct": trade["stop_loss_pct"],
            "timestamp": trade["created_at"],
            "status": trade["status"]
        })
    return result

# Инициализация БД при импорте
init_db()

