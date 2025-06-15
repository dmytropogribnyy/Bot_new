from collections import deque
from datetime import datetime, timedelta

# Хранилище входов по времени — ограничим максимумом для безопасности
hourly_trade_log = deque(maxlen=500)


def update_trade_count():
    """
    Добавляет метку времени при каждом успешном входе в сделку.
    """
    now = datetime.utcnow()
    hourly_trade_log.append(now)


def is_hourly_limit_reached(max_trades=6):
    """
    Проверяет, достигнут ли лимит входов в сделку за последний час.
    """
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=1)
    recent = [t for t in hourly_trade_log if t >= cutoff]
    return len(recent) >= max_trades
