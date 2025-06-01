# notifier.py

from telegram.telegram_utils import send_telegram_message
from utils_logging import log


def notify_dry_trade(trade_data):
    """
    Notify about a DRY_RUN trade.
    No longer logs 'score' because new logic doesn't use 'score'.
    """
    symbol = trade_data["symbol"]
    direction = trade_data["direction"]
    qty = trade_data["qty"]
    entry_price = trade_data.get("entry", 0.0)

    log(f"{symbol} 🔍 Notifying dry trade: qty = {qty:.3f}", level="DEBUG")
    log(f"{symbol} 🧪 [DRY_RUN] Signal → {direction}", level="INFO")

    # Telegram message 1
    msg = f"🧪-DRY-RUN-{symbol}-{direction}"
    send_telegram_message(msg, force=True, parse_mode="")

    # Telegram message 2 (more details)
    msg = f"DRY-RUN-{direction}{symbol}@{entry_price:.2f}Qty{qty:.3f}"
    send_telegram_message(msg, force=True, parse_mode="")
    log(msg, level="INFO")


def notify_error(message):
    msg = f"🔥-{message}"
    send_telegram_message(msg, force=True, parse_mode="")
    log(msg, level="ERROR")


def notify_deposit(delta):
    msg = f"📥-Deposit-detected-+{delta:.2f}-USDC"
    send_telegram_message(msg, force=True, parse_mode="")
    log(msg, level="INFO")


def notify_withdrawal(delta):
    msg = f"📤-Withdrawal-detected--{delta:.2f}-USDC"
    send_telegram_message(msg, force=True, parse_mode="")
    log(msg, level="INFO")


def notify_low_balance(current_balance, threshold):
    """
    Notify when the balance drops below critical thresholds.
    """
    from telegram.telegram_utils import send_telegram_message

    message = f"⚠️ LOW BALANCE WARNING: Balance fell below {threshold} USDC (Current: {current_balance:.2f} USDC)"
    send_telegram_message(message, force=True)


def notify_milestone(milestone, growth_pct):
    """
    Notify when an account balance milestone is reached.
    """
    from telegram.telegram_utils import send_telegram_message

    if isinstance(milestone, str) and milestone == "2x":
        message = f"🎉 MILESTONE REACHED: Account doubled! Growth: {growth_pct:.2f}%"
    else:
        message = f"🎉 MILESTONE REACHED: Balance exceeded {milestone} USDC! Growth: {growth_pct:.2f}%"

    send_telegram_message(message, force=True)
