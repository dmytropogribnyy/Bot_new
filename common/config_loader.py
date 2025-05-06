# common/config_loader.py (optimized for small deposits)
import os
from pathlib import Path
from threading import Lock

import pytz
from dotenv import load_dotenv

# Load environment variables
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
TELEGRAM_TOKEN = get_config("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = get_config("TELEGRAM_CHAT_ID")

# ========== Paths and Files ==========
# Match paths exactly as in the original config.py
# In config_loader.py, add or update this line in the Paths and Files section:
CONFIG_FILE = get_config("CONFIG_FILE", "C:/Bots/BinanceBot/common/config_loader.py")
EXPORT_PATH = get_config("EXPORT_PATH", "C:/Bots/BinanceBot/data/tp_performance.csv")
TP_LOG_FILE = get_config("TP_LOG_FILE", "C:/Bots/BinanceBot/data/tp_performance.csv")
LOG_FILE_PATH = get_config("LOG_FILE_PATH", "C:/Bots/BinanceBot/logs/main.log")
LOG_LEVEL = get_config("LOG_LEVEL", "INFO")
if not Path(TP_LOG_FILE).exists():
    print(f"Warning: TP_LOG_FILE not found at: {TP_LOG_FILE}")
else:
    print(f"TP_LOG_FILE found at: {TP_LOG_FILE}")

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

# Priority symbols for small deposits - low price, good volatility
PRIORITY_SMALL_BALANCE_PAIRS = [
    "XRP/USDC",  # Low price, high liquidity
    "DOGE/USDC",  # Low price, good volatility
    "ADA/USDC",  # Low price, steady volatility
    "SOL/USDC",  # Medium price, good volume
]

SYMBOLS_ACTIVE = get_config("SYMBOLS_ACTIVE", "").split(",") if get_config("SYMBOLS_ACTIVE") else USDC_SYMBOLS
FIXED_PAIRS = get_config("FIXED_PAIRS", "").split(",") if get_config("FIXED_PAIRS") else []
MAX_DYNAMIC_PAIRS = int(get_config("MAX_DYNAMIC_PAIRS", 10))
MIN_DYNAMIC_PAIRS = int(get_config("MIN_DYNAMIC_PAIRS", 5))

# ========== Risk Management ==========
RISK_PERCENT = None  # Will be set dynamically
MAX_POSITIONS = int(get_config("MAX_POSITIONS", 3))
MAX_OPEN_ORDERS = int(get_config("MAX_OPEN_ORDERS", 5))
MAX_MARGIN_PERCENT = float(get_config("MAX_MARGIN_PERCENT", 0.2))
MIN_NOTIONAL_OPEN = float(get_config("MIN_NOTIONAL_OPEN", 20))
MIN_NOTIONAL_ORDER = float(get_config("MIN_NOTIONAL_ORDER", 20))

# ========== TP/SL Settings ==========
TP1_PERCENT = float(get_config("TP1_PERCENT", 0.007))  # 0.7%
TP2_PERCENT = float(get_config("TP2_PERCENT", 0.013))  # 1.3%
SL_PERCENT = float(get_config("SL_PERCENT", 0.01))  # 1.0%
TP1_SHARE = float(get_config("TP1_SHARE", 0.7))
TP2_SHARE = float(get_config("TP2_SHARE", 0.3))

# ========== Fee Rates ==========
TAKER_FEE_RATE = float(get_config("TAKER_FEE_RATE", 0.0005))  # 0.05%
MAKER_FEE_RATE = float(get_config("MAKER_FEE_RATE", 0.0002))  # 0.02%

# ========== Strategy Settings ==========
USE_HTF_CONFIRMATION = get_config("USE_HTF_CONFIRMATION", "False") == "True"
ADAPTIVE_SCORE_ENABLED = get_config("ADAPTIVE_SCORE_ENABLED", "True") == "True"
AGGRESSIVENESS_THRESHOLD = float(get_config("AGGRESSIVENESS_THRESHOLD", 0.6))
SCORE_WEIGHTS = {"RSI": 2.0, "MACD_RSI": 2.0, "MACD_EMA": 2.0, "HTF": 1.0, "VOLUME": 1.0}

# ========== Auto TP/SL Adjustments ==========
AUTO_TP_SL_ENABLED = get_config("AUTO_TP_SL_ENABLED", "True") == "True"
FLAT_ADJUSTMENT = float(get_config("FLAT_ADJUSTMENT", 0.7))
TREND_ADJUSTMENT = float(get_config("TREND_ADJUSTMENT", 1.3))
ADX_TREND_THRESHOLD = float(get_config("ADX_TREND_THRESHOLD", 20))
ADX_FLAT_THRESHOLD = float(get_config("ADX_FLAT_THRESHOLD", 15))

# ========== Exit Strategies ==========
ENABLE_TRAILING = get_config("ENABLE_TRAILING", "True") == "True"
ENABLE_BREAKEVEN = get_config("ENABLE_BREAKEVEN", "True") == "True"
BREAKEVEN_TRIGGER = float(get_config("BREAKEVEN_TRIGGER", 0.5))
SOFT_EXIT_ENABLED = get_config("SOFT_EXIT_ENABLED", "True") == "True"
SOFT_EXIT_SHARE = float(get_config("SOFT_EXIT_SHARE", 0.5))
SOFT_EXIT_THRESHOLD = float(get_config("SOFT_EXIT_THRESHOLD", 0.8))

# ========== Signal Strength Control ==========
# Moved this section earlier to prevent import errors
MIN_TRADE_SCORE = int(get_config("MIN_TRADE_SCORE", 0))
SCORE_BASED_RISK = get_config("SCORE_BASED_RISK", "True") == "True"
SCORE_BASED_TP = get_config("SCORE_BASED_TP", "True") == "True"

# ========== Monitoring Settings ==========
IP_MONITOR_INTERVAL_SECONDS = int(get_config("IP_MONITOR_INTERVAL_SECONDS", 180))
ROUTER_REBOOT_MODE_TIMEOUT_MINUTES = int(get_config("ROUTER_REBOOT_MODE_TIMEOUT_MINUTES", 30))

# ========== ML TP Optimization ==========
TP_ML_MIN_TRADES_INITIAL = int(get_config("TP_ML_MIN_TRADES_INITIAL", 12))
TP_ML_MIN_TRADES_FULL = int(get_config("TP_ML_MIN_TRADES_FULL", 20))
TP_ML_SWITCH_THRESHOLD = float(get_config("TP_ML_SWITCH_THRESHOLD", 0.05))

# ========== Safety and Margin Buffer ==========
MARGIN_SAFETY_BUFFER = float(get_config("MARGIN_SAFETY_BUFFER", 0.9))  # Use 90% of available margin

# ========== Timezone Settings ==========
TIMEZONE = pytz.timezone(get_config("TIMEZONE", "Europe/Bratislava"))

# ========== Small Balance Filter Thresholds ==========
# Enhanced filter thresholds for small deposits (less strict to allow more trades)
FILTER_THRESHOLDS = {
    "default": {"atr": 0.0025, "adx": 15.0, "bb": 0.007, "relax_factor": 1.0},
    "default_light": {"atr": 0.002, "adx": 13.0, "bb": 0.006, "relax_factor": 0.9},  # Less strict for small accounts
    "XRPUSDC": {"atr": 0.0018, "adx": 12.0, "bb": 0.005, "relax_factor": 0.8},  # Optimized for XRP
    "DOGEUSDC": {"atr": 0.0018, "adx": 12.0, "bb": 0.005, "relax_factor": 0.8},  # Optimized for DOGE
    "ADAUSDC": {"atr": 0.0018, "adx": 12.0, "bb": 0.005, "relax_factor": 0.8},  # Optimized for ADA
}

# ========== Volatility Settings ==========
VOLATILITY_SKIP_ENABLED = get_config("VOLATILITY_SKIP_ENABLED", "True") == "True"
VOLATILITY_ATR_THRESHOLD = float(get_config("VOLATILITY_ATR_THRESHOLD", 0.002))  # Lower for small accounts
VOLATILITY_RANGE_THRESHOLD = float(get_config("VOLATILITY_RANGE_THRESHOLD", 0.005))  # Lower for small accounts

# ========== Leverage Settings ==========
LEVERAGE_MAP = {
    "BTCUSDT": 5,
    "ETHUSDT": 5,
    "BTCUSDC": 5,
    "ETHUSDC": 5,
    "DOGEUSDC": 10,  # Higher leverage for small price pairs
    "XRPUSDC": 10,  # Higher leverage for small price pairs
    "ADAUSDC": 10,  # Higher leverage for small price pairs
    "SOLUSDC": 5,
    "BNBUSDC": 5,
    "LINKUSDC": 5,
    "ARBUSDC": 5,
    "SUIUSDC": 5,
}

# ========== Runtime State ==========
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


# ========== Risk Management Functions ==========
def get_adaptive_risk_percent(balance):
    """Return appropriate risk percentage based on account size.
    Optimized for small deposits with a progressive scale."""
    if balance < 100:
        return 0.02  # 2% for ultra-small accounts (more aggressive for quick results)
    elif balance < 150:
        return 0.025  # 2.5% for small accounts
    elif balance < 300:
        return 0.03  # 3% for medium accounts
    else:
        return 0.04  # 4% for larger accounts (less than 5% to stay conservative)


def get_max_positions(balance):
    """Return maximum number of positions based on account size.
    Allow multiple positions even for smaller accounts for faster testing."""
    if balance < 100:
        return 2  # Allow 2 positions for ultra-small accounts for faster testing
    elif balance < 150:
        return 3  # More positions for small accounts
    elif balance < 300:
        return 4  # Even more for medium accounts
    else:
        return 5  # Max for large accounts


def initialize_risk_percent():
    """Initialize RISK_PERCENT based on current balance."""
    global RISK_PERCENT
    from utils_core import get_cached_balance

    balance = get_cached_balance() or 100
    RISK_PERCENT = get_adaptive_risk_percent(balance)


def get_min_net_profit(balance):
    """Get minimum acceptable net profit based on balance.
    Lower thresholds for small accounts to enable more trades."""
    if balance < 100:
        return 0.15  # Very small min profit for ultra-small accounts
    elif balance < 150:
        return 0.2  # Small min profit for small accounts
    elif balance < 300:
        return 0.3  # Medium min profit for medium accounts
    else:
        return 0.5  # Higher requirements for larger accounts


def get_adaptive_score_threshold(balance):
    """Get minimum signal score threshold based on account size.
    Lower for smaller accounts to enable more trades."""
    if balance < 100:
        return 2.7  # Lower threshold for ultra-small accounts
    elif balance < 150:
        return 3.0  # Medium threshold for small accounts
    elif balance < 300:
        return 3.2  # Higher threshold for medium accounts
    else:
        return 3.5  # Very high threshold for large accounts


def get_priority_pairs(balance):
    """Get appropriate trading pairs based on account size."""
    if balance < 150:
        # For small accounts, focus on low-price, higher volatility pairs
        return PRIORITY_SMALL_BALANCE_PAIRS
    else:
        # For larger accounts, use full symbol list
        return USDC_SYMBOLS
