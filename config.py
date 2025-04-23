# config.py

# --- Imports ---
import os
from pathlib import Path
from threading import Lock

import pytz
from dotenv import load_dotenv

load_dotenv()

# --- API & Auth ---
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ALLOWED_USER_ID = 383821734

# --- Exchange --- Уже определено в файле exchange_init.py
# exchange = ccxt.binance(
#     {
#         "apiKey": API_KEY,
#         "secret": API_SECRET,
#         "enableRateLimit": True,
#         "options": {
#             "defaultType": "future",
#             "adjustForTimeDifference": True,
#         },
#         "urls": {
#             "api": {
#                 "public": "https://fapi.binance.com/fapi/v1",
#                 "private": "https://fapi.binance.com/fapi/v1",
#             }
#         },
#     }
# )

# --- Timezone & Paths ---
TIMEZONE = pytz.timezone("Europe/Bratislava")
# config.py
LOG_FILE_PATH = str(Path("c:/Bots/BinanceBot/telegram_log.txt"))
EXPORT_PATH = str(Path("c:/Bots/BinanceBot/data/tp_performance.csv"))
TP_LOG_FILE = str(Path("c:/Bots/BinanceBot/data/tp_performance.csv"))

# Проверка существования файла
if not Path(TP_LOG_FILE).exists():
    raise FileNotFoundError(f"TP_LOG_FILE not found at: {TP_LOG_FILE}")
else:
    print(f"TP_LOG_FILE found at: {TP_LOG_FILE}")

# --- Logging ---
LOG_LEVEL = "DEBUG"  # Уровень логирования: "INFO", "DEBUG", "ERROR"
LOG_SCORE_EVERYWHERE = False  # NEW: Allow score logging in REAL_RUN if True

# --- Mode & Debug ---
DRY_RUN = False
VERBOSE = True
USE_DYNAMIC_IN_DRY_RUN = True
ADAPTIVE_SCORE_ENABLED = True

# --- Symbols & Leverage ---
SYMBOLS_ACTIVE = [
    "BTC/USDC",
    "ETH/USDC",
    "XRP/USDC",
    "ADA/USDC",
    "SOL/USDC",
    "BNB/USDC",
    "LINK/USDC",
    "ARB/USDC",
    "DOGE/USDC",
    "SUI/USDC",
]

FIXED_PAIRS = [
    "BTC/USDC",
    "ETH/USDC",
    "XRP/USDC",
    "ADA/USDC",
    "SOL/USDC",
    "BNB/USDC",
    "LINK/USDC",
    "ARB/USDC",
    "DOGE/USDC",
    "SUI/USDC",
]
# MAX_DYNAMIC_PAIRS = 30
# MIN_DYNAMIC_PAIRS = 15
MAX_DYNAMIC_PAIRS = 0
MIN_DYNAMIC_PAIRS = 0

LEVERAGE_MAP = {
    "DOGE/USDC": 10,
    "BTC/USDC": 5,
    "ETH/USDC": 5,
    "BNB/USDC": 5,
    "ADA/USDC": 10,
    "XRP/USDC": 10,
    "SOL/USDC": 10,
    "SUI/USDC": 10,
    "LINK/USDC": 10,
    "ARB/USDC": 10,
}

# --- TP / SL Strategy ---
TP1_SHARE = 1.0
TP2_SHARE = 0.0
TP1_PERCENT = 0.005  # 0.5%
TP2_PERCENT = 0.01  # 1%
SL_PERCENT = 0.007  # мягкий
SOFT_EXIT_THRESHOLD = 0.8  # быстрее сработает частичный выход

# Для возвращения к нормальному флоу после теста
# TP1_PERCENT = 0.007
# TP1_PERCENT = 0.02  # Временно увеличено для теста
# TP2_PERCENT = 0.013
# TP1_SHARE = 0.7
# TP2_SHARE = 0.3
# SL_PERCENT = 0.01
# TP_SL_MULTIPLIER = 1.2
# SOFT_EXIT_THRESHOLD = 0.9  # 90% от TP1

# --- Risk Management ---
AGGRESSIVENESS_THRESHOLD = 0.6  # Порог для определения AGGRESSIVE режима
AGGRESSIVE_THRESHOLD = 50
SAFE_THRESHOLD = 10
MIN_NOTIONAL = 5
MAX_HOLD_MINUTES = 90
RISK_DRAWDOWN_THRESHOLD = 5.0

# MAX_OPEN_ORDERS = 10  # Limit TP/SL orders per symbol
MAX_OPEN_ORDERS = 3  # Temp for testing

# Фиксированные параметры для теста
MAX_POSITIONS = 3
# RISK_PERCENT = 0.01 #usual value
RISK_PERCENT = 0.005  # temp value for fix

# Функции для автоматизации (будут использоваться после теста для нормального флоу)
# def get_adaptive_risk_percent(balance):
#     """Calculate adaptive risk percentage based on balance."""
#     if balance < 100:
#         return 0.01  # 1% для теста
#     elif balance < 300:
#         return 0.02  # 2%
#     elif balance < 1000:
#         return 0.03  # 3%
#     else:
#         return 0.05  # 5%

# def get_max_positions(balance):
#     """Calculate maximum number of positions based on balance."""
#     if balance < 100:
#         return 1  # 1 сделка для теста
#     elif balance < 300:
#         return 2  # 2 сделки
#     elif balance < 1000:
#         return 3  # 3 сделки
#     else:
#         return 5  # 5 сделок

# --- Entry Filter Thresholds ---
ATR_THRESHOLD = 0.0015
ADX_THRESHOLD = 7
BB_WIDTH_THRESHOLD = 0.008

FILTER_THRESHOLDS = {
    "default": {"atr": 0.00002, "adx": 0.1, "bb": 0.0002},
    "default_light": {"atr": 0.00001, "adx": 0.05, "bb": 0.0001},
    "BTC/USDC": {"atr": 0.00002, "adx": 0.1, "bb": 0.0002},
    "DOGE/USDC": {"atr": 0.000015, "adx": 0.08, "bb": 0.00015},
    "ETH/USDC": {"atr": 0.000015, "adx": 0.08, "bb": 0.00015},
    "BNB/USDC": {"atr": 0.000015, "adx": 0.08, "bb": 0.00015},
    "ADA/USDC": {"atr": 0.000015, "adx": 0.08, "bb": 0.00015},
    "XRP/USDC": {"atr": 0.000015, "adx": 0.08, "bb": 0.00015},
    "SOL/USDC": {"atr": 0.000015, "adx": 0.08, "bb": 0.00015},
    "SUI/USDC": {"atr": 0.000015, "adx": 0.08, "bb": 0.00015},
    "LINK/USDC": {"atr": 0.000015, "adx": 0.08, "bb": 0.00015},
    "ARB/USDC": {"atr": 0.000015, "adx": 0.08, "bb": 0.00015},
}

# Для возвращения к нормальному флоу после теста
# FILTER_THRESHOLDS = {
#     "default": {"atr": 0.0015, "adx": 7, "bb": 0.008},  # Для депозита ≥ 100 USDC
#     "default_light": {"atr": 0.001, "adx": 5, "bb": 0.006},  # Для депозита < 100 USDC
#     "BTC/USDC": {"atr": 0.002, "adx": 10, "bb": 0.01},
#     "DOGE/USDC": {"atr": 0.0015, "adx": 7, "bb": 0.008},
#     "ETH/USDC": {"atr": 0.0015, "adx": 7, "bb": 0.008},
#     "BNB/USDC": {"atr": 0.0015, "adx": 7, "bb": 0.008},
#     "ADA/USDC": {"atr": 0.0015, "adx": 7, "bb": 0.008},
#     "XRP/USDC": {"atr": 0.0015, "adx": 7, "bb": 0.008},
#     "SOL/USDC": {"atr": 0.0015, "adx": 7, "bb": 0.008},
#     "SUI/USDC": {"atr": 0.0015, "adx": 7, "bb": 0.008},
#     "LINK/USDC": {"atr": 0.0015, "adx": 7, "bb": 0.008},
#     "ARB/USDC": {"atr": 0.0015, "adx": 7, "bb": 0.008},
# }

# --- Volatility Filter ---
VOLATILITY_SKIP_ENABLED = False  # Отключено для теста
VOLATILITY_ATR_THRESHOLD = 0.00005  # Уменьшено для теста
VOLATILITY_RANGE_THRESHOLD = 0.0005  # Уменьшено для теста
DRY_RUN_VOLATILITY_ATR_THRESHOLD = 0.0025
DRY_RUN_VOLATILITY_RANGE_THRESHOLD = 0.0075

# Для возвращения к нормальному флоу после теста
# VOLATILITY_SKIP_ENABLED = True
# VOLATILITY_ATR_THRESHOLD = 0.0012
# VOLATILITY_RANGE_THRESHOLD = 0.015
# DRY_RUN_VOLATILITY_ATR_THRESHOLD = 0.0025
# DRY_RUN_VOLATILITY_RANGE_THRESHOLD = 0.0075

# --- Daily Loss Protection ---
DAILY_PROTECTION_ENABLED = True
SAFE_TRIGGER_THRESHOLD = 0.10
FULL_STOP_THRESHOLD = 0.05

# --- Strategy Toggles ---
ENABLE_TRAILING = True
TRAILING_PERCENT = 0.02
ENABLE_BREAKEVEN = True
# ENABLE_BREAKEVEN = False  # Отключено для теста
BREAKEVEN_TRIGGER = 0.5
SOFT_EXIT_ENABLED = True
SOFT_EXIT_SHARE = 0.5  # Закрываем 50% позиции

# Auto TP/SL Adjustments
AUTO_TP_SL_ENABLED = True
FLAT_ADJUSTMENT = 0.7
TREND_ADJUSTMENT = 1.3
ADX_TREND_THRESHOLD = 20
ADX_FLAT_THRESHOLD = 15

# --- Signal Strength Control ---
MIN_TRADE_SCORE = 0
SCORE_BASED_RISK = True
SCORE_BASED_TP = True

SCORE_WEIGHTS = {
    "RSI": 1.0,
    "MACD_RSI": 1.0,
    "MACD_EMA": 1.0,
    "HTF": 1.0,
    "VOLUME": 0.5,
}

# --- Runtime Control ---
RUNNING = True  # Глобальный флаг для Graceful Shutdown

# --- Runtime Trade Stats ---
trade_stats_lock = Lock()
trade_stats = {
    "total": 0,
    "wins": 0,
    "losses": 0,
    "pnl": 0.0,
    "streak_loss": 0,
    "initial_balance": 0,
    "deposits_today": 0,
    "deposits_week": 0,
    "withdrawals": 0,
    "api_errors": 0,
}

# --- IP Monitoring ---
ROUTER_REBOOT_MODE_TIMEOUT_MINUTES = 30
IP_MONITOR_INTERVAL_SECONDS = 180

# --- Symbol Rotation ---
UPDATE_INTERVAL_SECONDS = 60 * 60  # 1 час

# --- Additional Settings ---
USE_HTF_CONFIRMATION = False

# ML TP Optimization
TP_ML_MIN_TRADES_INITIAL = 12
TP_ML_MIN_TRADES_FULL = 20
TP_ML_THRESHOLD = 0.05  # 5% преимущество
TP_ML_SWITCH_THRESHOLD = 0.05

# --- Fees & Profit ---
TAKER_FEE_RATE = 0.0001  # 0.01% для тейкера
MIN_NET_PROFIT = {50: 0.13, 100: 0.3, 500: 1.0, "max": 2.0}  # Смягчено для теста


def get_min_net_profit(balance):
    for threshold in sorted(k for k in MIN_NET_PROFIT if k != "max"):
        if balance <= threshold:
            return MIN_NET_PROFIT[threshold]
    return MIN_NET_PROFIT["max"]


# --- Config File ---
CONFIG_FILE = "config.py"
