# core/exchange_init.py
import time

import ccxt

from common.config_loader import API_KEY, API_SECRET, DRY_RUN, LEVERAGE_MAP, SYMBOLS_ACTIVE
from telegram.telegram_utils import send_telegram_message
from utils_logging import log

# Initialize exchange (Standard Futures)
exchange = ccxt.binance(
    {
        "apiKey": API_KEY,
        "secret": API_SECRET,
        "enableRateLimit": True,
        "options": {
            "defaultType": "future",  # futures mode (USDT-M)
            "adjustForTimeDifference": True,
        },
    }
)

# Check connection
try:
    log("Checking connection to exchange...", level="INFO")
    exchange.load_markets()
    mode_text = "DRY_RUN" if DRY_RUN else "LIVE"
    log(f"Connection to Binance Futures successfully established (Mode: {mode_text})", level="INFO")
    send_telegram_message(f"✅ Binance API connected successfully (Mode: {mode_text})", force=True)
except Exception as e:
    log(f"Error connecting to Binance Futures: {e}", level="ERROR")
    send_telegram_message(f"❌ Error connecting to Binance Futures: {e}", force=True)


def set_leverage_for_symbols():
    """Sets leverage for all active symbols."""
    success_count = 0
    error_count = 0

    for symbol in SYMBOLS_ACTIVE:
        try:
            normalized_symbol = symbol.replace("/", "")
            if normalized_symbol not in exchange.markets:
                log(f"Symbol {symbol} not found on exchange (skip)", level="WARNING")
                continue

            leverage = LEVERAGE_MAP.get(normalized_symbol, 5)
            exchange.fapiPrivate_post_leverage({"symbol": normalized_symbol, "leverage": leverage})
            log(f"Set leverage {leverage}x for {symbol}", level="INFO")
            success_count += 1
            time.sleep(0.2)
        except Exception as e:
            log(f"Failed to set leverage for {symbol}: {e}", level="ERROR")
            error_count += 1

    log(f"Leverage setup complete: {success_count} symbols set, {error_count} errors", level="INFO")
    if success_count > 0:
        send_telegram_message(f"✅ Leverage set for {success_count} symbols", force=True)


# Set leverage after connecting
try:
    set_leverage_for_symbols()
except Exception as e:
    log(f"Error setting leverage: {e}", level="ERROR")
    send_telegram_message(f"⚠️ Error setting leverage: {e}", force=True)
