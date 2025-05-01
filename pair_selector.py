# pair_selector.py
import json
import os
import time
from threading import Lock

import pandas as pd

from common.config_loader import (
    DRY_RUN,
    FIXED_PAIRS,
    MAX_DYNAMIC_PAIRS,
    MIN_DYNAMIC_PAIRS,
    SYMBOLS_ACTIVE,
    USDC_SYMBOLS,
    USDT_SYMBOLS,
    USE_TESTNET,
)
from core.binance_api import convert_symbol
from core.exchange_init import exchange
from telegram.telegram_utils import send_telegram_message
from utils_core import get_cached_balance, safe_call_retry
from utils_logging import log

SYMBOLS_FILE = "data/dynamic_symbols.json"
UPDATE_INTERVAL_SECONDS = 60 * 60
symbols_file_lock = Lock()

DRY_RUN_FALLBACK_SYMBOLS = USDT_SYMBOLS if USE_TESTNET else USDC_SYMBOLS


def fetch_all_symbols():
    try:
        markets = safe_call_retry(exchange.load_markets, label="load_markets")
        if not markets:
            log("No markets returned from API", level="ERROR")
            if DRY_RUN:
                log("Using fallback symbols in DRY_RUN", level="WARNING")
                send_telegram_message("⚠️ Using fallback symbols due to API failure", force=True)
                return DRY_RUN_FALLBACK_SYMBOLS
            log("No active symbols available and DRY_RUN is False, stopping", level="ERROR")
            send_telegram_message("⚠️ No active symbols available, stopping bot", force=True)
            return []
        log(f"Loaded markets: {len(markets)} total symbols", level="DEBUG")
        log(f"Sample markets: {list(markets.keys())[:5]}...", level="DEBUG")

        active_symbols = []
        for symbol in SYMBOLS_ACTIVE:
            api_symbol = convert_symbol(symbol)
            if api_symbol in markets and markets[api_symbol]["active"]:
                active_symbols.append(symbol)
                log(
                    f"Symbol: {symbol}, API: {api_symbol}, Type: {markets[api_symbol]['type']}, Active: {markets[api_symbol]['active']}",
                    level="DEBUG",
                )
            else:
                log(
                    f"Symbol {symbol} (API: {api_symbol}) not found or inactive on exchange",
                    level="WARNING",
                )

        log(
            f"Validated {len(active_symbols)} active symbols: {active_symbols[:5]}...", level="INFO"
        )
        if not active_symbols and DRY_RUN:
            log("No symbols validated from API in DRY_RUN, using fallback symbols", level="WARNING")
            return DRY_RUN_FALLBACK_SYMBOLS
        return active_symbols
    except Exception as e:
        log(f"Error fetching all symbols: {str(e)}", level="ERROR")
        if DRY_RUN:
            log("API error in DRY_RUN, using fallback symbols", level="WARNING")
            return DRY_RUN_FALLBACK_SYMBOLS
        return []


def fetch_symbol_data(symbol, timeframe="15m", limit=100):
    try:
        api_symbol = convert_symbol(symbol)
        ohlcv = safe_call_retry(
            exchange.fetch_ohlcv, api_symbol, timeframe, limit=limit, label=f"fetch_ohlcv {symbol}"
        )
        if not ohlcv:
            log(f"No OHLCV data returned for {symbol}", level="ERROR")
            return None
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        return df
    except Exception as e:
        log(f"Error fetching data for {symbol}: {e}", level="ERROR")
        return None


def calculate_volatility(df):
    if df is None or len(df) < 2:
        return 0
    df["range"] = df["high"] - df["low"]
    return df["range"].mean() / df["close"].mean()


def select_active_symbols():
    min_dyn = MIN_DYNAMIC_PAIRS
    max_dyn = MAX_DYNAMIC_PAIRS
    if max_dyn > 0:
        balance = get_cached_balance()
        if balance < 100:
            min_dyn = min(min_dyn, 5)
            max_dyn = min(max_dyn, 5)
        else:
            min_dyn = min(min_dyn, 10)
            max_dyn = min(max_dyn, 25)

    all_symbols = fetch_all_symbols()
    fixed = FIXED_PAIRS
    dynamic_data = {}
    for s in all_symbols:
        if s in fixed:
            continue
        df = fetch_symbol_data(s)
        if df is not None:
            dynamic_data[s] = {
                "volatility": calculate_volatility(df),
                "volume": df["volume"].mean(),
            }

    sorted_dyn = sorted(
        dynamic_data.items(), key=lambda x: x[1]["volatility"] * x[1]["volume"], reverse=True
    )[:30]
    dyn_count = max(min_dyn, min(max_dyn, len(sorted_dyn)))
    selected_dyn = [s for s, _ in sorted_dyn[:dyn_count]]

    active_symbols = fixed + selected_dyn
    log(f"Validated {len(active_symbols)} active symbols: {active_symbols[:5]}...", level="INFO")
    try:
        os.makedirs(os.path.dirname(SYMBOLS_FILE), exist_ok=True)
        with symbols_file_lock, open(SYMBOLS_FILE, "w") as f:
            json.dump(active_symbols, f)
        log(f"Saved active symbols to {SYMBOLS_FILE}", level="INFO")
    except Exception as e:
        log(f"Error saving active symbols to {SYMBOLS_FILE}: {e}", level="ERROR")

    msg = (
        f"🔄 Symbol rotation completed:\n"
        f"Total pairs: {len(active_symbols)}\n"
        f"Fixed: {len(fixed)}, Dynamic: {len(selected_dyn)}"
    )
    send_telegram_message(msg, force=True)
    return active_symbols


def start_symbol_rotation(stop_event):
    while not stop_event.is_set():
        try:
            select_active_symbols()
        except Exception as e:
            log(f"Symbol rotation error: {e}", level="ERROR")
            send_telegram_message(f"⚠️ Symbol rotation failed: {e}", force=True)
        time.sleep(UPDATE_INTERVAL_SECONDS)
