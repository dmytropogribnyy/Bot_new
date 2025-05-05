# notifier.py
from telegram.telegram_utils import send_telegram_message
from utils_logging import log


def notify_dry_trade(trade_data):
    symbol = trade_data["symbol"]
    direction = trade_data["direction"]
    qty = trade_data["qty"]
    score = trade_data["score"]
    log(f"{symbol} 🔍 Notifying dry trade: qty = {qty:.3f}", level="DEBUG")
    log(f"{symbol} 🧪 [DRY_RUN] Signal → {direction}, score: {score}/5", level="INFO")
    msg = f"🧪-DRY-RUN-{symbol}-{direction}-Score-{round(score, 2)}-of-5"
    send_telegram_message(msg, force=True, parse_mode="")
    # Use a more precise format for qty to avoid rounding to 0.00
    msg = f"DRY-RUN-{direction}{symbol}at{trade_data['entry']:.2f}Qty{qty:.3f}"
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

    Args:
        current_balance: Current account balance
        threshold: The threshold that was crossed (e.g., 50, 100)
    """
    from telegram.telegram_utils import send_telegram_message

    message = f"⚠️ LOW BALANCE WARNING: Balance fell below {threshold} USDC (Current: {current_balance:.2f} USDC)"
    send_telegram_message(message, force=True)


def notify_milestone(milestone, growth_pct):
    """
    Notify when an account balance milestone is reached.

    Args:
        milestone: The milestone value or identifier (e.g., 150, "2x")
        growth_pct: Current growth percentage
    """
    from telegram.telegram_utils import send_telegram_message

    if isinstance(milestone, str) and milestone == "2x":
        message = f"🎉 MILESTONE REACHED: Account doubled! Growth: {growth_pct:.2f}%"
    else:
        message = f"🎉 MILESTONE REACHED: Balance exceeded {milestone} USDC! Growth: {growth_pct:.2f}%"

    send_telegram_message(message, force=True)
