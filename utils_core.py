import json
import os
import time
from datetime import datetime
from threading import Lock

from common.config_loader import LEVERAGE_MAP, SYMBOLS_ACTIVE
from core.exchange_init import exchange
from telegram.telegram_utils import send_telegram_message
from utils_logging import log

STATE_FILE = "data/bot_state.json"
DEFAULT_STATE = {
    "stopping": False,
    "shutdown": False,
    "allowed_user_id": 383821734,
}

CACHE_TTL = 30
api_cache = {
    "balance": {"value": None, "timestamp": 0},
    "positions": {"value": [], "timestamp": 0},
}
cache_lock = Lock()
state_lock = Lock()


def get_last_signal_time():
    path = "data/last_signal.txt"
    if not os.path.exists(path):
        log(f"Last signal file {path} not found.", level="INFO")
        return None
    try:
        with open(path, "r") as f:
            ts = f.read().strip()
            return datetime.fromisoformat(ts)
    except Exception as e:
        log(f"Error reading last signal time from {path}: {e}", level="ERROR")
        return None


def update_last_signal_time():
    path = "data/last_signal.txt"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(datetime.now().isoformat())
        log(f"Updated last signal time in {path}.", level="INFO")
    except Exception as e:
        log(f"Error updating last signal time in {path}: {e}", level="ERROR")


def get_open_symbols():
    try:
        open_syms = []
        positions = get_cached_positions()
        for p in positions:
            if float(p.get("contracts", 0)) > 0:
                open_syms.append(p["symbol"])
        log(f"Fetched open symbols: {open_syms}", level="INFO")
        return open_syms
    except Exception as e:
        log(f"Error fetching open symbols: {e}", level="ERROR")
        return []


def get_cached_balance():
    with cache_lock:
        now = time.time()
        log("Checking balance cache...", level="DEBUG")
        if (
            now - api_cache["balance"]["timestamp"] > CACHE_TTL
            or api_cache["balance"]["value"] is None
        ):
            try:
                log("[DEBUG] Fetching balance from exchange...", level="DEBUG")
                balance_info = exchange.fetch_balance()
                total_margin_balance = float(balance_info["info"].get("totalMarginBalance", 0))
                log(
                    f"[DEBUG] Fetched balance (totalMarginBalance): {total_margin_balance}",
                    level="DEBUG",
                )
                api_cache["balance"]["value"] = total_margin_balance
                api_cache["balance"]["timestamp"] = now
                log(
                    f"Updated balance cache: {api_cache['balance']['value']} USDC",
                    level="DEBUG",
                )
            except Exception as e:
                log(f"Error fetching balance: {e}", level="ERROR")
                send_telegram_message(f"⚠️ Failed to fetch balance: {e}", force=True)
                return (
                    api_cache["balance"]["value"]
                    if api_cache["balance"]["value"] is not None
                    else 0.0
                )
        log(f"Returning cached balance: {api_cache['balance']['value']}", level="DEBUG")
        return api_cache["balance"]["value"]


def get_cached_positions():
    with cache_lock:
        now = time.time()
        if (
            now - api_cache["positions"]["timestamp"] > CACHE_TTL
            or not api_cache["positions"]["value"]
        ):
            try:
                api_cache["positions"]["value"] = exchange.fetch_positions()
                api_cache["positions"]["timestamp"] = now
                log(
                    f"Updated positions cache: {len(api_cache['positions']['value'])} positions",
                    level="DEBUG",
                )
            except Exception as e:
                log(f"Error fetching positions: {e}", level="ERROR")
                send_telegram_message(f"⚠️ Failed to fetch positions: {e}", force=True)
                return api_cache["positions"]["value"] if api_cache["positions"]["value"] else []
        return api_cache["positions"]["value"]


def initialize_cache():
    get_cached_balance()
    get_cached_positions()
    log("API cache initialized", level="INFO")


def load_state():
    with state_lock:
        try:
            if not os.path.exists(STATE_FILE):
                log(f"State file {STATE_FILE} not found, using default state.", level="INFO")
                return DEFAULT_STATE.copy()
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
                log(f"Loaded state from {STATE_FILE}: {state}", level="DEBUG")
                for key, value in DEFAULT_STATE.items():
                    if key not in state:
                        state[key] = value
                return state
        except json.JSONDecodeError as e:
            log(
                f"Error decoding state file {STATE_FILE}: {e}. Using default state.",
                important=True,
                level="ERROR",
            )
            send_telegram_message(
                f"❌ Error decoding state file {STATE_FILE}: {str(e)}. Reset to default state.",
                force=True,
            )
            return DEFAULT_STATE.copy()
        except Exception as e:
            log(
                f"Unexpected error loading state file {STATE_FILE}: {e}. Using default state.",
                important=True,
                level="ERROR",
            )
            send_telegram_message(
                f"❌ Unexpected error loading state file {STATE_FILE}: {str(e)}. Reset to default state.",
                force=True,
            )
            return DEFAULT_STATE.copy()


def save_state(state, retries=3, delay=1):
    attempt = 0
    while attempt < retries:
        with state_lock:
            try:
                log(
                    f"Attempting to save state (attempt {attempt + 1}/{retries}): {state}",
                    level="DEBUG",
                )
                os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
                temp_file = STATE_FILE + ".tmp"
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(state, f, indent=4)
                os.replace(temp_file, STATE_FILE)
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    saved_state = json.load(f)
                log(f"Successfully saved state to {STATE_FILE}: {saved_state}", level="DEBUG")
                if saved_state != state:
                    log(
                        f"State mismatch after save: expected {state}, got {saved_state}",
                        level="ERROR",
                    )
                    raise ValueError("State mismatch after save")
                return
            except Exception as e:
                attempt += 1
                log(
                    f"Attempt {attempt}/{retries} - Error saving state to {STATE_FILE}: {e}",
                    important=True,
                    level="ERROR",
                )
                if attempt == retries:
                    send_telegram_message(
                        f"❌ Failed to save state to {STATE_FILE} after {retries} attempts: {str(e)}",
                        force=True,
                    )
                else:
                    time.sleep(delay)
    log(f"Failed to save state after {retries} retries.", level="ERROR")


def safe_call_retry(func, *args, tries=3, delay=1, label="API call", **kwargs):
    for attempt in range(tries):
        try:
            result = func(*args, **kwargs)
            if result is None:
                raise ValueError(f"{label} returned None")
            return result
        except Exception as e:
            log(f"{label} failed (attempt {attempt + 1}/{tries}): {e}", level="ERROR")
            if attempt < tries - 1:
                time.sleep(delay)
            else:
                log(f"{label} exhausted retries", level="ERROR")
                send_telegram_message(f"⚠️ {label} failed after {tries} retries", force=True)
                return None


def set_leverage_for_symbols():
    for symbol in SYMBOLS_ACTIVE:
        leverage = LEVERAGE_MAP.get(symbol, 5)
        safe_call_retry(
            exchange.set_leverage,
            leverage,
            symbol,
            tries=3,
            delay=1,
            label=f"set_leverage {symbol}",
        )
    log("Leverage set for all symbols", level="INFO")


if __name__ == "__main__":
    initialize_cache()
    print(f"Balance: {get_cached_balance()}")
    print(f"Positions: {len(get_cached_positions())}")
