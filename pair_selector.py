# pair_selector.py
import json
import os
import time
from threading import Lock

import pandas as pd

from config import (
    FIXED_PAIRS,
    MAX_DYNAMIC_PAIRS,
    MIN_DYNAMIC_PAIRS,
    exchange,
)
from telegram.telegram_utils import escape_markdown_v2, send_telegram_message
from utils_logging import log

SYMBOLS_FILE = "data/dynamic_symbols.json"
UPDATE_INTERVAL_SECONDS = 4 * 60 * 60  # 4 hours
symbols_file_lock = Lock()


def fetch_all_symbols():
    try:
        markets = exchange.load_markets()
        symbols = [
            symbol
            for symbol in markets.keys()
            if symbol.endswith("/USDC")
            and markets[symbol]["active"]
            and markets[symbol]["type"] == "future"
        ]
        log(f"Fetched {len(symbols)} USDC futures symbols", level="INFO")
        return symbols
    except Exception as e:
        log(f"Error fetching all symbols: {e}", level="ERROR")
        return []


def fetch_symbol_data(symbol, timeframe="15m", limit=100):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
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
    all_symbols = fetch_all_symbols()
    symbol_data = {}

    for symbol in all_symbols:
        if symbol in FIXED_PAIRS:
            continue
        df = fetch_symbol_data(symbol)
        if df is not None:
            volatility = calculate_volatility(df)
            volume = df["volume"].mean()
            symbol_data[symbol] = {"volatility": volatility, "volume": volume}

    sorted_symbols = sorted(
        symbol_data.items(),
        key=lambda x: x[1]["volatility"] * x[1]["volume"],
        reverse=True,
    )
    dynamic_count = max(MIN_DYNAMIC_PAIRS, min(MAX_DYNAMIC_PAIRS, len(sorted_symbols)))
    selected_dynamic = [s[0] for s in sorted_symbols[:dynamic_count]]

    active_symbols = FIXED_PAIRS + selected_dynamic
    log(
        f"Selected {len(active_symbols)} active symbols: {len(FIXED_PAIRS)} fixed, {len(selected_dynamic)} dynamic",
        level="INFO",
    )

    try:
        os.makedirs(os.path.dirname(SYMBOLS_FILE), exist_ok=True)
        with symbols_file_lock:
            with open(SYMBOLS_FILE, "w") as f:
                json.dump(active_symbols, f)
        log(f"Saved active symbols to {SYMBOLS_FILE}", level="INFO")
    except Exception as e:
        log(f"Error saving active symbols to {SYMBOLS_FILE}: {e}", level="ERROR")

    return active_symbols


def start_symbol_rotation():
    while True:
        try:
            new_symbols = select_active_symbols()
            msg = (
                f"🔄 Symbol rotation completed:\n"
                f"Total pairs: {len(new_symbols)}\n"
                f"Fixed: {len(FIXED_PAIRS)}, Dynamic: {len(new_symbols) - len(FIXED_PAIRS)}"
            )
            send_telegram_message(escape_markdown_v2(msg), force=True)
        except Exception as e:
            log(f"Symbol rotation error: {e}", level="ERROR")
            send_telegram_message(
                escape_markdown_v2(f"⚠️ Symbol rotation failed: {str(e)}"),
                force=True,
            )
        time.sleep(UPDATE_INTERVAL_SECONDS)
