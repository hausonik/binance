"""
Управление режимами торговли.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Режимы торговли
CONFIRM_ALL = "CONFIRM_ALL"  # Все сделки требуют подтверждения
AUTO_GATED = "AUTO_GATED"    # Автосделки с проверкой риска (по умолчанию)
AUTO_ALL = "AUTO_ALL"        # Полностью автоматические сделки (выключено)

def get_trading_mode() -> str:
    """Возвращает текущий режим торговли из .env или по умолчанию AUTO_GATED."""
    mode = os.getenv("TRADING_MODE", AUTO_GATED).upper()
    if mode not in [CONFIRM_ALL, AUTO_GATED, AUTO_ALL]:
        return AUTO_GATED
    return mode

def set_trading_mode(mode: str):
    """Устанавливает режим торговли (сохраняется в .env)."""
    if mode not in [CONFIRM_ALL, AUTO_GATED, AUTO_ALL]:
        raise ValueError(f"Invalid trading mode: {mode}")
    
    # Читаем .env
    env_path = ".env"
    if not os.path.exists(env_path):
        with open(env_path, "w") as f:
            f.write(f"TRADING_MODE={mode}\n")
        return
    
    # Обновляем или добавляем TRADING_MODE
    lines = []
    found = False
    with open(env_path, "r") as f:
        for line in f:
            if line.startswith("TRADING_MODE="):
                lines.append(f"TRADING_MODE={mode}\n")
                found = True
            else:
                lines.append(line)
    
    if not found:
        lines.append(f"TRADING_MODE={mode}\n")
    
    with open(env_path, "w") as f:
        f.writelines(lines)

def can_auto_trade() -> bool:
    """Проверяет, разрешены ли автоматические сделки."""
    mode = get_trading_mode()
    return mode in [AUTO_GATED, AUTO_ALL]

def requires_confirmation() -> bool:
    """Проверяет, требуется ли подтверждение для сделок."""
    return get_trading_mode() == CONFIRM_ALL

def is_auto_gated() -> bool:
    """Проверяет, включен ли режим AUTO_GATED."""
    return get_trading_mode() == AUTO_GATED

