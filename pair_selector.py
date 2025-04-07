import json
import os
import time
from threading import Lock  # Fix: Add threading import

import pandas as pd  # Keep for fetch_symbol_data  # noqa: F401  # Keep for calculate_volatility

from config import (
    DRY_RUN,
    FIXED_PAIRS,
    MAX_DYNAMIC_PAIRS,
    MIN_DYNAMIC_PAIRS,
    exchange,  # Keep for fetch_all_symbols
)
from core.strategy import fetch_data, should_enter_trade
from telegram.telegram_utils import escape_markdown_v2, send_telegram_message
from utils_core import get_cached_balance  # Keep for smart pair selection
from utils_logging import log

SYMBOLS_FILE = "data/dynamic_symbols.json"
UPDATE_INTERVAL_SECONDS = 4 * 60 * 60
symbols_file_lock = Lock()

DRY_RUN_FALLBACK_SYMBOLS = [
    "ADA/USDC",
    "XRP/USDC",
    "SUI/USDC",
    "LINK/USDC",
    "ARB/USDC",
    "AVAX/USDC",
    "LTC/USDC",
    "BCH/USDC",
    "NEAR/USDC",
    "ALGO/USDC",
]


def fetch_all_symbols():
    try:
        markets = exchange.load_markets()
        log(f"Loaded markets: {len(markets)} total symbols", level="DEBUG")
        log(f"Sample markets: {list(markets.keys())[:5]}...", level="DEBUG")

        usdc_symbols = [
            symbol
            for symbol in markets.keys()
            if symbol.endswith("/USDC:USDC") or symbol.endswith("USDC:USDC")
        ]
        log(f"Found {len(usdc_symbols)} USDC symbols: {usdc_symbols[:5]}...", level="INFO")

        for symbol in usdc_symbols[:5]:
            log(
                f"Symbol: {symbol}, Type: {markets[symbol]['type']}, Active: {markets[symbol]['active']}",
                level="DEBUG",
            )

        active_usdc_symbols = [symbol for symbol in usdc_symbols if markets[symbol]["active"]]
        log(
            f"Found {len(active_usdc_symbols)} active USDC symbols: {active_usdc_symbols[:5]}...",
            level="DEBUG",
        )

        symbols = [
            symbol
            for symbol in active_usdc_symbols
            if markets[symbol]["type"] in ["future", "swap"]
        ]

        symbols = [symbol.replace(":USDC", "") for symbol in symbols]
        log(f"Fetched {len(symbols)} USDC futures symbols: {symbols[:5]}...", level="INFO")

        if not symbols and DRY_RUN:
            log("No symbols fetched from API in DRY_RUN, using fallback symbols", level="WARNING")
            return DRY_RUN_FALLBACK_SYMBOLS
        return symbols
    except Exception as e:
        log(f"Error fetching all symbols: {str(e)}", level="ERROR")
        if DRY_RUN:
            log("API error in DRY_RUN, using fallback symbols", level="WARNING")
            return DRY_RUN_FALLBACK_SYMBOLS
        return []


def fetch_symbol_data(symbol, timeframe="15m", limit=100):
    return fetch_data(symbol, timeframe)


def calculate_volatility(df):
    if df is None or len(df) < 2:
        return 0
    df["range"] = df["high"] - df["low"]
    return df["range"].mean() / df["close"].mean()


def select_active_symbols(last_trade_times, last_trade_times_lock):
    all_symbols = fetch_all_symbols()
    symbol_scores = {}

    balance = get_cached_balance()
    log(f"Current balance: {balance} USDC", level="INFO")

    max_active_pairs = max(MIN_DYNAMIC_PAIRS, min(MAX_DYNAMIC_PAIRS, int(balance / 20)))
    log(f"Max active pairs based on balance: {max_active_pairs}", level="INFO")

    for symbol in all_symbols:
        if symbol in FIXED_PAIRS:
            continue
        df = fetch_symbol_data(symbol)
        if df is None:
            log(f"Skipping {symbol} due to data fetch error", level="WARNING")
            continue
        with last_trade_times_lock:
            result = should_enter_trade(symbol, df, last_trade_times, last_trade_times_lock)
        if result:
            direction, score = result
            symbol_scores[symbol] = {"score": score, "direction": direction}
        else:
            volatility = calculate_volatility(df)
            volume = df["volume"].mean()
            symbol_scores[symbol] = {"score": volatility * volume, "direction": None}

    sorted_symbols = sorted(
        symbol_scores.items(),
        key=lambda x: x[1]["score"],
        reverse=True,
    )

    selected_dynamic = []
    for symbol, info in sorted_symbols:
        if len(selected_dynamic) >= max_active_pairs:
            break
        if info["direction"]:
            selected_dynamic.append(symbol)
        elif len(selected_dynamic) < MIN_DYNAMIC_PAIRS:
            selected_dynamic.append(symbol)

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


def start_symbol_rotation(last_trade_times, last_trade_times_lock):
    while True:
        try:
            new_symbols = select_active_symbols(last_trade_times, last_trade_times_lock)
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
