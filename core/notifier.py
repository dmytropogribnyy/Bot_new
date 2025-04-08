from telegram.telegram_utils import send_telegram_message
from utils_logging import log


def notify_dry_trade(trade):
    msg = f"DRY-RUN-{trade['direction'].upper()}{trade['symbol']}at{trade['entry']:.2f}Qty{trade['qty']:.2f}"
    send_telegram_message(msg, force=True, parse_mode="")  # Отключаем MarkdownV2
    log(msg, level="INFO")


def notify_error(message):
    msg = f"🔥-{message}"
    send_telegram_message(msg, force=True, parse_mode="")  # Отключаем MarkdownV2
    log(msg, level="ERROR")


def notify_deposit(delta):
    msg = f"📥-Deposit-detected-+{delta:.2f}-USDC"
    send_telegram_message(msg, force=True, parse_mode="")  # Отключаем MarkdownV2
    log(msg, level="INFO")


def notify_withdrawal(delta):
    msg = f"📤-Withdrawal-detected--{delta:.2f}-USDC"
    send_telegram_message(msg, force=True, parse_mode="")  # Отключаем MarkdownV2
    log(msg, level="INFO")
