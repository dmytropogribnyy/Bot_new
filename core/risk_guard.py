from datetime import UTC, datetime, timedelta

# Хранилище временных блокировок
symbol_blocklist = {}
symbol_last_entry = {}


# Пауза после 3 SL подряд, например
def is_symbol_blocked(symbol):
    unblock_time = symbol_blocklist.get(symbol)
    if unblock_time and datetime.now(UTC) < unblock_time:
        return True
    return False


def pause_symbol(symbol, minutes=120):
    symbol_blocklist[symbol] = datetime.now(UTC) + timedelta(minutes=minutes)


def is_symbol_recently_traded(symbol, pause_seconds=300):
    last_time = symbol_last_entry.get(symbol)
    if last_time and (datetime.now(UTC) - last_time).total_seconds() < pause_seconds:
        return True
    return False


def update_symbol_last_entry(symbol):
    symbol_last_entry[symbol] = datetime.now(UTC)
