import json
import os
import time
from datetime import datetime
from pathlib import Path
from threading import Lock

from common.config_loader import LEVERAGE_MAP, SYMBOLS_ACTIVE
from constants import STATE_FILE
from core.exchange_init import exchange
from telegram.telegram_utils import send_telegram_message
from utils_logging import log

DEFAULT_STATE = {
    "stopping": False,
    "shutdown": False,
    "allowed_user_id": 383821734,
}

RANGE_LIMITS = {
    "score_threshold": (1.2, 3.5),
    "momentum_min": (0.0, 2.5),
    "wick_sensitivity": (0.0, 1.0),
    "htf_required": (0, 1),
}

CACHE_TTL = 30
api_cache = {
    "balance": {"value": None, "timestamp": 0},
    "positions": {"value": [], "timestamp": 0},
}
cache_lock = Lock()
state_lock = Lock()

RUNTIME_CONFIG_FILE = Path("data/runtime_config.json")


def ensure_data_directory():
    """Убедиться, что директория data/ существует и доступна"""
    data_dir = "data/"
    if not os.path.exists(data_dir):
        try:
            os.makedirs(data_dir, exist_ok=True)
            log(f"Создана директория {data_dir}", level="INFO")
        except Exception as e:
            log(f"Ошибка при создании директории {data_dir}: {e}", level="ERROR")
            return False

    # Проверка прав доступа
    try:
        test_file = os.path.join(data_dir, ".test_access")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        return True
    except Exception as e:
        log(f"Ошибка доступа к директории {data_dir}: {e}", level="ERROR")
        return False


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


def adjust_from_missed_opportunities():
    """
    Adapt runtime configuration based on missed trading opportunities.
    Analyzes missed_opportunities.json to identify patterns and adjust parameters.
    """
    import json
    from pathlib import Path

    from utils_core import RANGE_LIMITS, get_runtime_config, update_runtime_config
    from utils_logging import log

    path = Path("data/missed_opportunities.json")
    if not path.exists():
        log("[MissedFeedback] missed_opportunities.json not found", level="WARNING")
        return

    try:
        with open(path, "r") as f:
            data = json.load(f)

        if not data:
            return

        # Sort by profit descending
        top = sorted(data.items(), key=lambda x: x[1].get("profit", 0), reverse=True)[:3]
        avg_profit = sum(v.get("profit", 0) for _, v in top) / len(top)
        log(f"[MissedFeedback] Top missed avg profit: {avg_profit:.2f}", level="DEBUG")

        updates = {}
        if avg_profit > 5:
            config = get_runtime_config()

            # Use RANGE_LIMITS from utils_core for parameter boundaries
            if config.get("momentum_min", 0) > 0.3:
                updates["momentum_min"] = max(config["momentum_min"] - 0.1, RANGE_LIMITS["momentum_min"][0])

            if config.get("score_threshold", 0) > 2.0:
                updates["score_threshold"] = max(config["score_threshold"] - 0.05, RANGE_LIMITS["score_threshold"][0])

        if updates:
            log(f"[MissedFeedback] Adapting config from missed opportunities: {updates}", level="INFO")
            update_runtime_config(updates)

    except Exception as e:
        log(f"[MissedFeedback] Error processing missed_opportunities: {e}", level="ERROR")


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
        if now - api_cache["balance"]["timestamp"] > CACHE_TTL or api_cache["balance"]["value"] is None:
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
                return api_cache["balance"]["value"] if api_cache["balance"]["value"] is not None else 0.0
        log(f"Returning cached balance: {api_cache['balance']['value']}", level="DEBUG")
        return api_cache["balance"]["value"]


def get_cached_positions():
    with cache_lock:
        now = time.time()
        if now - api_cache["positions"]["timestamp"] > CACHE_TTL or not api_cache["positions"]["value"]:
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
    if not ensure_data_directory():
        send_telegram_message("⚠️ Проблема с доступом к директории data/. Проверьте права доступа.", force=True)

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


def get_runtime_config() -> dict:
    if RUNTIME_CONFIG_FILE.exists():
        try:
            with open(RUNTIME_CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            log(f"⚠️ Failed to load runtime_config.json: {e}", level="ERROR")
    return {}


def update_runtime_config(new_values: dict):
    config = get_runtime_config()
    config.update(new_values)

    try:
        with open(RUNTIME_CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        log(f"✅ Runtime config updated: {new_values}", level="INFO")
    except Exception as e:
        log(f"⚠️ Failed to update runtime_config.json: {e}", level="ERROR")

    # Parameter history logging
    try:
        history_path = Path("data/parameter_history.json")
        if history_path.exists():
            with open(history_path, "r") as f:
                history = json.load(f)
        else:
            history = []

        history.append({"timestamp": datetime.utcnow().isoformat(), "updates": new_values})
        with open(history_path, "w") as f:
            json.dump(history[-100:], f, indent=2)
    except Exception as e:
        log(f"⚠️ Error logging parameter history: {e}", level="WARNING")

    # Telegram notification of changes
    try:
        summary = "\n".join([f"{k}: {v}" for k, v in new_values.items()])
        send_telegram_message(f"🔧 *runtime_config updated:*\n```\n{summary}\n```", markdown=True)
        log("[RuntimeConfig] Update notification sent to Telegram", level="INFO")
    except Exception as e:
        log(f"[RuntimeConfig] Telegram notification failed: {e}", level="WARNING")


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


# --- Новые функции для адаптивного риск-менеджмента ---


def get_adaptive_risk_percent(balance):
    """
    Возвращает адаптивный процент риска на основе размера счета.

    Args:
        balance: Размер депозита

    Returns:
        Процент риска для данного размера счета
    """
    if balance < 100:
        return 0.01  # 1%
    elif balance < 150:
        return 0.02  # 2%
    elif balance < 300:
        return 0.03  # 3%
    else:
        return 0.05  # 5%


def get_max_positions(balance):
    """
    Возвращает максимальное количество позиций на основе размера счета.

    Args:
        balance: Размер депозита

    Returns:
        Максимальное количество открытых позиций
    """
    if balance < 100:
        return 1
    elif balance < 150:
        return 2
    elif balance < 300:
        return 3
    else:
        return 5


def get_min_net_profit(balance):
    """
    Возвращает минимальную допустимую прибыль для сделки на основе размера счета.

    Args:
        balance: Размер депозита

    Returns:
        Минимальная прибыль в USDC
    """
    if balance < 100:
        return 0.2  # $0.2 для очень малых депозитов
    elif balance < 200:
        return 0.3  # $0.3 для малых депозитов
    elif balance < 500:
        return 0.5  # $0.5 для средних депозитов
    else:
        return 1.0  # $1.0 для больших депозитов


def calculate_risk_reward_ratio(entry_price, tp_price, sl_price, side):
    """
    Рассчитывает соотношение риск/прибыль для сделки.

    Args:
        entry_price: Цена входа
        tp_price: Цена тейк-профита
        sl_price: Цена стоп-лосса
        side: Направление ("buy" или "sell")

    Returns:
        Соотношение риск/прибыль (reward / risk)
    """
    if side.lower() == "buy":
        reward = abs(tp_price - entry_price)
        risk = abs(entry_price - sl_price)
    else:  # side == "sell"
        reward = abs(entry_price - tp_price)
        risk = abs(sl_price - entry_price)

    if risk == 0:
        return 0  # Избегаем деления на ноль

    return reward / risk


def check_min_profit(entry_price, tp_price, qty, tp_share, side, taker_fee_rate, min_profit):
    """
    Проверяет, обеспечивает ли сделка минимальную прибыль после комиссий.

    Args:
        entry_price: Цена входа
        tp_price: Цена тейк-профита
        qty: Количество
        tp_share: Доля позиции, закрываемая на TP (0-1)
        side: Направление ("buy" или "sell")
        taker_fee_rate: Комиссия тейкера
        min_profit: Минимальная требуемая прибыль в USDC

    Returns:
        (bool, float): Результат проверки и ожидаемая прибыль
    """
    # Рассчитываем прибыль без комиссий
    if side.lower() == "buy":
        gross_profit = qty * tp_share * (tp_price - entry_price)
    else:  # side == "sell"
        gross_profit = qty * tp_share * (entry_price - tp_price)

    # Рассчитываем комиссии
    open_commission = qty * entry_price * taker_fee_rate
    close_commission = qty * tp_share * tp_price * taker_fee_rate
    total_commission = open_commission + close_commission

    # Чистая прибыль
    net_profit = gross_profit - total_commission

    return net_profit >= min_profit, net_profit


def get_market_volatility_index():
    """
    Рассчитывает индекс волатильности рынка на основе ключевых пар.
    Возвращает значение обычно между 0.5 (низкая волатильность) и 2.0 (высокая волатильность).
    """
    try:
        from core.binance_api import fetch_ohlcv

        # Используем основные пары для оценки общей волатильности рынка
        key_pairs = ["BTC/USDC", "ETH/USDC"]
        volatilities = []

        for pair in key_pairs:
            data = fetch_ohlcv(pair, timeframe="15m", limit=24)
            if data and len(data) >= 24:
                closes = [candle[4] for candle in data]
                highs = [candle[2] for candle in data]
                lows = [candle[3] for candle in data]

                # Расчет относительного диапазона цен
                ranges = [(h - low) / c for h, low, c in zip(highs, lows, closes)]
                avg_range = sum(ranges) / len(ranges)

                # Сравнение с "нормальным" диапазоном (базовое значение 0.01 или 1%)
                rel_volatility = avg_range / 0.01
                volatilities.append(rel_volatility)

        if volatilities:
            return sum(volatilities) / len(volatilities)

        return 1.0  # Дефолтное значение - нормальная волатильность
    except Exception as e:
        log(f"Error calculating market volatility index: {e}", level="ERROR")
        return 1.0  # Дефолтное значение в случае ошибки


def reset_state_flags():
    """Reset stop and shutdown flags in the state file."""
    state = load_state()
    state["stopping"] = False
    state["shutdown"] = False
    save_state(state)
    from utils_logging import log

    log("Reset stopping and shutdown flags in state file", level="INFO")


# =======================
# Open Interest Cache
# =======================

_symbol_oi_cache = {}


def get_cached_symbol_open_interest(symbol):
    return _symbol_oi_cache.get(symbol, 0.0)


def update_cached_symbol_open_interest(symbol, value):
    _symbol_oi_cache[symbol] = value


# Add to utils_core.py
def load_json_file(path, default=None):
    """
    Load data from a JSON file with error handling.

    Args:
        path: Path to the JSON file
        default: Default value to return if loading fails

    Returns:
        dict: The loaded JSON data or default value
    """
    import json
    import os

    try:
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
        else:
            log(f"File not found: {path}", level="WARNING")
            return default if default is not None else {}
    except Exception as e:
        log(f"Error loading JSON file {path}: {e}", level="ERROR")
        return default if default is not None else {}


def save_json_file(path, data, indent=2):
    """
    Save data to a JSON file with error handling.

    Args:
        path: Path to the JSON file
        data: Data to save (must be JSON serializable)
        indent: Indentation level for the JSON file

    Returns:
        bool: True if successful, False otherwise
    """
    import json
    import os

    try:
        # Create directory if it doesn't exist
        directory = os.path.dirname(path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        with open(path, "w") as f:
            json.dump(data, f, indent=indent)
        log(f"Successfully saved data to {path}", level="DEBUG")
        return True
    except Exception as e:
        log(f"Error saving JSON file {path}: {e}", level="ERROR")
        return False


def is_optimal_trading_hour():
    """
    Centralized check for optimal trading hours.
    Excludes only deep night hours (3–7 UTC).
    """
    inactive_hours = [3, 4, 5, 6, 7]
    current_hour = datetime.utcnow().hour
    return current_hour not in inactive_hours


if __name__ == "__main__":
    initialize_cache()
    print(f"Balance: {get_cached_balance()}")
    print(f"Positions: {len(get_cached_positions())}")
