# core/exchange_init.py
import time

import ccxt

from common.config_loader import API_KEY, API_SECRET, DRY_RUN, LEVERAGE_MAP, SYMBOLS_ACTIVE
from telegram.telegram_utils import send_telegram_message
from utils_logging import log

# Initialize exchange
exchange = ccxt.binanceusdm(
    {
        "apiKey": API_KEY,
        "secret": API_SECRET,
        "enableRateLimit": True,
        "options": {
            "defaultType": "future",
            "adjustForTimeDifference": True,
        },
    }
)

# Check connection
try:
    log("Checking connection to exchange...", level="INFO")
    exchange.fetch_balance()
    mode_text = "DRY_RUN" if DRY_RUN else "LIVE"
    log(f"Connection to Binance successfully established (Mode: {mode_text})", level="INFO")
    send_telegram_message(f"✅ Binance API connected successfully (Mode: {mode_text})", force=True)
except Exception as e:
    log(f"Error connecting to exchange: {e}", level="ERROR")
    send_telegram_message(f"❌ Error connecting to Binance API: {e}", force=True)


# Set leverage for all active symbols
def set_leverage_for_symbols():
    """Sets leverage for all active symbols."""
    success_count = 0
    error_count = 0

    for symbol in SYMBOLS_ACTIVE:
        try:
            normalized_symbol = symbol.replace("/", "")
            leverage = LEVERAGE_MAP.get(normalized_symbol, 5)  # Default 5x if not specified
            exchange.set_leverage(leverage, symbol)
            log(f"Set leverage {leverage}x for {symbol}", level="INFO")
            success_count += 1
            time.sleep(0.2)  # Small delay between API calls
        except Exception as e:
            log(f"Failed to set leverage for {symbol}: {e}", level="ERROR")
            error_count += 1

    log(f"Leverage setup complete: {success_count} symbols set, {error_count} errors", level="INFO")
    if success_count > 0:
        send_telegram_message(f"✅ Leverage set for {success_count} symbols", force=True)


# Call the function inside a try-except block
try:
    set_leverage_for_symbols()
except Exception as e:
    log(f"Error setting leverage: {e}", level="ERROR")
    send_telegram_message(f"⚠️ Error setting leverage: {e}", force=True)
