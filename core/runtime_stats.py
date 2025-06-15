from collections import deque
from datetime import datetime, timedelta

from utils_core import get_runtime_config
from utils_logging import log

# Хранилище входов по времени — ограничим максимумом для безопасности
hourly_trade_log = deque(maxlen=500)


def update_trade_count():
    """
    Добавляет метку времени при каждом успешном входе в сделку.
    """
    now = datetime.utcnow()
    hourly_trade_log.append(now)


def is_hourly_limit_reached():
    """
    Проверяет, достигнут ли лимит входов в сделку за последний час.
    """
    cfg = get_runtime_config()
    max_trades = cfg.get("max_hourly_trade_limit", 6)

    now = datetime.utcnow()
    cutoff = now - timedelta(hours=1)
    recent = [t for t in hourly_trade_log if t >= cutoff]

    log(f"[HourlyLimit] {len(recent)} trades in last 60 minutes (limit={max_trades})", level="DEBUG")

    return len(recent) >= max_trades
