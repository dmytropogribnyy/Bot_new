# common/config_loader.py
"""
Centralized configuration management for BinanceBot
Contains all trading parameters, thresholds, and runtime settings
"""

import os
from pathlib import Path
from threading import Lock

import pytz
from dotenv import load_dotenv

from utils_logging import log

try:
    from constants import SYMBOLS_FILE
except ImportError:
    SYMBOLS_FILE = "data/dynamic_symbols.json"

load_dotenv()


def get_config(var_name: str, default=None):
    """Get value from environment variables or return default."""
    return os.getenv(var_name, default)


# ========== API Configuration ==========
API_KEY = get_config("API_KEY")
API_SECRET = get_config("API_SECRET")
USE_TESTNET = get_config("USE_TESTNET", "False") == "True"

# ========== Trading Modes ==========
DRY_RUN = get_config("DRY_RUN", "False") == "True"
VERBOSE = get_config("VERBOSE", "False") == "True"
RUNNING = True

# ========== Telegram Settings ==========
TELEGRAM_TOKEN = get_config("TELEGRAM_TOKEN", "")
if TELEGRAM_TOKEN:
    TELEGRAM_TOKEN = TELEGRAM_TOKEN.replace("\\x3a", ":")
TELEGRAM_CHAT_ID = get_config("TELEGRAM_CHAT_ID")

print(f"Loaded TELEGRAM_TOKEN: {TELEGRAM_TOKEN if TELEGRAM_TOKEN else 'Not set'}")
print(f"Loaded TELEGRAM_CHAT_ID: {TELEGRAM_CHAT_ID if TELEGRAM_CHAT_ID else 'Not set'}")

# ========== Paths and Files ==========
CONFIG_FILE = get_config("CONFIG_FILE", "C:/Bots/BinanceBot/common/config_loader.py")
EXPORT_PATH = get_config("EXPORT_PATH", "C:/Bots/BinanceBot/data/tp_performance.csv")
TP_LOG_FILE = get_config("TP_LOG_FILE", "C:/Bots/BinanceBot/data/tp_performance.csv")
LOG_FILE_PATH = get_config("LOG_FILE_PATH", "C:/Bots/BinanceBot/logs/main.log")
LOG_LEVEL = get_config("LOG_LEVEL", "INFO")

ENABLE_FULL_DEBUG_MONITORING = get_config("ENABLE_FULL_DEBUG_MONITORING", "False") == "True"

if not Path(TP_LOG_FILE).exists():
    log(f"TP_LOG_FILE not found at: {TP_LOG_FILE}", level="WARNING")
else:
    log(f"TP_LOG_FILE found at: {TP_LOG_FILE}", level="INFO")

# ========== Trading Symbols ==========
USDT_SYMBOLS = ["BTC/USDT"]
USDC_SYMBOLS = [
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

DEFAULT_PRIORITY_SMALL_BALANCE_PAIRS = [
    "XRP/USDC",
    "DOGE/USDC",
    "ADA/USDC",
    "SOL/USDC",
    "MATIC/USDC",
    "DOT/USDC",
]


def set_bot_status(status: str):
    """
    Устанавливает текущий статус бота ('running', 'paused', 'stopped') в runtime_config.json.
    """
    from utils_core import update_runtime_config

    if status not in ("running", "paused", "stopped"):
        raise ValueError(f"Invalid status: {status}")

    update_runtime_config({"bot_status": status})


def get_priority_small_balance_pairs():
    """Load priority pairs from file if available, else use defaults."""
    try:
        from core.priority_evaluator import load_priority_pairs

        return load_priority_pairs()
    except Exception as e:
        log(f"Error loading dynamic priority pairs: {e}. Using defaults.", level="WARNING")
        return DEFAULT_PRIORITY_SMALL_BALANCE_PAIRS


SYMBOLS_ACTIVE = get_config("SYMBOLS_ACTIVE", "").split(",") if get_config("SYMBOLS_ACTIVE") else USDC_SYMBOLS
FIXED_PAIRS = get_config("FIXED_PAIRS", "").split(",") if get_config("FIXED_PAIRS") else []
MAX_DYNAMIC_PAIRS = int(get_config("MAX_DYNAMIC_PAIRS", 15))
MIN_DYNAMIC_PAIRS = int(get_config("MIN_DYNAMIC_PAIRS", 6))

# ========== Micro-Trade Optimization ==========
MICRO_TRADE_TIMEOUT_MINUTES = int(get_config("MICRO_TRADE_TIMEOUT_MINUTES", 240))
MICRO_TRADE_SIZE_THRESHOLD = float(get_config("MICRO_TRADE_SIZE_THRESHOLD", 0.15))
MICRO_PROFIT_THRESHOLD = float(get_config("MICRO_PROFIT_THRESHOLD", 0.2))
MICRO_PROFIT_ENABLED = get_config("MICRO_PROFIT_ENABLED", "True") == "True"

# ========== Pair Rotation Optimization ==========
MISSED_OPPORTUNITIES_FILE = get_config("MISSED_OPPORTUNITIES_FILE", "data/missed_opportunities.json")
PAIR_COOLING_PERIOD_HOURS = int(get_config("PAIR_COOLING_PERIOD_HOURS", 24))
PAIR_ROTATION_MIN_INTERVAL = int(get_config("PAIR_ROTATION_MIN_INTERVAL", 600))

# ========== Risk Management ==========
RISK_PERCENT = None  # will be set dynamically
MAX_POSITIONS = int(get_config("MAX_POSITIONS", 3))  # Deprecated
MAX_OPEN_ORDERS = int(get_config("MAX_OPEN_ORDERS", 5))
MAX_MARGIN_PERCENT = float(get_config("MAX_MARGIN_PERCENT", 0.2))
MIN_NOTIONAL_OPEN = float(get_config("MIN_NOTIONAL_OPEN", 20))
MIN_NOTIONAL_ORDER = float(get_config("MIN_NOTIONAL_ORDER", 20))

# ========== Strategy Mode Settings ==========
GLOBAL_SCALPING_TEST = False

# ========== TP/SL Settings ==========
TP1_PERCENT = float(get_config("TP1_PERCENT", 0.007))
TP2_PERCENT = float(get_config("TP2_PERCENT", 0.014))
SL_PERCENT = float(get_config("SL_PERCENT", 0.007))
TP1_SHARE = float(get_config("TP1_SHARE", 0.8))
TP2_SHARE = float(get_config("TP2_SHARE", 0.2))

# ========== Auto-Profit Settings ==========
AUTO_CLOSE_PROFIT_THRESHOLD = 5.0
BONUS_PROFIT_THRESHOLD = 7.0

# ========== Fee Rates ==========
TAKER_FEE_RATE = float(get_config("TAKER_FEE_RATE", 0.0005))
MAKER_FEE_RATE = float(get_config("MAKER_FEE_RATE", 0.0002))

# ========== Auto TP/SL Adjustments ==========
AUTO_TP_SL_ENABLED = get_config("AUTO_TP_SL_ENABLED", "True") == "True"
FLAT_ADJUSTMENT = float(get_config("FLAT_ADJUSTMENT", 0.7))
TREND_ADJUSTMENT = float(get_config("TREND_ADJUSTMENT", 1.3))
ADX_TREND_THRESHOLD = float(get_config("ADX_TREND_THRESHOLD", 20))
ADX_FLAT_THRESHOLD = float(get_config("ADX_FLAT_THRESHOLD", 15))

# ========== Exit Strategies ==========
ENABLE_TRAILING = get_config("ENABLE_TRAILING", "True") == "True"
ENABLE_BREAKEVEN = get_config("ENABLE_BREAKEVEN", "True") == "True"
BREAKEVEN_TRIGGER = float(get_config("BREAKEVEN_TRIGGER", 0.30))
SOFT_EXIT_ENABLED = get_config("SOFT_EXIT_ENABLED", "True") == "True"
SOFT_EXIT_THRESHOLD = float(get_config("SOFT_EXIT_THRESHOLD", 0.7))
SOFT_EXIT_SHARE = float(get_config("SOFT_EXIT_SHARE", 0.5))

# ========== Monitoring Settings ==========
IP_MONITOR_INTERVAL_SECONDS = int(get_config("IP_MONITOR_INTERVAL_SECONDS", 180))
ROUTER_REBOOT_MODE_TIMEOUT_MINUTES = int(get_config("ROUTER_REBOOT_MODE_TIMEOUT_MINUTES", 30))

# ========== ML TP Optimization ==========
TP_ML_MIN_TRADES_INITIAL = int(get_config("TP_ML_MIN_TRADES_INITIAL", 12))
TP_ML_MIN_TRADES_FULL = int(get_config("TP_ML_MIN_TRADES_FULL", 20))
TP_ML_SWITCH_THRESHOLD = float(get_config("TP_ML_SWITCH_THRESHOLD", 0.05))

# ========== Safety and Margin Buffer ==========
MARGIN_SAFETY_BUFFER = float(get_config("MARGIN_SAFETY_BUFFER", 0.92))

# ========== Timezone Settings ==========
TIMEZONE = pytz.timezone(get_config("TIMEZONE", "Europe/Bratislava"))

# ========== Trading Hours Settings ==========
TRADING_HOURS_FILTER = get_config("TRADING_HOURS_FILTER", "False") == "True"
HIGH_ACTIVITY_HOURS = [0, 1, 2, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22]
EUROPEAN_MARKET_HOURS = [8, 9, 10, 11, 12, 13, 14, 15, 16]
ASIAN_MARKET_HOURS = [0, 1, 2]
EVENING_HOURS = [17, 18, 19, 20, 21, 22]
WEEKEND_TRADING = get_config("WEEKEND_TRADING", "False") == "True"

# ========== Short-term Trading Optimizations ==========
SHORT_TERM_MODE = get_config("SHORT_TERM_MODE", "True") == "True"
MOMENTUM_LOOKBACK = int(get_config("MOMENTUM_LOOKBACK", 6))
VOLUME_SPIKE_THRESHOLD = float(get_config("VOLUME_SPIKE_THRESHOLD", 1.5))
BREAKOUT_DETECTION = get_config("BREAKOUT_DETECTION", "True") == "True"

# ========== Small Balance Filter Thresholds ==========
FILTER_THRESHOLDS = {
    "default": {"atr": 0.0025, "adx": 15.0, "bb": 0.007, "relax_factor": 1.0},
    "default_light": {"atr": 0.0018, "adx": 12.0, "bb": 0.005, "relax_factor": 0.9},
    "XRPUSDC": {"atr": 0.0016, "adx": 10.0, "bb": 0.004, "relax_factor": 0.85},
    "DOGEUSDC": {"atr": 0.0016, "adx": 10.0, "bb": 0.004, "relax_factor": 0.85},
    "ADAUSDC": {"atr": 0.0016, "adx": 10.0, "bb": 0.004, "relax_factor": 0.85},
    "MATICUSDC": {"atr": 0.0016, "adx": 10.0, "bb": 0.004, "relax_factor": 0.85},
    "DOTUSDC": {"atr": 0.0018, "adx": 12.0, "bb": 0.005, "relax_factor": 0.85},
}

# ========== Volatility Settings ==========
VOLATILITY_SKIP_ENABLED = get_config("VOLATILITY_SKIP_ENABLED", "True") == "True"
VOLATILITY_ATR_THRESHOLD = float(get_config("VOLATILITY_ATR_THRESHOLD", 0.0018))
VOLATILITY_RANGE_THRESHOLD = float(get_config("VOLATILITY_RANGE_THRESHOLD", 0.004))

# ========== Leverage Settings ==========
LEVERAGE_MAP = {
    "BTCUSDT": 5,
    "ETHUSDT": 5,
    "BTCUSDC": 5,
    "ETHUSDC": 5,
    "DOGEUSDC": 12,
    "XRPUSDC": 12,
    "ADAUSDC": 10,
    "SOLUSDC": 6,
    "BNBUSDC": 5,
    "LINKUSDC": 8,
    "ARBUSDC": 6,
    "SUIUSDC": 6,
    "MATICUSDC": 10,
    "DOTUSDC": 8,
}

# ========== Daily Goal Tracking ==========
TRACK_DAILY_TRADE_TARGET = get_config("TRACK_DAILY_TRADE_TARGET", "True") == "True"
DAILY_TRADE_TARGET = int(get_config("DAILY_TRADE_TARGET", 9))
DAILY_PROFIT_TARGET = float(get_config("DAILY_PROFIT_TARGET", 10.0))
WEEKLY_PROFIT_TARGET = float(get_config("WEEKLY_PROFIT_TARGET", 55.0))

# ========== Runtime State ==========
trade_stats_lock = Lock()
trade_stats = {
    "total": 0,
    "wins": 0,
    "losses": 0,
    "pnl": 0.0,
    "streak_loss": 0,
    "streak_win": 0,
    "initial_balance": 0,
    "deposits_today": 0,
    "deposits_week": 0,
    "withdrawals": 0,
    "api_errors": 0,
}


def initialize_risk_percent():
    """
    Legacy fallback: sets RISK_PERCENT to a fixed 0.03
    (not used in the new architecture).
    """
    global RISK_PERCENT

    RISK_PERCENT = 0.03
    log(f"[LegacyInit] RISK_PERCENT set to {RISK_PERCENT*100:.1f}%", level="DEBUG")
