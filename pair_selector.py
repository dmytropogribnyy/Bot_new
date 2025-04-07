# pair_selector.py
import json
import os
import time
from threading import Lock

import pandas as pd

from config import (
    DRY_RUN,
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

# Fallback list for DRY_RUN with valid Binance USDM Futures symbols
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

        # Filter for USDC symbols with new format (e.g., BTC/USDC:USDC)
        usdc_symbols = [
            symbol
            for symbol in markets.keys()
            if symbol.endswith("/USDC:USDC") or symbol.endswith("USDC:USDC")
        ]
        log(f"Found {len(usdc_symbols)} USDC symbols: {usdc_symbols[:5]}...", level="INFO")

        # Log details of the first few USDC symbols
        for symbol in usdc_symbols[:5]:
            log(
                f"Symbol: {symbol}, Type: {markets[symbol]['type']}, Active: {markets[symbol]['active']}",
                level="DEBUG",
            )

        # Updated: Add back filters for type and active status
        # Reason: Now that API works, we can filter for active futures/swap pairs
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

        # Normalize symbols to remove :USDC suffix (e.g., BTC/USDC:USDC -> BTC/USDC)
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
    try:
        # Convert symbol back to API format for fetching data (e.g., BTC/USDC -> BTC/USDC:USDC)
        api_symbol = f"{symbol}:USDC"
        ohlcv = exchange.fetch_ohlcv(api_symbol, timeframe, limit=limit)
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
