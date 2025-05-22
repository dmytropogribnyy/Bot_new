# config.py
import os
from pathlib import Path
from threading import Lock

import pytz
from dotenv import load_dotenv

load_dotenv()

# API keys
USE_TESTNET = True
API_KEY = os.getenv("API_KEY_TESTNET" if USE_TESTNET else "API_KEY")
API_SECRET = os.getenv("API_SECRET_TESTNET" if USE_TESTNET else "API_SECRET")

# Торговые пары
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
SYMBOLS_ACTIVE = USDT_SYMBOLS if USE_TESTNET else USDC_SYMBOLS
FIXED_PAIRS = SYMBOLS_ACTIVE
MAX_DYNAMIC_PAIRS = 0
MIN_DYNAMIC_PAIRS = 0


# Risk management (RISK_PERCENT will be set later)
def get_adaptive_risk_percent(balance):
    if balance < 100:
        return 0.025  # Микробаланс
    elif balance < 300:
        return 0.03  # Малый счёт
    elif balance < 600:
        return 0.025  # Средний
    elif balance < 1000:
        return 0.02  # Крупный
    else:
        return 0.015  # Очень крупный


# Delay RISK_PERCENT calculation until after imports
RISK_PERCENT = None  # Will be set by initialize_risk_percent()


def initialize_risk_percent():
    global RISK_PERCENT
    from utils_core import get_cached_balance

    balance = get_cached_balance() or 100
    RISK_PERCENT = get_adaptive_risk_percent(balance)


MAX_POSITIONS = 3
MIN_NOTIONAL_OPEN = 20
MIN_NOTIONAL_ORDER = 20
MAX_MARGIN_PERCENT = 0.2
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ALLOWED_USER_ID = 383821734

# Timezone & Paths
TIMEZONE = pytz.timezone("Europe/Bratislava")
LOG_FILE_PATH = str(Path("c:/Bots/BinanceBot/telegram_log.txt"))
EXPORT_PATH = str(Path("c:/Bots/BinanceBot/data/tp_performance.csv"))
TP_LOG_FILE = str(Path("c:/Bots/BinanceBot/data/tp_performance.csv"))
if not Path(TP_LOG_FILE).exists():
    raise FileNotFoundError(f"TP_LOG_FILE not found at: {TP_LOG_FILE}")
else:
    print(f"TP_LOG_FILE found at: {TP_LOG_FILE}")

# Logging
LOG_LEVEL = "DEBUG"
LOG_SCORE_EVERYWHERE = False

# Mode & Debug
DRY_RUN = False
VERBOSE = True
USE_DYNAMIC_IN_DRY_RUN = True
ADAPTIVE_SCORE_ENABLED = True

# Leverage
if USE_TESTNET:
    LEVERAGE_MAP = {"BTCUSDT": 2}
else:
    LEVERAGE_MAP = {sym.replace("/", ""): 2 for sym in USDC_SYMBOLS}

# TP / SL Strategy
TP1_SHARE = 0.7
TP2_SHARE = 0.3
TP1_PERCENT = 0.002
TP2_PERCENT = 0.003
SL_PERCENT = 0.002
SOFT_EXIT_THRESHOLD = 0.8

# Фильтры
if USE_TESTNET:
    FILTER_THRESHOLDS = {"BTCUSDT": {"atr": 0.0001, "adx": 7, "bb": 0.0015}}
else:
    FILTER_THRESHOLDS = {sym.replace("/", ""): {"atr": 0.00002, "adx": 0.1, "bb": 0.0002} for sym in USDC_SYMBOLS}

# Volatility Filter
VOLATILITY_SKIP_ENABLED = False
VOLATILITY_ATR_THRESHOLD = 0.00005
VOLATILITY_RANGE_THRESHOLD = 0.0005
DRY_RUN_VOLATILITY_ATR_THRESHOLD = 0.0025
DRY_RUN_VOLATILITY_RANGE_THRESHOLD = 0.0075

# Daily Loss Protection
DAILY_PROTECTION_ENABLED = True
SAFE_TRIGGER_THRESHOLD = 0.10
FULL_STOP_THRESHOLD = 0.05

# Strategy Toggles
ENABLE_TRAILING = True
TRAILING_PERCENT = 0.02
ENABLE_BREAKEVEN = True
BREAKEVEN_TRIGGER = 0.5
SOFT_EXIT_ENABLED = True
SOFT_EXIT_SHARE = 0.5

# Auto TP/SL Adjustments
AUTO_TP_SL_ENABLED = True
FLAT_ADJUSTMENT = 0.7
TREND_ADJUSTMENT = 1.3
ADX_TREND_THRESHOLD = 20
ADX_FLAT_THRESHOLD = 15

# Signal Strength Control
MIN_TRADE_SCORE = 0
SCORE_BASED_RISK = True
SCORE_BASED_TP = True
SCORE_WEIGHTS = {"RSI": 2.0, "MACD_RSI": 2.0, "MACD_EMA": 2.0, "HTF": 1.0, "VOLUME": 1.0}

# Runtime Control
RUNNING = True

# Runtime Trade Stats
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

# IP Monitoring
ROUTER_REBOOT_MODE_TIMEOUT_MINUTES = 30
IP_MONITOR_INTERVAL_SECONDS = 180

# Symbol Rotation
UPDATE_INTERVAL_SECONDS = 60 * 60

# ML TP Optimization
TP_ML_MIN_TRADES_INITIAL = 12
TP_ML_MIN_TRADES_FULL = 20
TP_ML_THRESHOLD = 0.05
TP_ML_SWITCH_THRESHOLD = 0.05

# Fees & Profit
TAKER_FEE_RATE = 0.0001
MIN_NET_PROFIT = {50: 0.1, 100: 0.1, 500: 0.1, "max": 0.1}


def get_min_net_profit(balance):
    for threshold in sorted(k for k in MIN_NET_PROFIT if k != "max"):
        if balance <= threshold:
            return MIN_NET_PROFIT[threshold]
    return MIN_NET_PROFIT["max"]


# Config File
CONFIG_FILE = "config.py"
