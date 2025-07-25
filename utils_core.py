import csv
import decimal
import json
import os
import time
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from threading import Lock

from constants import ENTRY_LOG_FILE, STATE_FILE
from telegram.telegram_utils import send_telegram_message
from utils_logging import log

MARGIN_SAFETY_BUFFER = 0.92  # безопасность на случай нехватки маржи

# Глобальные настройки кеша
CACHE_TTL = 30
api_cache = {
    "balance": {"value": None, "timestamp": 0},
    "positions": {"value": [], "timestamp": 0},
}
cache_lock = Lock()

# Состояние бота
DEFAULT_STATE = {
    "stopping": False,
    "shutdown": False,
    "allowed_user_id": 383821734,
}
state_lock = Lock()

# Runtime config
RUNTIME_CONFIG_FILE = Path("data/runtime_config.json")


def ensure_data_directory():
    """Убедиться, что директория data/ существует и доступна."""

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


def get_cached_balance():
    """Получает кэшированный баланс (totalMarginBalance)."""
    from core.exchange_init import exchange

    with cache_lock:
        # ✅ ДОБАВЛЕНО: Защита от отсутствующих ключей
        if "balance" not in api_cache:
            api_cache["balance"] = {"value": None, "timestamp": 0}
            log("[Cache] Initialized missing 'balance' key in api_cache", level="DEBUG")

        now = time.time()
        if (now - api_cache["balance"]["timestamp"] > CACHE_TTL) or (api_cache["balance"]["value"] is None):
            try:
                balance_info = exchange.fetch_balance()
                total_margin = float(balance_info["info"].get("totalMarginBalance", 0))
                api_cache["balance"]["value"] = total_margin
                api_cache["balance"]["timestamp"] = now
                log(f"Updated balance cache: {total_margin} USDC", level="DEBUG")
            except Exception as e:
                log(f"Error fetching balance: {e}", level="ERROR")
                send_telegram_message(f"⚠️ Failed to fetch balance: {e}", force=True)
                # ✅ УЛУЧШЕНО: Безопасное обращение к кешу
                cached_value = api_cache.get("balance", {}).get("value")
                return cached_value if cached_value is not None else 0.0
        return api_cache["balance"]["value"]


def get_cached_positions():
    """Получает кэшированные позиции (exchange.fetch_positions)."""
    from core.exchange_init import exchange

    with cache_lock:
        # ✅ ДОБАВЛЕНО: Защита от отсутствующих ключей
        if "positions" not in api_cache:
            api_cache["positions"] = {"value": [], "timestamp": 0}
            log("[Cache] Initialized missing 'positions' key in api_cache", level="DEBUG")

        now = time.time()
        if (now - api_cache["positions"]["timestamp"] > CACHE_TTL) or (not api_cache["positions"]["value"]):
            try:
                all_positions = exchange.fetch_positions()
                api_cache["positions"]["value"] = all_positions
                api_cache["positions"]["timestamp"] = now
                log(f"Updated positions cache: {len(all_positions)} positions", level="DEBUG")
            except Exception as e:
                log(f"Error fetching positions: {e}", level="ERROR")
                send_telegram_message(f"⚠️ Failed to fetch positions: {e}", force=True)
                # ✅ УЛУЧШЕНО: Безопасное обращение к кешу
                cached_value = api_cache.get("positions", {}).get("value")
                return cached_value if cached_value else []
        return api_cache["positions"]["value"]


def initialize_cache():
    """Инициализация кэша и проверка директории data/."""

    if not ensure_data_directory():
        send_telegram_message("⚠️ Проблема с доступом к директории data/. Проверьте права доступа.", force=True)

    get_cached_balance()
    get_cached_positions()
    log("API cache initialized", level="INFO")


def load_state():
    """Загружает состояние бота (stopping, shutdown и пр.) из STATE_FILE."""

    with state_lock:
        try:
            if not os.path.exists(STATE_FILE):
                log(f"State file {STATE_FILE} not found, using default state.", level="INFO")
                return DEFAULT_STATE.copy()

            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
            # Заполним недостающие ключи значениями по умолчанию
            for k, v in DEFAULT_STATE.items():
                if k not in state:
                    state[k] = v
            return state

        except json.JSONDecodeError as e:
            log(f"Error decoding state file {STATE_FILE}: {e}. Using default state.", level="ERROR", important=True)
            send_telegram_message(f"❌ Error decoding state file {STATE_FILE}: {str(e)}. Reset to default state.", force=True)
            return DEFAULT_STATE.copy()
        except Exception as e:
            log(f"Unexpected error loading state file {STATE_FILE}: {e}. Using default state.", level="ERROR", important=True)
            send_telegram_message(f"❌ Unexpected error loading state file {STATE_FILE}: {str(e)}. Reset to default state.", force=True)
            return DEFAULT_STATE.copy()


def save_state(state, retries=3, delay=1):
    """Сохраняет текущее состояние бота в STATE_FILE с попытками ретрая."""

    attempt = 0
    while attempt < retries:
        with state_lock:
            try:
                temp_file = STATE_FILE + ".tmp"
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(state, f, indent=4)
                os.replace(temp_file, STATE_FILE)

                # Проверка, что сохранили корректно
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    saved_state = json.load(f)
                if saved_state != state:
                    log(f"State mismatch after save: expected {state}, got {saved_state}", level="ERROR")
                    raise ValueError("State mismatch after save")
                return
            except Exception as e:
                attempt += 1
                log(f"Attempt {attempt}/{retries} - Error saving state to {STATE_FILE}: {e}", level="ERROR", important=True)
                if attempt == retries:
                    send_telegram_message(f"❌ Failed to save state to {STATE_FILE} after {retries} attempts: {str(e)}", force=True)
                else:
                    time.sleep(delay)

    log(f"Failed to save state after {retries} retries.", level="ERROR")


def safe_call_retry(func, *args, tries=3, delay=1, label="API call", **kwargs):
    import time

    from telegram.telegram_utils import send_telegram_message

    for attempt in range(tries):
        try:
            result = func(*args, **kwargs)
            if result is None:
                raise ValueError(f"{label} returned None")

            if attempt > 0:
                log(f"{label} succeeded on attempt {attempt + 1}/{tries}", level="INFO")

            return result

        except (decimal.InvalidOperation, decimal.ConversionSyntax) as dec_e:
            # Перехватываем ошибки Decimal
            log(f"{label} decimal error (attempt {attempt + 1}/{tries}): {dec_e} ({type(dec_e)})", level="ERROR")

            if attempt < tries - 1:
                sleep_time = delay * (2**attempt)
                log(f"{label} retrying in {sleep_time} s...", level="WARNING")
                time.sleep(sleep_time)
            else:
                log(f"{label} exhausted retries after decimal error", level="ERROR")
                send_telegram_message(f"⚠️ {label} failed after {tries} tries (Decimal error)", force=True)
                return None

        except Exception as e:
            log(f"{label} failed (attempt {attempt + 1}/{tries}): {e}", level="ERROR")

            if attempt < tries - 1:
                sleep_time = delay * (2**attempt)
                log(f"{label} retrying in {sleep_time} s...", level="WARNING")
                time.sleep(sleep_time)
            else:
                log(f"{label} exhausted retries", level="ERROR")
                send_telegram_message(f"⚠️ {label} failed after {tries} retries", force=True)
                return None


def get_runtime_config() -> dict:
    """Загружает runtime_config.json, возвращает dict или пустой dict при ошибке."""

    if RUNTIME_CONFIG_FILE.exists():
        try:
            with open(RUNTIME_CONFIG_FILE, "r") as f:
                config = json.load(f)

            if not isinstance(config, dict):
                raise TypeError(f"runtime_config is not a dict → {type(config)}")

            return config
        except Exception as e:
            log(f"⚠️ Failed to load runtime_config.json: {e}", level="ERROR")
    return {}


def update_runtime_config(new_values: dict):
    """Обновляет runtime_config.json и логирует изменения."""

    config = get_runtime_config()
    config.update(new_values)
    try:
        with open(RUNTIME_CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        log(f"✅ Runtime config updated: {new_values}", level="INFO")
    except Exception as e:
        log(f"⚠️ Failed to update runtime_config.json: {e}", level="ERROR")

    # Логирование истории изменений
    history_path = Path("data/parameter_history.json")
    try:
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

    # Telegram-уведомление
    try:
        summary = "\n".join([f"{k}: {v}" for k, v in new_values.items()])
        send_telegram_message(f"🔧 *runtime_config updated:*\n```\n{summary}\n```", markdown=True)
        log("[RuntimeConfig] Update notification sent to Telegram", level="INFO")
    except Exception as e:
        log(f"[RuntimeConfig] Telegram notification failed: {e}", level="WARNING")


def log_rejected_entry(symbol, reasons, breakdown):
    """
    Логирует отказ от входа в сделку. (Без упоминания score).
    """

    symbol = extract_symbol(symbol)
    row = {
        "timestamp": datetime.utcnow().isoformat(),
        "symbol": symbol,
        "reasons": ",".join(reasons),
        "components": ";".join([f"{k}:{v:.2f}" for k, v in breakdown.items()]),
    }
    try:
        with open(ENTRY_LOG_FILE, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            if f.tell() == 0:
                writer.writeheader()
            writer.writerow(row)
    except Exception as e:
        log(f"Failed to log rejected entry for {symbol}: {e}", level="ERROR")


def initialize_runtime_adaptive_config():
    """
    Устанавливает базовые значения в runtime_config при старте (без HTF, score и т.д.).
    """

    balance = get_cached_balance() or 100

    if balance < 120:
        max_positions = 3
    elif balance < 300:
        max_positions = 5
    elif balance < 600:
        max_positions = 7
    else:
        max_positions = 10

    current_config = get_runtime_config()
    defaults = {
        "max_concurrent_positions": max_positions,
        "risk_multiplier": 1.0,
        "wick_sensitivity": 0.3,
        "rsi_threshold": 50,
        "rel_volume_threshold": 0.5,
        "SL_PERCENT": 0.015,
        "last_adaptation_timestamp": None,
    }

    # Проверим, не хватает ли каких-то ключей
    missing = {k: v for k, v in defaults.items() if k not in current_config}
    if missing:
        update_runtime_config(missing)
        log(f"Initialized missing runtime config values: {missing}", level="INFO")


def get_min_net_profit(balance=None):
    """
    Адаптивная шкала прибыли:
    - Если последняя сделка убыточна → 0.10
    - Если 0–1 TP1/TP2 подряд → 0.10
    - Если 2–4 подряд → 0.20
    - Если ≥5 подряд → 0.30
    - Если явно задано в runtime_config["min_profit_threshold"] — используется оно
    """
    import os

    import pandas as pd

    from common.config_loader import TP_LOG_FILE
    from tp_logger import get_last_trade
    from utils_logging import log

    # ✅ Сначала проверяем runtime override (если установлен явно)
    try:
        cfg = get_runtime_config()
        if "min_profit_threshold" in cfg:
            return float(cfg["min_profit_threshold"])
    except Exception as e:
        log(f"[ProfitAdapt] Failed to read runtime_config override: {e}", level="WARNING")

    # 🧠 Далее стандартная адаптация по TP streak
    last = get_last_trade()
    if not last:
        return 0.10

    last_result = str(last.get("Result", "")).upper()
    abs_profit = float(last.get("Absolute Profit", 0))

    if last_result == "SL" or abs_profit < 0:
        return 0.10  # сброс

    try:
        if not os.path.exists(TP_LOG_FILE):
            return 0.10

        df = pd.read_csv(TP_LOG_FILE)
        df = df[df["Result"].isin(["TP1", "TP2"])]
        if df.empty:
            return 0.10

        # Подсчёт TP подряд с конца
        streak = 0
        for result in reversed(df["Result"].tolist()):
            if result in ("TP1", "TP2"):
                streak += 1
            else:
                break

        if streak < 2:
            return 0.10
        elif streak < 5:
            return 0.20
        else:
            return 0.30

    except Exception as e:
        log(f"[ProfitAdapt] Failed to compute TP streak: {e}", level="ERROR")
        return 0.10


def reset_state_flags():
    """Сбрасывает stopping и shutdown в state-файле."""

    st = load_state()
    st["stopping"] = False
    st["shutdown"] = False
    save_state(st)
    log("Reset stopping and shutdown flags in state file", level="INFO")


# Утилиты для JSON-файлов (общие)
def load_json_file(path, default=None):
    """Загрузка JSON с обработкой ошибок."""

    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            log(f"File not found: {path}", level="WARNING")
            return default if default is not None else {}
    except Exception as e:
        log(f"Error loading JSON file {path}: {e}", level="ERROR")
        return default if default is not None else {}


def save_json_file(path, data, indent=2):
    """Сохранение JSON с обработкой ошибок."""

    try:
        directory = os.path.dirname(path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent)
        log(f"Successfully saved data to {path}", level="DEBUG")
        return True
    except Exception as e:
        log(f"Error saving JSON file {path}: {e}", level="ERROR")
        return False


def is_optimal_trading_hour(strict: bool = True) -> bool:
    """
    Проверка, разрешено ли торговать в текущий час UTC согласно runtime_config.

    - strict=True: используем monitoring_hours_utc (например, 2–23)
    - strict=False: мягкое окно — разрешены только override-сделки

    Возвращает True, если текущий UTC-час разрешён.
    """
    now_utc_hour = datetime.utcnow().hour
    config = get_runtime_config()

    allowed_hours = config.get("monitoring_hours_utc", list(range(24)))

    if now_utc_hour in allowed_hours:
        log(f"[TimeCheck] ⏰ UTC hour={now_utc_hour} → ✅ allowed", level="DEBUG")
        return True
    else:
        if not strict:
            log(f"[TimeCheck] ⏰ UTC hour={now_utc_hour} → ⚠️ not allowed, but soft override enabled", level="DEBUG")
            return True
        log(f"[TimeCheck] ⏰ UTC hour={now_utc_hour} → ❌ not allowed (strict mode)", level="DEBUG")
        return False


def normalize_symbol(symbol) -> str:
    """
    Унифицирует формат символа:
    - Если dict — извлекает .get("symbol")
    - Приводит к формату BASE/QUOTE:QUOTE
    - Пример: "btc-usdc" → "BTC/USDC:USDC"
    - Безопасно обрабатывает странные входы
    """
    if isinstance(symbol, dict):
        symbol = symbol.get("symbol", "")

    if not isinstance(symbol, str) or not symbol:
        return ""

    symbol = symbol.upper().split(":")[0]
    symbol = symbol.replace("-", "/").replace(":", "/")

    if "/" not in symbol:
        return symbol

    base, quote = symbol.split("/", 1)
    return f"{base}/{quote}:{quote}"


def calculate_atr_volatility(df, period: int = 14) -> float:
    """
    Вычисляет ATR (Average True Range) по DataFrame с колонками ['high', 'low', 'close'].
    Возвращает последнее значение (float).
    """

    try:
        import ta

        atr_series = ta.volatility.AverageTrueRange(high=df["high"], low=df["low"], close=df["close"], window=period).average_true_range()
        return float(atr_series.iloc[-1]) if len(atr_series) else 0.0
    except Exception as e:
        log(f"[calculate_atr_volatility] Error: {e}", level="ERROR")
        return 0.0


def get_market_volatility_index() -> float:
    """
    Возвращает относительную волатильность BTC: ATR / текущая цена
    (примерный диапазон: 0.5–2.0).
    """

    try:
        import pandas as pd
        import ta

        from core.binance_api import fetch_ohlcv

        # Загружаем последние 50 свечей BTC/USDC (15м)
        raw = fetch_ohlcv("BTC/USDC", timeframe="15m", limit=50)
        if not raw or len(raw) < 20:
            return 1.0

        df = pd.DataFrame(raw, columns=["time", "open", "high", "low", "close", "volume"])
        atr_series = ta.volatility.AverageTrueRange(high=df["high"], low=df["low"], close=df["close"], window=14).average_true_range()
        atr = atr_series.iloc[-1]
        close_price = float(df["close"].iloc[-1])

        return round(atr / close_price, 4) if close_price else 1.0

    except Exception as e:
        log(f"[Volatility] Ошибка в get_market_volatility_index: {e}", level="WARNING")
        return 1.0


def extract_symbol(s):
    return normalize_symbol(s.get("symbol", "") if isinstance(s, dict) else s)
    # and then use  like symbol = extract_symbol(symbol)


def get_total_position_value():
    """
    Считает общую текущую стоимость всех открытых позиций (в USDT/USDC).

    Returns:
        float: Общая стоимость позиций.
    """
    from core.exchange_init import exchange

    try:
        positions = safe_call_retry(exchange.fetch_positions)
        total_value = 0.0
        log(f"[DEBUG] get_total_position_value: {len(positions)} positions", level="DEBUG")

        for pos in positions:
            amt = float(pos.get("positionAmt", 0))
            entry = float(pos.get("entryPrice", 0))
            symbol = pos.get("symbol", "UNKNOWN")

            if abs(amt) < 1e-6 or entry <= 0:
                continue  # пропускаем фантомные или нулевые позиции

            value = abs(amt * entry)
            total_value += value
            log(f"[DEBUG] → {symbol}: amt={amt}, entry={entry}, value={value:.2f}", level="DEBUG")

        log(f"[DEBUG] Total position value = {total_value:.2f}", level="DEBUG")
        return total_value

    except Exception as e:
        log(f"[get_total_position_value] ❌ Ошибка при расчёте: {e}", level="ERROR")
        return 0.0


def safe_float_conversion(value, default=0.0):
    """Универсальная безопасная конвертация в float"""
    if value is None:
        return default
    try:
        if isinstance(value, str):
            value = value.strip().replace(",", "")
        if hasattr(value, "__float__"):
            return float(value)
        return float(str(value))
    except (ValueError, TypeError, InvalidOperation) as e:
        log(f"[SafeFloat] Failed to convert {value}: {e}", level="ERROR")
        return default


def safe_decimal(value):
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError) as e:
        log(f"[SafeDecimal] Failed to convert {value}: {e}", level="ERROR")
        return Decimal("0")


if __name__ == "__main__":
    initialize_cache()
    print("Balance:", get_cached_balance())
    print("Positions:", len(get_cached_positions()))
