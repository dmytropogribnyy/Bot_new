import os
import pytz
import ccxt
from dotenv import load_dotenv

load_dotenv()

# --- API & Auth ---
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ALLOWED_USER_ID = 383821734  # Telegram user ID allowed to interact with the bot

# --- Timezone & Paths ---
TIMEZONE = pytz.timezone("Europe/Bratislava")
LOG_FILE_PATH = "telegram_log.txt"  # Path to the log file for bot activity
EXPORT_PATH = "data/tp_performance.csv"  # Path to export trade performance data

# --- Logging ---
LOG_LEVEL = "INFO"  # Log level ("DEBUG", "INFO", "WARNING", "ERROR"); "DEBUG" for verbose output

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

FIXED_PAIRS = ["BTC/USDC", "ETH/USDC", "DOGE/USDC", "SOL/USDC", "BNB/USDC"]
MAX_DYNAMIC_PAIRS = 30  # Maximum number of dynamic trading pairs
MIN_DYNAMIC_PAIRS = 15  # Minimum number of dynamic trading pairs

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
TP1_PERCENT = 0.007  # Take-profit 1 percentage
TP2_PERCENT = 0.013  # Take-profit 2 percentage
TP1_SHARE = 0.7  # Share of position to close at TP1
TP2_SHARE = 0.3  # Share of position to close at TP2
SL_PERCENT = 0.01  # Stop-loss percentage

# --- Risk Management ---
ADAPTIVE_RISK_PERCENT = 0.05  # Risk percentage per trade
AGGRESSIVE_THRESHOLD = 50  # Threshold for aggressive mode (in USDC)
SAFE_THRESHOLD = 10  # Threshold for safe mode (in USDC)
MIN_NOTIONAL = 5  # Minimum notional value for a trade (in USDC)
MAX_HOLD_MINUTES = 90  # Maximum time to hold a position (in minutes)
RISK_DRAWDOWN_THRESHOLD = 5.0  # Drawdown threshold for reducing risk (in %)

# --- Entry Filter Thresholds (fallback / default) ---
ATR_THRESHOLD = 0.0015  # Average True Range threshold
ADX_THRESHOLD = 7  # ADX (Average Directional Index) threshold
BB_WIDTH_THRESHOLD = 0.008  # Bollinger Bands width threshold

# --- Volatility Filter ---
VOLATILITY_SKIP_ENABLED = True  # Enable volatility filter
VOLATILITY_ATR_THRESHOLD = 0.0012  # ATR threshold for volatility filter
VOLATILITY_RANGE_THRESHOLD = 0.015  # Price range threshold for volatility filter

DRY_RUN_VOLATILITY_ATR_THRESHOLD = 0.0025  # Softer ATR threshold in DRY_RUN mode
DRY_RUN_VOLATILITY_RANGE_THRESHOLD = 0.0075  # Softer range threshold in DRY_RUN mode

# --- Daily Loss Protection ---
DAILY_PROTECTION_ENABLED = True  # Enable daily loss protection
SAFE_TRIGGER_THRESHOLD = 0.10  # Threshold to switch to safe mode (10% loss)
FULL_STOP_THRESHOLD = 0.05  # Threshold to stop trading (5% loss)

# --- Strategy Toggles ---
ENABLE_TRAILING = True  # Enable trailing stop
TRAILING_PERCENT = 0.02  # Trailing stop percentage
ENABLE_BREAKEVEN = True  # Enable break-even stop
BREAKEVEN_TRIGGER = 0.5  # Break-even trigger (as a fraction of TP1)

# --- Signal Strength Control ---
MIN_TRADE_SCORE = 3  # Minimum score to enter a trade (out of 5)
SCORE_BASED_RISK = True  # Adjust risk based on signal score
SCORE_BASED_TP = True  # Adjust take-profit based on signal score

# --- Mode & Debug ---
DRY_RUN = True  # Run in dry-run mode (no real trades)
VERBOSE = DRY_RUN  # Enable verbose logging if DRY_RUN is True
is_aggressive = False  # Use aggressive trading mode
USE_DYNAMIC_IN_DRY_RUN = True  # Use dynamic pair selection in DRY_RUN mode

# --- Runtime Trade Stats ---
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
    "api_errors": 0,  # Track API errors for error handling
}

# --- Exchange ---
exchange = ccxt.binanceusdm(
    {
        "apiKey": API_KEY,
        "secret": API_SECRET,
        "enableRateLimit": True,
        "options": {"defaultType": "future"},
    }
)

# --- Auto-learned Entry Filter Thresholds ---
FILTER_THRESHOLDS = {
    "DOGE/USDC": {"atr": 0.0015, "adx": 7, "bb": 0.008},
    "BTC/USDC": {"atr": 0.0015, "adx": 7, "bb": 0.008},
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
ROUTER_REBOOT_MODE_TIMEOUT_MINUTES = 30  # Timeout for router reboot mode (in minutes)
IP_MONITOR_INTERVAL_SECONDS = 180  # IP check interval (every 3 minutes)
