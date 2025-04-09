import os
from threading import Lock

import ccxt
import pytz
from dotenv import load_dotenv

load_dotenv()

# --- API & Auth ---
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ALLOWED_USER_ID = 383821734

# --- Timezone & Paths ---
TIMEZONE = pytz.timezone("Europe/Bratislava")
LOG_FILE_PATH = "telegram_log.txt"
EXPORT_PATH = "data/tp_performance.csv"
TP_LOG_FILE = "data/tp_performance.csv"

# --- Logging ---
LOG_LEVEL = "INFO"  # Уровень логирования: "INFO", "DEBUG", "ERROR"
LOG_SCORE_EVERYWHERE = False  # NEW: Allow score logging in REAL_RUN if True

# --- Symbols & Leverage (fallback) ---
SYMBOLS_ACTIVE = [
    "DOGE/USDC",
    "BTC/USDC",
    "ETH/USDC",
    "BNB/USDC",
    "ADA/USDC",
    "XRP/USDC",
    "SOL/USDC",
    "SUI/USDC",
    "LINK/USDC",
    "ARB/USDC",
]

FIXED_PAIRS = ["BTC/USDC", "ETH/USDC", "XRP/USDC", "ADA/USDC", "SOL/USDC"]
MAX_DYNAMIC_PAIRS = 30
MIN_DYNAMIC_PAIRS = 15

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
TP1_PERCENT = 0.007
TP2_PERCENT = 0.013
TP1_SHARE = 0.7
TP2_SHARE = 0.3
SL_PERCENT = 0.01

# --- Risk Management ---
AGGRESSIVENESS_THRESHOLD = 0.6  # Порог для определения AGGRESSIVE режима
AGGRESSIVE_THRESHOLD = 50
SAFE_THRESHOLD = 10
MIN_NOTIONAL = 5
MAX_HOLD_MINUTES = 90
RISK_DRAWDOWN_THRESHOLD = 5.0

# --- Entry Filter Thresholds (fallback / default) ---
ATR_THRESHOLD = 0.0015
ADX_THRESHOLD = 7
BB_WIDTH_THRESHOLD = 0.008

# --- Volatility Filter ---
VOLATILITY_SKIP_ENABLED = True
VOLATILITY_ATR_THRESHOLD = 0.0012
VOLATILITY_RANGE_THRESHOLD = 0.015
DRY_RUN_VOLATILITY_ATR_THRESHOLD = 0.0025
DRY_RUN_VOLATILITY_RANGE_THRESHOLD = 0.0075

# --- Daily Loss Protection ---
DAILY_PROTECTION_ENABLED = True
SAFE_TRIGGER_THRESHOLD = 0.10
FULL_STOP_THRESHOLD = 0.05

# --- Strategy Toggles ---
ENABLE_TRAILING = True
TRAILING_PERCENT = 0.02
ENABLE_BREAKEVEN = True
BREAKEVEN_TRIGGER = 0.5

# --- Signal Strength Control ---
MIN_TRADE_SCORE = 2
SCORE_BASED_RISK = True
SCORE_BASED_TP = True

SCORE_WEIGHTS = {
    "RSI": 1.0,
    "MACD_RSI": 1.0,
    "MACD_EMA": 1.0,
    "HTF": 1.0,
    "VOLUME": 0.5,
}

# --- Mode & Debug ---
DRY_RUN = True
VERBOSE = DRY_RUN
USE_DYNAMIC_IN_DRY_RUN = True
ADAPTIVE_SCORE_ENABLED = True

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

# --- Exchange ---
exchange = ccxt.binance(
    {
        "apiKey": API_KEY,
        "secret": API_SECRET,
        "enableRateLimit": True,
        "options": {
            "defaultType": "future",
            "adjustForTimeDifference": True,
        },
        "urls": {
            "api": {
                "public": "https://fapi.binance.com/fapi/v1",
                "private": "https://fapi.binance.com/fapi/v1",
            }
        },
    }
)

# --- Auto-learned Entry Filter Thresholds ---
FILTER_THRESHOLDS = {
    "default": {"atr": 0.0015, "adx": 7, "bb": 0.008},  # Для депозита ≥ 100 USDC
    "default_light": {"atr": 0.001, "adx": 5, "bb": 0.006},  # Для депозита < 100 USDC
    "BTC/USDC": {"atr": 0.002, "adx": 10, "bb": 0.01},
    "DOGE/USDC": {"atr": 0.0015, "adx": 7, "bb": 0.008},
    "ETH/USDC": {"atr": 0.0015, "adx": 7, "bb": 0.008},
    "BNB/USDC": {"atr": 0.0015, "adx": 7, "bb": 0.008},
    "ADA/USDC": {"atr": 0.0015, "adx": 7, "bb": 0.008},
    "XRP/USDC": {"atr": 0.0015, "adx": 7, "bb": 0.008},
    "SOL/USDC": {"atr": 0.0015, "adx": 7, "bb": 0.008},
    "SUI/USDC": {"atr": 0.0015, "adx": 7, "bb": 0.008},
    "LINK/USDC": {"atr": 0.0015, "adx": 7, "bb": 0.008},
    "ARB/USDC": {"atr": 0.0015, "adx": 7, "bb": 0.008},
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

# --- Config File ---
CONFIG_FILE = "config.py"
