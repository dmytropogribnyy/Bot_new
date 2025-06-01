import json
import os
import time
from collections import defaultdict
from threading import Lock

# Было: from filter_adaptation_leg import get_runtime_config
# Заменяем на utils_core (или другой модуль, где вы храните get_runtime_config):
from utils_core import get_runtime_config, load_json_file, save_json_file
from utils_logging import log

FILE_PATH = "data/symbol_signal_activity.json"
SIGNAL_ACTIVITY_FILE = FILE_PATH
ACTIVITY_WINDOW = 3600  # 1 час
ACTIVITY_LOCK = Lock()


def load_activity():
    try:
        with open(FILE_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_activity(data):
    with open(FILE_PATH, "w") as f:
        json.dump(data, f, indent=4)


def track_symbol_signal(symbol):
    """
    Фиксируем, что по символу пришёл сигнал.
    Очищаем записи старше ACTIVITY_WINDOW, затем добавляем текущий таймстамп.
    """
    now = int(time.time())
    with ACTIVITY_LOCK:
        data = load_activity()
        if symbol not in data:
            data[symbol] = []
        # Очистка старых записей (старше 1 часа)
        data[symbol] = [ts for ts in data[symbol] if ts >= now - ACTIVITY_WINDOW]
        data[symbol].append(now)
        save_activity(data)


def get_most_active_symbols(top_n=5, minutes=60):
    """
    Возвращает список самых "активных" символов за последние N минут,
    основываясь на том, сколько сигналов было зафиксировано.
    """
    cutoff = int(time.time()) - minutes * 60
    counts = defaultdict(int)

    with ACTIVITY_LOCK:
        data = load_activity()
        for symbol, timestamps in data.items():
            recent = [ts for ts in timestamps if ts >= cutoff]
            counts[symbol] = len(recent)

    sorted_symbols = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return [s[0] for s in sorted_symbols[:top_n]]


def auto_adjust_relax_factors_from_missed(min_count_threshold=3, max_relax=0.5):
    """
    Увеличивает relax_factor для символов, у которых часто были пропущенные сигналы
    (хранится в missed_opportunities.json), но не выше max_relax.
    """
    try:
        missed_file = "data/missed_opportunities.json"
        adapt_file = "data/filter_adaptation.json"

        if not os.path.exists(missed_file):
            return

        missed_data = load_json_file(missed_file)
        filter_data = load_json_file(adapt_file)
        updated = False

        for symbol, stats in missed_data.items():
            normalized = symbol.replace("/", "").upper()
            count = stats.get("count", 0)
            if count >= min_count_threshold:
                # Если в filter_adaptation.json нет relax_factor для этого символа — берём дефолт из runtime_config
                current = filter_data.get(normalized, {}).get("relax_factor", get_runtime_config().get("relax_factor", 0.35))
                if current < max_relax:
                    new_relax = round(min(current + 0.05, max_relax), 3)
                    if normalized not in filter_data:
                        filter_data[normalized] = {}
                    filter_data[normalized]["relax_factor"] = new_relax
                    log(f"[AutoRelax] ↑ Increased relax_factor for {symbol}: {current} → {new_relax}", level="INFO")
                    updated = True

        if updated:
            save_json_file(adapt_file, filter_data)
            log("[AutoRelax] Updated relax_factor values based on missed opportunities", level="INFO")
    except Exception as e:
        log(f"[AutoRelax] Error adjusting relax factors: {e}", level="ERROR")


def get_symbol_activity_data():
    """
    Возвращает структуру с количеством сигналов в формате:
    {
      "DOGE/USDC": {"signal_count_24h": 5},
      "BTC/USDC":  {"signal_count_24h": 3},
      ...
    }

    В примере below: signal_count_24h расчитывается как count_1h * 24,
    но вы можете дальше доработать под реальные требования.
    """
    from pathlib import Path

    path = Path(FILE_PATH)
    if not path.exists():
        return {}

    try:
        raw = load_json_file(path)
        # Допустим, у нас в raw для каждого символа храним: {"timestamps": [...]} или что-то подобное.
        # Ниже упрощённо предполагаем, что raw[symbol] = {"count_1h": X}
        # и умножаем на 24, чтобы получить примерную оценку за сутки.
        result = {}
        for symbol, info in raw.items():
            # Если вы храните иначе, подкорректируйте логику:
            # Например, у вас может быть raw[symbol] = [timestamps...], тогда нужно len(...) и т.д.
            if isinstance(info, dict) and "count_1h" in info:
                count_24h = info["count_1h"] * 24
            else:
                # fallback - просто длина массива
                count_24h = len(info) * 24 if isinstance(info, list) else 0
            result[symbol] = {"signal_count_24h": count_24h}
        return result

    except Exception as e:
        log(f"[SymbolActivity] Error loading activity data: {e}", level="ERROR")
        return {}
