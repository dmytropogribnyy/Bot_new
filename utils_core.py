import json
import os
import time
from datetime import datetime
from threading import Lock

from config import exchange
from telegram.telegram_utils import send_telegram_message
from utils_logging import log

STATE_FILE = "data/bot_state.json"
DEFAULT_STATE = {
    "pause": False,
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
                log("Fetching balance from exchange...", level="DEBUG")
                api_cache["balance"]["value"] = exchange.fetch_balance()["total"]["USDC"]
                log(f"Fetched balance: {api_cache['balance']['value']}", level="DEBUG")
                api_cache["balance"]["timestamp"] = now
                log(
                    f"Updated balance cache: {api_cache['balance']['value']} USDC",
                    level="DEBUG",
                )
            except Exception as e:
                log(f"Error fetching balance: {e}", level="ERROR")
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
                return DEFAULT_STATE.copy()
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
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
                os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
                with open(STATE_FILE, "w", encoding="utf-8") as f:
                    json.dump(state, f, indent=4)
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


def get_adaptive_risk_percent(balance):
    """Calculate adaptive risk percentage based on balance."""
    if balance < 100:
        return 0.03
    elif balance < 300:
        return 0.05
    else:
        return 0.07


if __name__ == "__main__":
    initialize_cache()
    print(f"Balance: {get_cached_balance()}")
    print(f"Positions: {len(get_cached_positions())}")
