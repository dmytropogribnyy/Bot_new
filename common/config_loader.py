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

# ========== Micro-Trade Optimization ==========
# Updated: Extended timeout for micro trades to capture more opportunities
MICRO_TRADE_TIMEOUT_MINUTES = int(get_config("MICRO_TRADE_TIMEOUT_MINUTES", 240))  # Increased from 45 to 240 minutes
MICRO_TRADE_SIZE_THRESHOLD = float(get_config("MICRO_TRADE_SIZE_THRESHOLD", 0.15))
MICRO_PROFIT_THRESHOLD = float(get_config("MICRO_PROFIT_THRESHOLD", 0.3))
MICRO_PROFIT_ENABLED = get_config("MICRO_PROFIT_ENABLED", "True") == "True"

# ========== Pair Rotation Optimization ==========
MISSED_OPPORTUNITIES_FILE = get_config("MISSED_OPPORTUNITIES_FILE", "data/missed_opportunities.json")
PAIR_COOLING_PERIOD_HOURS = int(get_config("PAIR_COOLING_PERIOD_HOURS", 24))
PAIR_ROTATION_MIN_INTERVAL = int(get_config("PAIR_ROTATION_MIN_INTERVAL", 600))

# ========== Risk Management ==========
RISK_PERCENT = None  # Will be set dynamically
MAX_POSITIONS = int(get_config("MAX_POSITIONS", 3))
MAX_OPEN_ORDERS = int(get_config("MAX_OPEN_ORDERS", 5))
MAX_MARGIN_PERCENT = float(get_config("MAX_MARGIN_PERCENT", 0.2))
MIN_NOTIONAL_OPEN = float(get_config("MIN_NOTIONAL_OPEN", 20))
MIN_NOTIONAL_ORDER = float(get_config("MIN_NOTIONAL_ORDER", 20))

# ========== TP/SL Settings ==========
# Optimized for 15-minute timeframe with better risk/reward
TP1_PERCENT = float(get_config("TP1_PERCENT", 0.008))  # Updated to 0.8% from 0.9%
TP2_PERCENT = float(get_config("TP2_PERCENT", 0.016))  # Unchanged at 1.6%
SL_PERCENT = float(get_config("SL_PERCENT", 0.007))  # Unchanged at 0.7%
TP1_SHARE = float(get_config("TP1_SHARE", 0.8))  # Unchanged at 80%
TP2_SHARE = float(get_config("TP2_SHARE", 0.2))  # Unchanged at 20%

# ========== Auto-Profit Settings ==========
AUTO_CLOSE_PROFIT_THRESHOLD = 5.0
BONUS_PROFIT_THRESHOLD = 7.0

# ========== Fee Rates ==========
TAKER_FEE_RATE = float(get_config("TAKER_FEE_RATE", 0.0005))
MAKER_FEE_RATE = float(get_config("MAKER_FEE_RATE", 0.0002))

# ========== Strategy Settings ==========
USE_HTF_CONFIRMATION = get_config("USE_HTF_CONFIRMATION", "False") == "True"
ADAPTIVE_SCORE_ENABLED = get_config("ADAPTIVE_SCORE_ENABLED", "True") == "True"
AGGRESSIVENESS_THRESHOLD = float(get_config("AGGRESSIVENESS_THRESHOLD", 0.6))

# Enhanced scoring weights for short-term trading
SCORE_WEIGHTS = {
    "RSI": 2.0,
    "MACD_RSI": 2.5,
    "MACD_EMA": 2.5,
    "HTF": 0.5,
    "VOLUME": 2.0,
    "EMA_CROSS": 3.0,
    "VOL_SPIKE": 2.5,
    "PRICE_ACTION": 2.5,
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
BREAKEVEN_TRIGGER = float(get_config("BREAKEVEN_TRIGGER", 0.30))  # Updated to 0.30 from 0.40
SOFT_EXIT_ENABLED = get_config("SOFT_EXIT_ENABLED", "True") == "True"
SOFT_EXIT_THRESHOLD = float(get_config("SOFT_EXIT_THRESHOLD", 0.7))
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
MARGIN_SAFETY_BUFFER = float(get_config("MARGIN_SAFETY_BUFFER", 0.92))

# ========== Timezone Settings ==========
TIMEZONE = pytz.timezone(get_config("TIMEZONE", "Europe/Bratislava"))

# ========== Trading Hours Settings ==========
TRADING_HOURS_FILTER = get_config("TRADING_HOURS_FILTER", "False") == "True"
HIGH_ACTIVITY_HOURS = [8, 9, 10, 11, 12, 13, 14, 15, 16, 20, 21, 22]
WEEKEND_TRADING = get_config("WEEKEND_TRADING", "False") == "True"

# ========== Short-term Trading Optimizations ==========
SHORT_TERM_MODE = get_config("SHORT_TERM_MODE", "True") == "True"
MOMENTUM_LOOKBACK = int(get_config("MOMENTUM_LOOKBACK", 6))
VOLUME_SPIKE_THRESHOLD = float(get_config("VOLUME_SPIKE_THRESHOLD", 1.5))
BREAKOUT_DETECTION = get_config("BREAKOUT_DETECTION", "True") == "True"

# ========== Small Balance Filter Thresholds ==========
# Will be enhanced by dynamic_filters.py but kept for compatibility
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
# New constants for goal tracking
TRACK_DAILY_TRADE_TARGET = get_config("TRACK_DAILY_TRADE_TARGET", "True") == "True"
DAILY_TRADE_TARGET = int(get_config("DAILY_TRADE_TARGET", 9))  # Target 9 trades per day
DAILY_PROFIT_TARGET = float(get_config("DAILY_PROFIT_TARGET", 10.0))  # Target 10 USDC profit per day
WEEKLY_PROFIT_TARGET = float(get_config("WEEKLY_PROFIT_TARGET", 55.0))  # Target 55 USDC profit per week

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


# ========== Risk Management Functions ==========
# Note: The enhanced version will be in risk_utils.py, but maintaining compatibility here
def get_adaptive_risk_percent(balance, win_streak=0):
    """Return appropriate risk percentage based on account size and recent performance.
    Optimized for small deposits with a progressive scale.

    Note: This is the legacy version. The enhanced version is in risk_utils.py.
    """
    log("Using legacy get_adaptive_risk_percent. Consider using the enhanced version in risk_utils.py", level="DEBUG")

    # Import the enhanced version from risk_utils
    try:
        from core.risk_utils import get_adaptive_risk_percent as enhanced_risk_calc

        return enhanced_risk_calc(balance, win_streak=win_streak)
    except ImportError as e:
        log(f"Could not import enhanced risk calculator: {e}", level="DEBUG")
        # Fall back to legacy implementation
        # Base risk based on account size
        if balance < 100:
            base_risk = 0.018
        elif balance < 150:
            base_risk = 0.022
        elif balance < 300:
            base_risk = 0.028
        else:
            base_risk = 0.038

        # Adjust based on recent performance
        win_streak_boost = min(win_streak * 0.002, 0.01)

        # Cap final risk percentage
        return min(base_risk + win_streak_boost, 0.05)


def get_max_positions(balance):
    """Return maximum number of positions based on account size."""
    if balance < 100:
        return 2
    elif balance < 150:
        return 2  # Updated: Limit to 2 positions for <150 USDC
    elif balance < 300:
        return 3  # Limited to 3 for better risk management
    else:
        return 4  # Limited to 4 for better risk management


def initialize_risk_percent():
    """Initialize RISK_PERCENT based on current balance."""
    global RISK_PERCENT
    from utils_core import get_cached_balance

    balance = get_cached_balance() or 100
    win_streak = trade_stats.get("streak_win", 0)

    # Try to use the enhanced version from risk_utils
    try:
        from core.risk_utils import get_adaptive_risk_percent as risk_calc
    except ImportError as e:
        log(f"Could not import enhanced risk calculator: {e}", level="DEBUG")
        risk_calc = get_adaptive_risk_percent

    RISK_PERCENT = risk_calc(balance, win_streak=win_streak)


def get_min_net_profit(balance):
    """Get minimum acceptable net profit based on balance."""
    if balance < 100:
        return 0.12
    elif balance < 150:
        return 0.18
    elif balance < 300:
        return 0.25
    else:
        return 0.4


def get_adaptive_score_threshold(balance, market_volatility="normal"):
    """Get minimum signal score threshold based on account size and market conditions."""
    # Base thresholds by account size
    if balance < 100:
        base_threshold = 2.7
    elif balance < 150:
        base_threshold = 3.0
    elif balance < 300:
        base_threshold = 3.2
    else:
        base_threshold = 3.5

    # Adjust for market volatility
    if market_volatility == "high":
        return max(base_threshold - 0.3, 2.3)
    elif market_volatility == "low":
        return base_threshold + 0.2

    return base_threshold


def get_priority_pairs(balance):
    """Get appropriate trading pairs based on account size."""
    if balance < 150:
        return PRIORITY_SMALL_BALANCE_PAIRS
    else:
        return USDC_SYMBOLS


def get_atr_multipliers(regime="neutral", score=3.0):
    """Return optimized ATR multipliers based on market regime and signal strength."""
    # Base multipliers for neutral market
    tp1_mult = 0.8
    tp2_mult = 1.6
    sl_mult = 1.2

    # Adjust for market regime
    if regime == "trend":
        tp1_mult *= 1.1
        tp2_mult *= 1.2
        sl_mult *= 0.9
    elif regime == "flat":
        tp1_mult *= 0.8
        tp2_mult *= 0.7
        sl_mult *= 0.8
    elif regime == "breakout":
        tp1_mult *= 1.2
        tp2_mult *= 1.3

    # Adjust for signal strength
    if score > 4.0:
        tp2_mult *= 1.2
        sl_mult *= 0.9
    elif score < 3.0:
        tp1_mult *= 0.9
        tp2_mult *= 0.8

    return tp1_mult, tp2_mult, sl_mult


def get_adaptive_leverage(symbol, volatility_ratio=1.0, balance=None, market_regime=None):
    """
    Determines optimal leverage with strong safety constraints

    Args:
        symbol: Trading pair (normalized format without '/')
        volatility_ratio: Ratio of current volatility to average (>1 = higher than average)
        balance: Current account balance
        market_regime: Current market regime (optional)

    Returns:
        Optimized leverage value
    """
    # Import here to avoid circular imports
    try:
        from stats import get_performance_stats

        # Base leverage from configuration
        base_leverage = LEVERAGE_MAP.get(symbol, 5)

        # Get balance if not provided
        if balance is None:
            from utils_core import get_cached_balance

            balance = get_cached_balance()

        # Conservative adjustment for micro-deposits
        if balance and balance < 150:
            balance_factor = 1.2  # +20% for small deposits for more efficient capital use
        else:
            balance_factor = 1.0

        # Market regime adjustment
        regime_factor = 1.0
        if market_regime == "breakout":
            regime_factor = 1.15  # +15% in breakouts
        elif market_regime == "flat":
            regime_factor = 0.85  # -15% in flat markets

        # Volatility adjustment (inverse relationship)
        vol_adjustment = 1 / volatility_ratio if volatility_ratio > 0 else 1

        # Get performance metrics for adaptive constraints
        stats = get_performance_stats()

        # Determine leverage cap based on performance
        if stats["win_rate"] >= 0.72 and stats["profit_factor"] >= 1.9:
            max_leverage = 8  # Allow up to 8x only with proven performance
        else:
            max_leverage = 6  # Otherwise cap at 6x for safety

        # Apply conservative minimum leverage
        min_leverage = 3

        # Calculate and constrain final leverage
        adjusted_leverage = base_leverage * vol_adjustment * balance_factor * regime_factor
        return max(min_leverage, min(round(adjusted_leverage), max_leverage))

    except Exception as e:
        log(f"Error in get_adaptive_leverage: {e}", level="ERROR")
        # Fallback to safe default
        return 5


def get_bot_status():
    """Get current bot status (running, paused, etc.)"""
    try:
        import json

        with open("data/bot_state.json", "r") as f:
            data = json.load(f)
            return data.get("status", "unknown")
    except Exception as e:
        log(f"Error getting bot status: {e}", level="DEBUG")
        return "unknown"


def set_bot_status(status):
    """Set bot status (running, paused, etc.)"""
    try:
        import json
        import os
        from datetime import datetime

        # Create directory if it doesn't exist
        os.makedirs("data", exist_ok=True)

        # Get existing state or create new
        try:
            with open("data/bot_state.json", "r") as f:
                data = json.load(f)
        except Exception as e:
            log(f"Could not read existing bot state: {e}", level="DEBUG")
            data = {}

        # Update status
        data["status"] = status
        data["updated_at"] = datetime.now().isoformat()

        # Write back to file
        with open("data/bot_state.json", "w") as f:
            json.dump(data, f)

        log(f"Bot status updated to: {status}", level="INFO")
        return True
    except Exception as e:
        log(f"Error setting bot status: {e}", level="ERROR")
        return False


def set_max_risk(risk):
    """Set the current maximum risk value"""
    try:
        import json
        import os
        from datetime import datetime

        # Ensure risk is capped between 1% and 5%
        risk = max(0.01, min(0.05, risk))

        # Create directory if it doesn't exist
        os.makedirs("data", exist_ok=True)

        # Write to risk settings file
        with open("data/risk_settings.json", "w") as f:
            json.dump({"max_risk": risk, "updated_at": datetime.now().isoformat()}, f)

        log(f"Maximum risk updated to {risk*100:.1f}%", level="INFO")
        return True
    except Exception as e:
        log(f"Error setting max risk: {e}", level="ERROR")
        return False


def set_filter_thresholds(atr, volume):
    """Set the ATR% and volume filter thresholds"""
    try:
        import json
        import os
        from datetime import datetime

        # Create directory if it doesn't exist
        os.makedirs("data", exist_ok=True)

        # Write to filter settings file
        with open("data/filter_settings.json", "w") as f:
            json.dump({"atr_percent": atr, "volume_usdc": volume, "updated_at": datetime.now().isoformat()}, f)

        log(f"Filter thresholds updated: ATR={atr*100:.2f}%, Volume={volume:,.0f} USDC", level="INFO")
        return True
    except Exception as e:
        log(f"Error setting filter thresholds: {e}", level="ERROR")
        return False
