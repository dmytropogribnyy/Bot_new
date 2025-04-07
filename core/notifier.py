from telegram.telegram_utils import escape_markdown_v2, send_telegram_message
from utils_logging import log


def notify_dry_trade(trade):
    msg = (
        f"DRY RUN: {trade['direction'].upper()} {trade['symbol']} @ {trade['entry']:.2f}"
        f" | Qty: {trade['qty']:.2f}"
    )
    send_telegram_message(escape_markdown_v2(msg), force=True)
    log(msg, level="INFO")


def notify_error(message):
    msg = f"🔥 {message}"
    send_telegram_message(escape_markdown_v2(msg), force=True)
    log(msg, level="ERROR")


def notify_deposit(delta):
    msg = f"📥 Deposit detected: +{delta:.2f} USDC"
    send_telegram_message(escape_markdown_v2(msg), force=True)
    log(msg, level="INFO")


def notify_withdrawal(delta):
    msg = f"📤 Withdrawal detected: -{delta:.2f} USDC"
    send_telegram_message(escape_markdown_v2(msg), force=True)
    log(msg, level="INFO")
