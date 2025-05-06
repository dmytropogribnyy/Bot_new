# core/exchange_init.py
import time

import ccxt

from common.config_loader import API_KEY, API_SECRET, DRY_RUN, LEVERAGE_MAP, SYMBOLS_ACTIVE, USE_TESTNET
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
    from core.binance_api import convert_symbol  # Правильный импорт

    success_count = 0
    error_count = 0

    for symbol in SYMBOLS_ACTIVE:
        try:
            api_symbol = convert_symbol(symbol)  # Корректное преобразование символа

            # Правильное форматирование символа для API
            if USE_TESTNET:
                # Для тестнета может потребоваться другой формат
                normalized_symbol = api_symbol.replace("/", "").replace(":USDC", "")
            else:
                # Для реального режима - убираем слеш
                normalized_symbol = symbol.replace("/", "")

            # Проверка существования символа на бирже
            markets = exchange.load_markets()
            if normalized_symbol not in [m.replace("/", "") for m in markets.keys()]:
                log(f"Symbol {symbol} не найден на бирже (пропускаем)", level="WARNING")
                continue

            # Получение значения кредитного плеча из конфигурации
            leverage = LEVERAGE_MAP.get(normalized_symbol, 5)

            # Установка кредитного плеча
            exchange.fapiPrivate_post_leverage({"symbol": normalized_symbol, "leverage": leverage})
            log(f"Установлено кредитное плечо {leverage}x для {symbol}", level="INFO")
            success_count += 1
            time.sleep(0.2)  # Небольшая задержка между запросами
        except Exception as e:
            log(f"Ошибка установки кредитного плеча для {symbol}: {e}", level="ERROR")
            error_count += 1

    log(f"Настройка кредитного плеча завершена: установлено для {success_count} символов, {error_count} ошибок", level="INFO")
    if success_count > 0:
        send_telegram_message(f"✅ Кредитное плечо установлено для {success_count} символов", force=True)
