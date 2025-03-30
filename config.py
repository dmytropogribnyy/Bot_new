import os
import pytz
from dotenv import load_dotenv

load_dotenv()

# Load sensitive data
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ALLOWED_USER_ID = 383821734  # You can also load from env if needed

# Paths and time
LOG_FILE_PATH = "telegram_log.txt"
EXPORT_PATH = "tp_performance.csv"
TIMEZONE = pytz.timezone("Europe/Bratislava")

# Symbols and leverage
SYMBOLS_ACTIVE = ['DOGE/USDC', 'BTC/USDC', 'ETH/USDC', 'BNB/USDC', 'ADA/USDC', 'XRP/USDC', 'SOL/USDC']
LEVERAGE_MAP = {
    'DOGE/USDC': 10, 'BTC/USDC': 5, 'ETH/USDC': 5,
    'BNB/USDC': 5, 'ADA/USDC': 10, 'XRP/USDC': 10, 'SOL/USDC': 10
}

# Risk management
ADAPTIVE_RISK_PERCENT = 0.05
AGGRESSIVE_THRESHOLD = 50
SAFE_THRESHOLD = 10
MIN_NOTIONAL = 5

# Strategy flags
ENABLE_TRAILING = True
TRAILING_PERCENT = 0.02
ENABLE_BREAKEVEN = True
BREAKEVEN_TRIGGER = 0.5

# Control
DRY_RUN = False
VERBOSE = False
