from datetime import datetime, timedelta
from threading import Lock

from utils_logging import log

# Anti-reentry (пауза между входами)
last_trade_times = {}
last_trade_times_lock = Lock()

# Auto-pause по 3 loss подряд
loss_streaks = {}  # symbol: count
paused_symbols = {}  # symbol: datetime

# Daily max loss — глобальная пауза
global_trading_pause_until = None


def is_symbol_paused(symbol: str) -> bool:
    until = paused_symbols.get(symbol)
    if until and until > datetime.utcnow():
        return True
    elif until:
        paused_symbols.pop(symbol, None)
    return False


def pause_symbol(symbol: str, minutes: int = 15):
    until = datetime.utcnow() + timedelta(minutes=minutes)
    paused_symbols[symbol] = until
    log(f"[LossStreak] {symbol} paused until {until}", level="WARNING")


def increment_loss_streak(symbol: str):
    loss_streaks[symbol] = loss_streaks.get(symbol, 0) + 1


def reset_loss_streak(symbol: str):
    loss_streaks.pop(symbol, None)


def get_loss_streak(symbol: str) -> int:
    return loss_streaks.get(symbol, 0)


def pause_all_trading(minutes: int = 60):
    global global_trading_pause_until
    global_trading_pause_until = datetime.utcnow() + timedelta(minutes=minutes)
    log(f"[GlobalPause] Trading paused for {minutes} minutes due to daily loss limit", level="ERROR")


def is_trading_globally_paused() -> bool:
    global global_trading_pause_until
    if global_trading_pause_until and global_trading_pause_until > datetime.utcnow():
        return True
    return False
