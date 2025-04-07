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

# --- Logging ---
LOG_LEVEL = "INFO"

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

# --- Mode & Debug ---
DRY_RUN = True
VERBOSE = DRY_RUN
is_aggressive = False
USE_DYNAMIC_IN_DRY_RUN = True

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
if DRY_RUN:

    class MockExchange:
        def fetch_ohlcv(self, symbol, timeframe, limit):
            print(f"[MockExchange] fetch_ohlcv called for {symbol}")
            base_price = 50000 if "BTC" in symbol else 2000 if "ETH" in symbol else 0.1
            # Static list of 50 rows to avoid loop issues
            data = [
                [i, base_price, base_price + 10, base_price - 10, base_price + i, 1000]
                for i in range(50)
            ]
            return data

        def fetch_ticker(self, symbol):
            print(f"[MockExchange] fetch_ticker called for {symbol}")
            base_price = 50000 if "BTC" in symbol else 2000 if "ETH" in symbol else 0.1
            return {"last": base_price}

        def fetch_balance(self):
            print("[MockExchange] fetch_balance called")
            return {"total": {"USDC": 44.0654828}}

        def fetch_positions(self):
            print("[MockExchange] fetch_positions called")
            return []

        def create_limit_order(self, symbol, side, amount, price):
            print(f"[MockExchange] create_limit_order called for {symbol}")
            pass

        def create_order(self, symbol, type, side, amount, price=None, params=None):
            print(f"[MockExchange] create_order called for {symbol}")
            pass

        def create_market_sell_order(self, symbol, amount):
            print(f"[MockExchange] create_market_sell_order called for {symbol}")
            pass

        def create_market_buy_order(self, symbol, amount):
            print(f"[MockExchange] create_market_buy_order called for {symbol}")
            pass

        def load_markets(self):
            print("[MockExchange] load_markets called")
            return {
                f"{symbol}:USDC": {"type": "future", "active": True} for symbol in SYMBOLS_ACTIVE
            }

    exchange = MockExchange()
else:
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
ROUTER_REBOOT_MODE_TIMEOUT_MINUTES = 30
IP_MONITOR_INTERVAL_SECONDS = 180
