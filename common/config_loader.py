# common/config_loader.py (optimized for short-term trading with small deposits)
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
# We'll keep these for reference but will use dynamic selection
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

# Priority symbols for small deposits - expanded with more low-price options
PRIORITY_SMALL_BALANCE_PAIRS = [
    "XRP/USDC",  # Low price, high liquidity
    "DOGE/USDC",  # Low price, good volatility
    "ADA/USDC",  # Low price, steady volatility
    "SOL/USDC",  # Medium price, good volume
    "MATIC/USDC",  # Added: Low price, high liquidity
    "DOT/USDC",  # Added: Good volatility profile
]

# Symbol selection will be dynamic, but these serve as fallback
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
# Optimized for small deposits with better risk/reward
TP1_PERCENT = float(get_config("TP1_PERCENT", 0.009))  # 0.9% (increased from 0.6%)
TP2_PERCENT = float(get_config("TP2_PERCENT", 0.016))  # 1.6% (increased from 1.3%)
SL_PERCENT = float(get_config("SL_PERCENT", 0.007))  # 0.7% (decreased from 0.9%)
TP1_SHARE = float(get_config("TP1_SHARE", 0.8))  # 80% (unchanged)
TP2_SHARE = float(get_config("TP2_SHARE", 0.2))  # 20% (unchanged)

# ========== Fee Rates ==========
TAKER_FEE_RATE = float(get_config("TAKER_FEE_RATE", 0.0005))  # 0.05%
MAKER_FEE_RATE = float(get_config("MAKER_FEE_RATE", 0.0002))  # 0.02%

# ========== Strategy Settings ==========
USE_HTF_CONFIRMATION = get_config("USE_HTF_CONFIRMATION", "False") == "True"
ADAPTIVE_SCORE_ENABLED = get_config("ADAPTIVE_SCORE_ENABLED", "True") == "True"
AGGRESSIVENESS_THRESHOLD = float(get_config("AGGRESSIVENESS_THRESHOLD", 0.6))

# Enhanced scoring weights for short-term trading
SCORE_WEIGHTS = {
    "RSI": 2.0,  # Увеличено с 1.5
    "MACD_RSI": 2.5,  # Увеличено с 2.0
    "MACD_EMA": 2.5,  # Увеличено с 2.0
    "HTF": 0.5,  # Без изменений
    "VOLUME": 2.0,  # Увеличено с 1.5
    "EMA_CROSS": 3.0,  # Увеличено с 2.0
    "VOL_SPIKE": 2.5,  # Увеличено с 1.5
    "PRICE_ACTION": 2.5,  # Увеличено с 1.5
}

# ========== Auto TP/SL Adjustments ==========
AUTO_TP_SL_ENABLED = get_config("AUTO_TP_SL_ENABLED", "True") == "True"
FLAT_ADJUSTMENT = float(get_config("FLAT_ADJUSTMENT", 0.7))
TREND_ADJUSTMENT = float(get_config("TREND_ADJUSTMENT", 1.3))
ADX_TREND_THRESHOLD = float(get_config("ADX_TREND_THRESHOLD", 20))
ADX_FLAT_THRESHOLD = float(get_config("ADX_FLAT_THRESHOLD", 15))

# ========== Exit Strategies ==========
ENABLE_TRAILING = get_config("ENABLE_TRAILING", "True") == "True"
ENABLE_BREAKEVEN = get_config("ENABLE_BREAKEVEN", "True") == "True"
BREAKEVEN_TRIGGER = float(get_config("BREAKEVEN_TRIGGER", 0.4))  # Changed from 0.5 to 0.4 for earlier breakeven
SOFT_EXIT_ENABLED = get_config("SOFT_EXIT_ENABLED", "True") == "True"
SOFT_EXIT_THRESHOLD = float(get_config("SOFT_EXIT_THRESHOLD", 0.7))  # Changed from 0.8 to 0.7 for earlier profit taking
SOFT_EXIT_SHARE = float(get_config("SOFT_EXIT_SHARE", 0.5))

# ========== Signal Strength Control ==========
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
MARGIN_SAFETY_BUFFER = float(get_config("MARGIN_SAFETY_BUFFER", 0.92))  # Increased from 0.9 to 0.92

# ========== Timezone Settings ==========
TIMEZONE = pytz.timezone(get_config("TIMEZONE", "Europe/Bratislava"))

# ========== Trading Hours Settings ========== (New section)
TRADING_HOURS_FILTER = get_config("TRADING_HOURS_FILTER", "False") == "True"  # Enable/disable trading hours filter
HIGH_ACTIVITY_HOURS = [8, 9, 10, 11, 12, 13, 14, 15, 16, 20, 21, 22]  # UTC hours with highest market activity
WEEKEND_TRADING = get_config("WEEKEND_TRADING", "False") == "True"  # Disable trading on weekends

# ========== Short-term Trading Optimizations ========== (New section)
SHORT_TERM_MODE = get_config("SHORT_TERM_MODE", "True") == "True"  # Enable short-term focused trading
MOMENTUM_LOOKBACK = int(get_config("MOMENTUM_LOOKBACK", 6))  # Number of candles to check for momentum
VOLUME_SPIKE_THRESHOLD = float(get_config("VOLUME_SPIKE_THRESHOLD", 1.5))  # Volume increase to consider as spike
BREAKOUT_DETECTION = get_config("BREAKOUT_DETECTION", "True") == "True"  # Enable breakout detection

# ========== Small Balance Filter Thresholds ==========
# Adjusted for more opportunities in short-term trading
FILTER_THRESHOLDS = {
    "default": {"atr": 0.0025, "adx": 15.0, "bb": 0.007, "relax_factor": 1.0},
    "default_light": {"atr": 0.0018, "adx": 12.0, "bb": 0.005, "relax_factor": 0.9},  # Less strict for small accounts
    "XRPUSDC": {"atr": 0.0016, "adx": 10.0, "bb": 0.004, "relax_factor": 0.85},  # More permissive
    "DOGEUSDC": {"atr": 0.0016, "adx": 10.0, "bb": 0.004, "relax_factor": 0.85},  # More permissive
    "ADAUSDC": {"atr": 0.0016, "adx": 10.0, "bb": 0.004, "relax_factor": 0.85},  # More permissive
    "MATICUSDC": {"atr": 0.0016, "adx": 10.0, "bb": 0.004, "relax_factor": 0.85},  # Added for new pair
    "DOTUSDC": {"atr": 0.0018, "adx": 12.0, "bb": 0.005, "relax_factor": 0.85},  # Added for new pair
}

# ========== Volatility Settings ==========
VOLATILITY_SKIP_ENABLED = get_config("VOLATILITY_SKIP_ENABLED", "True") == "True"
VOLATILITY_ATR_THRESHOLD = float(get_config("VOLATILITY_ATR_THRESHOLD", 0.0018))  # Lowered from 0.002
VOLATILITY_RANGE_THRESHOLD = float(get_config("VOLATILITY_RANGE_THRESHOLD", 0.004))  # Lowered from 0.005

# ========== Leverage Settings ==========
# Added more assets with optimized leverage
LEVERAGE_MAP = {
    "BTCUSDT": 5,
    "ETHUSDT": 5,
    "BTCUSDC": 5,
    "ETHUSDC": 5,
    "DOGEUSDC": 12,  # Increased from 10 for better capital efficiency
    "XRPUSDC": 12,  # Increased from 10
    "ADAUSDC": 10,  # Unchanged
    "SOLUSDC": 6,  # Increased from 5
    "BNBUSDC": 5,  # Unchanged
    "LINKUSDC": 8,  # Increased from 5
    "ARBUSDC": 6,  # Increased from 5
    "SUIUSDC": 6,  # Increased from 5
    "MATICUSDC": 10,  # Added new pair
    "DOTUSDC": 8,  # Added new pair
}

# ========== Runtime State ==========
trade_stats_lock = Lock()
trade_stats = {
    "total": 0,
    "wins": 0,
    "losses": 0,
    "pnl": 0.0,
    "streak_loss": 0,
    "streak_win": 0,  # Added streak tracking for win streaks
    "initial_balance": 0,
    "deposits_today": 0,
    "deposits_week": 0,
    "withdrawals": 0,
    "api_errors": 0,
}


# ========== Risk Management Functions ==========
def get_adaptive_risk_percent(balance, win_streak=0):
    """Return appropriate risk percentage based on account size and recent performance.
    Optimized for small deposits with a progressive scale."""
    # Base risk based on account size
    if balance < 100:
        base_risk = 0.018  # 1.8% for ultra-small accounts (slightly reduced from 2%)
    elif balance < 150:
        base_risk = 0.022  # 2.2% for small accounts (slightly reduced from 2.5%)
    elif balance < 300:
        base_risk = 0.028  # 2.8% for medium accounts (slightly reduced from 3%)
    else:
        base_risk = 0.038  # 3.8% for larger accounts (slightly reduced from 4%)

    # Adjust based on recent performance
    win_streak_boost = min(win_streak * 0.002, 0.01)  # Up to +1% for win streaks

    # Cap final risk percentage
    return min(base_risk + win_streak_boost, 0.05)  # Cap at 5%


def get_max_positions(balance):
    """Return maximum number of positions based on account size.
    Allow multiple positions even for smaller accounts for faster testing."""
    if balance < 100:
        return 2  # Allow 2 positions for ultra-small accounts
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
    win_streak = trade_stats.get("streak_win", 0)
    RISK_PERCENT = get_adaptive_risk_percent(balance, win_streak)


def get_min_net_profit(balance):
    """Get minimum acceptable net profit based on balance.
    Lowered thresholds for small accounts to enable more trades."""
    if balance < 100:
        return 0.12  # Reduced from 0.15 to allow more trades for very small accounts
    elif balance < 150:
        return 0.18  # Reduced from 0.2 to allow more trades for small accounts
    elif balance < 300:
        return 0.25  # Reduced from 0.3
    else:
        return 0.4  # Reduced from 0.5


def get_adaptive_score_threshold(balance, market_volatility="normal"):
    """Get minimum signal score threshold based on account size and market conditions.
    Lower thresholds during high volatility periods."""
    # Base thresholds by account size
    if balance < 100:
        base_threshold = 2.7  # Lower threshold for ultra-small accounts
    elif balance < 150:
        base_threshold = 3.0  # Medium threshold for small accounts
    elif balance < 300:
        base_threshold = 3.2  # Higher threshold for medium accounts
    else:
        base_threshold = 3.5  # Very high threshold for larger accounts

    # Adjust for market volatility
    if market_volatility == "high":
        return max(base_threshold - 0.3, 2.3)  # More lenient in volatile markets
    elif market_volatility == "low":
        return base_threshold + 0.2  # More strict in low volatility

    return base_threshold


def get_priority_pairs(balance):
    """Get appropriate trading pairs based on account size."""
    if balance < 150:
        # For small accounts, focus on low-price, higher volatility pairs
        return PRIORITY_SMALL_BALANCE_PAIRS
    else:
        # For larger accounts, use full symbol list
        return USDC_SYMBOLS


# ========== ATR Multipliers for TP/SL ==========
def get_atr_multipliers(regime="neutral", score=3.0):
    """Return optimized ATR multipliers based on market regime and signal strength."""
    # Base multipliers for neutral market
    tp1_mult = 0.8  # Reduced from 1.0 for faster profit taking
    tp2_mult = 1.6  # Reduced from 2.0 for faster profit taking
    sl_mult = 1.2  # Reduced from 1.5 for better risk:reward

    # Adjust for market regime
    if regime == "trend":
        tp1_mult *= 1.1
        tp2_mult *= 1.2
        sl_mult *= 0.9  # Tighter stop in trending markets
    elif regime == "flat":
        tp1_mult *= 0.8
        tp2_mult *= 0.7
        sl_mult *= 0.8  # Tighter range in flat markets
    elif regime == "breakout":
        tp1_mult *= 1.2  # More aggressive targets in breakouts
        tp2_mult *= 1.3

    # Adjust for signal strength
    if score > 4.0:  # Strong signals get more room
        tp2_mult *= 1.2
        sl_mult *= 0.9  # Tighter stop for high conviction
    elif score < 3.0:  # Weak signals get tighter targets
        tp1_mult *= 0.9
        tp2_mult *= 0.8

    return tp1_mult, tp2_mult, sl_mult


# ========== Adaptive Leverage Function ==========
def get_adaptive_leverage(symbol, volatility_ratio=1.0, balance=None):
    """Determines optimal leverage for a pair based on current volatility and account size.

    Args:
        symbol: Trading pair (normalized format without '/')
        volatility_ratio: Ratio of current volatility to average (>1 = higher than average)
        balance: Current account balance

    Returns:
        Optimized leverage value
    """
    # Base leverage from configuration
    base_leverage = LEVERAGE_MAP.get(symbol, 5)

    # Adjust for volatility (inverse relationship)
    vol_adjustment = 1 / volatility_ratio if volatility_ratio > 0 else 1

    # Adjust for account size (higher leverage for small deposits)
    if balance and balance < 150:
        balance_factor = 1.2  # +20% for small deposits
    else:
        balance_factor = 1.0

    # Calculate final leverage with constraints
    adjusted_leverage = base_leverage * vol_adjustment * balance_factor

    # Constrain to reasonable limits
    min_leverage = 3
    max_leverage = 20

    return max(min_leverage, min(round(adjusted_leverage), max_leverage))
