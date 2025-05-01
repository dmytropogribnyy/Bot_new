# core/exchange_init.py
import ccxt

from config import API_KEY, API_SECRET, USE_TESTNET
from telegram.telegram_utils import send_telegram_message
from utils_logging import log

exchange_class = ccxt.binanceusdm
if USE_TESTNET:
    exchange = exchange_class(
        {
            "apiKey": API_KEY,
            "secret": API_SECRET,
            "enableRateLimit": True,
            "urls": {
                "api": {
                    "fapi": "https://testnet.binancefuture.com/fapi",
                    "public": "https://testnet.binancefuture.com/fapi",
                    "private": "https://testnet.binancefuture.com/fapi",
                }
            },
            "options": {
                "defaultType": "future",
                "adjustForTimeDifference": True,
            },
        }
    )
    exchange.set_sandbox_mode(True)
    log("Initialized Testnet exchange", level="INFO")
    send_telegram_message("Running in Testnet mode", force=True)
else:
    exchange = exchange_class(
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
    log("Initialized Real exchange", level="INFO")
    send_telegram_message("Running in Real mode", force=True)

# Проверка подключения
try:
    log("Checking exchange connection with fetch_balance", level="DEBUG")
    exchange.fetch_balance()
    log("Exchange connection successful", level="INFO")
except Exception as e:
    log(f"Exchange connection failed: {e}", level="ERROR")
    send_telegram_message(f"⚠️ Exchange connection failed: {e}", force=True)
