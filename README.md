# 🤖 Binance Profit Bot

A fully automated Binance Futures trading bot with Telegram control, adaptive risk, break-even logic, and trailing TP/SL.

---

## 📁 Project Structure

BINANCEBOT/
├── .env # Secret credentials (ignored in .gitignore)
├── .env.example # Template for setting up .env
├── config.py # Main bot configuration and constants
├── main.py # Entry point to launch trading and Telegram bot
├── trader.py # Core trading logic and execution
├── telegram_handler.py # Telegram message and file sending
├── telegram_commands.py# Telegram bot command handling (/positions, etc.)
├── utils.py # Helper functions (logging, formatting, alerts)
├── requirements.txt # Python dependencies
├── README.md # Project documentation
├── data/ # (Optional) for logs or exports
└── venv/ # Python virtual environment (not committed)

---

## 🔧 Requirements

- Python 3.10+
- pip
- Binance Futures account
- Telegram Bot Token

### Install dependencies:

```bash
pip install -r requirements.txt

```

🔑 Configuration
Create .env file in the project root:

API_KEY=your_binance_api_key
API_SECRET=your_binance_secret
TELEGRAM_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id

Check or edit config.py for symbol list, leverage, thresholds, etc.

🚀 Running the Bot
Activate virtual environment (if needed):

.\venv\Scripts\activate # Windows
source venv/bin/activate # Linux/macOS

The run:
python main.py

🤖 Telegram Commands

/positions - Show current open trades
/pause - Pause new trades
/resume - Resume trading
/log - Get log file
/help - List all commands

🛡 Features
✅ Multi-pair Binance Futures trading

📊 Dynamic TP/SL with adaptive strategy

🔁 Break-even & trailing stop support

📱 Telegram alerts and commands

📈 Weekly performance auto-check

🧠 Modular and expandable codebase

⚠️ Notes
Make sure your funds are in USDC Futures Wallet

Leverage is defined per symbol

All signals are filtered by volatility, trend and indicators

Enjoy fast, adaptive and intelligent automated trading ⚡
