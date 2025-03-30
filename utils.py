# utils.py

import pytz
from datetime import datetime
from config import TIMEZONE
from telegram_handler import send_telegram_message

def now():
    return datetime.now(TIMEZONE)

def log(message):
    print(f"[{now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")

def is_low_volatility(atr, price, threshold=0.005):
    return atr / price < threshold

def notify_entry(symbol, side, amount, tp, sl):
    send_telegram_message(
        f"✅ {side.upper()} {symbol}\nAmount: {amount}\nTP: {tp:.4f} / SL: {sl:.4f}", force=True)

def notify_error(context, error):
    send_telegram_message(f"❌ Error in {context}: {error}", force=True)
