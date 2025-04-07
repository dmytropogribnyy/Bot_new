from config import trade_stats, trade_stats_lock
from core.notifier import notify_deposit, notify_withdrawal
from utils_logging import log


def check_balance_change(current_balance, last_balance):
    if last_balance == 0:
        with trade_stats_lock:
            trade_stats["initial_balance"] = current_balance
        log(f"Initial balance set: {current_balance} USDC", level="INFO")
        return current_balance

    delta = round(current_balance - last_balance, 2)
    if abs(delta) < 0.5:
        return current_balance

    if delta > 0:
        with trade_stats_lock:
            trade_stats["deposits_today"] += delta
            trade_stats["deposits_week"] += delta
        notify_deposit(delta)

    elif delta < 0:
        with trade_stats_lock:
            trade_stats["withdrawals"] += abs(delta)
        notify_withdrawal(abs(delta))

    return current_balance
