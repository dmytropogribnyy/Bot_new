import json
import time
from collections import defaultdict
from threading import Lock

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
    now = int(time.time())
    with ACTIVITY_LOCK:
        data = load_activity()
        if symbol not in data:
            data[symbol] = []
        # Очистка старых записей
        data[symbol] = [ts for ts in data[symbol] if ts >= now - ACTIVITY_WINDOW]
        data[symbol].append(now)
        save_activity(data)


def get_most_active_symbols(top_n=5, minutes=60):
    cutoff = int(time.time()) - minutes * 60
    counts = defaultdict(int)
    with ACTIVITY_LOCK:
        data = load_activity()
        for symbol, timestamps in data.items():
            recent = [ts for ts in timestamps if ts >= cutoff]
            counts[symbol] = len(recent)

    sorted_symbols = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return [s[0] for s in sorted_symbols[:top_n]]
