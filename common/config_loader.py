# common/config_loader.py

import os

from dotenv import load_dotenv

# Загрузка переменных окружения из файла .env
load_dotenv()


def get_config(var_name: str, default=None):
    """Получить значение переменной окружения или вернуть дефолт."""
    return os.getenv(var_name, default)


# 🔹 Основные переменные проекта

# Binance API
API_KEY = get_config("API_KEY")
API_SECRET = get_config("API_SECRET")
USE_TESTNET = get_config("USE_TESTNET", "False") == "True"

# Telegram
TELEGRAM_TOKEN = get_config("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = get_config("TELEGRAM_CHAT_ID")

# Общие настройки
DRY_RUN = get_config("DRY_RUN", "False") == "True"
EXPORT_PATH = get_config("EXPORT_PATH", "data/")
TP_LOG_FILE = get_config("TP_LOG_FILE", "data/tp_log.csv")
LOG_FILE_PATH = get_config("LOG_FILE_PATH", "logs/main.log")
LOG_LEVEL = get_config("LOG_LEVEL", "INFO")

# Параметры торговли
LEVERAGE_MAP = {
    "BTCUSDT": 5,
    "ETHUSDT": 5,
    "DOGEUSDC": 10,
    # можно дополнять свои пары
}

SYMBOLS_ACTIVE = get_config("SYMBOLS_ACTIVE", "").split(",") if get_config("SYMBOLS_ACTIVE") else []

# Параметры TP/SL
TP1_PERCENT = float(get_config("TP1_PERCENT", "0.7"))
TP2_PERCENT = float(get_config("TP2_PERCENT", "1.4"))

# Флаги стратегии
USE_HTF_CONFIRMATION = get_config("USE_HTF_CONFIRMATION", "False") == "True"
ADAPTIVE_SCORE_ENABLED = get_config("ADAPTIVE_SCORE_ENABLED", "True") == "True"
AGGRESSIVENESS_THRESHOLD = float(get_config("AGGRESSIVENESS_THRESHOLD", "0.6"))

# Дополнительные настройки (если будут)
CONFIG_FILE = get_config("CONFIG_FILE", "config/config.json")
FIXED_PAIRS = get_config("FIXED_PAIRS", "").split(",") if get_config("FIXED_PAIRS") else []
VERBOSE = get_config("VERBOSE", "False") == "True"
