"""
Модуль управления рисками.
Проверяет все торговые операции перед исполнением.
"""
from database import get_open_trades, get_all_trades, log_event
from balances import get_balances
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

# Константы риска
MAX_RISK_PER_TRADE = 0.5  # Максимальный риск на сделку (% от капитала)
MAX_DAILY_LOSS = 2.0  # Максимальный дневной убыток (%)
MAX_DRAWDOWN = 10.0  # Максимальный глобальный drawdown (%)
MAX_CORRELATED_POSITIONS = 2  # Максимальное количество позиций по одной паре
MIN_VOLATILITY = 0.5  # Минимальная волатильность для торговли (%)
MAX_VOLATILITY = 8.0  # Максимальная волатильность для торговли (%)

class RiskCheckResult:
    """Результат проверки риска."""
    def __init__(self, allowed: bool, reason: str = ""):
        self.allowed = allowed
        self.reason = reason
    
    def __bool__(self):
        return self.allowed

def check_trade_risk(symbol: str, amount_usdc: float, sl_pct: float, volatility_pct: float) -> RiskCheckResult:
    """
    Проверяет риск сделки перед открытием.
    Возвращает RiskCheckResult с разрешением или запретом.
    """
    try:
        # 1. Проверка волатильности
        if volatility_pct < MIN_VOLATILITY:
            return RiskCheckResult(False, f"Волатильность слишком низкая: {volatility_pct:.2f}%")
        if volatility_pct > MAX_VOLATILITY:
            return RiskCheckResult(False, f"Волатильность слишком высокая: {volatility_pct:.2f}%")
        
        # 2. Получаем баланс
        balances = get_balances()
        if "error" in balances:
            return RiskCheckResult(False, "Ошибка получения баланса")
        
        usdc_balance = float(balances.get("USDC", {}).get("free", 0))
        if usdc_balance <= 0:
            return RiskCheckResult(False, "Недостаточно USDC баланса")
        
        # 3. Проверка риска на сделку (% от капитала)
        risk_amount = amount_usdc * (sl_pct / 100)
        risk_pct = (risk_amount / usdc_balance) * 100 if usdc_balance > 0 else 0
        
        if risk_pct > MAX_RISK_PER_TRADE:
            return RiskCheckResult(
                False, 
                f"Риск на сделку {risk_pct:.2f}% превышает лимит {MAX_RISK_PER_TRADE}%"
            )
        
        # 4. Проверка дневного убытка
        daily_loss = get_daily_loss_pct()
        if daily_loss >= MAX_DAILY_LOSS:
            return RiskCheckResult(
                False,
                f"Дневной убыток {daily_loss:.2f}% достиг лимита {MAX_DAILY_LOSS}%"
            )
        
        # 5. Проверка глобального drawdown
        drawdown = get_current_drawdown()
        if drawdown >= MAX_DRAWDOWN:
            return RiskCheckResult(
                False,
                f"Глобальный drawdown {drawdown:.2f}% достиг лимита {MAX_DRAWDOWN}%"
            )
        
        # 6. Проверка количества позиций по паре
        open_trades = get_open_trades()
        same_symbol_count = sum(1 for t in open_trades if t["symbol"] == symbol)
        if same_symbol_count >= MAX_CORRELATED_POSITIONS:
            return RiskCheckResult(
                False,
                f"Уже открыто {same_symbol_count} позиций по {symbol} (лимит: {MAX_CORRELATED_POSITIONS})"
            )
        
        # 7. Проверка общего количества открытых позиций
        total_positions = len(open_trades)
        if total_positions >= 10:  # Максимум 10 позиций одновременно
            return RiskCheckResult(False, f"Слишком много открытых позиций: {total_positions}")
        
        # Все проверки пройдены
        log_event("INFO", "risk", f"Риск одобрен: {symbol}, сумма: {amount_usdc}, риск: {risk_pct:.2f}%")
        return RiskCheckResult(True, "OK")
        
    except Exception as e:
        log_event("ERROR", "risk", f"Ошибка проверки риска: {str(e)}")
        return RiskCheckResult(False, f"Ошибка проверки риска: {str(e)}")

def get_daily_loss_pct() -> float:
    """Вычисляет дневной убыток в процентах от капитала."""
    try:
        balances = get_balances()
        if "error" in balances:
            return 0.0
        
        usdc_balance = float(balances.get("USDC", {}).get("free", 0))
        if usdc_balance <= 0:
            return 0.0
        
        # Получаем все сделки за сегодня
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        all_trades = get_all_trades()
        
        daily_pnl = 0.0
        for trade in all_trades:
            trade_time = datetime.fromisoformat(trade["created_at"].replace("Z", "+00:00"))
            if trade_time >= today and trade.get("pnl"):
                daily_pnl += float(trade["pnl"])
        
        # Предполагаем начальный капитал (можно улучшить, храня в БД)
        # Для простоты считаем от текущего баланса
        if usdc_balance > 0:
            return abs(min(0, daily_pnl)) / usdc_balance * 100
        
        return 0.0
    except Exception as e:
        log_event("ERROR", "risk", f"Ошибка расчета дневного убытка: {str(e)}")
        return 0.0

def get_current_drawdown() -> float:
    """Вычисляет текущий глобальный drawdown."""
    try:
        from database import get_pnl_history
        
        # Получаем историю PnL
        pnl_history = get_pnl_history("all")
        if not pnl_history:
            return 0.0
        
        # Находим максимум equity
        equity_values = [float(h["pnl"]) for h in pnl_history if h.get("equity")]
        if not equity_values:
            return 0.0
        
        max_equity = max(equity_values)
        current_equity = equity_values[-1] if equity_values else 0
        
        if max_equity <= 0:
            return 0.0
        
        drawdown = ((max_equity - current_equity) / max_equity) * 100
        return max(0, drawdown)
        
    except Exception as e:
        log_event("ERROR", "risk", f"Ошибка расчета drawdown: {str(e)}")
        return 0.0

def get_risk_summary() -> Dict:
    """Возвращает сводку по рискам."""
    return {
        "daily_loss_pct": get_daily_loss_pct(),
        "max_daily_loss": MAX_DAILY_LOSS,
        "drawdown_pct": get_current_drawdown(),
        "max_drawdown": MAX_DRAWDOWN,
        "open_positions": len(get_open_trades()),
        "max_risk_per_trade": MAX_RISK_PER_TRADE
    }

