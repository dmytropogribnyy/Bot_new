# 🤖 Binance USDC Futures Smart Bot

**Version**: 1.2 STABLE
**Last Updated**: April 2025

A fully autonomous trading bot for **Binance USDC-M Futures perpetuals**, featuring an adaptive multi-indicator strategy, dynamic risk management, multi-TP/SL, self-optimization, and full Telegram integration.

---

## 📁 Project Structure

````
BinanceBot/
├── core/
│   ├── strategy.py         # Trading strategy and filters
│   └── trade_engine.py     # Trade management
├── telegram/
│   ├── telegram_commands.py  # Command handling
│   ├── telegram_ip_commands.py  # IP-related commands
│   ├── telegram_handler.py   # Incoming message processing
│   └── telegram_utils.py     # Message utilities (MarkdownV2 escaping, sending)
├── data/
│   ├── bot_state.json
│   ├── dry_entries.csv
│   ├── dynamic_symbols.json
│   ├── last_ip.txt
│   ├── last_update.txt
├── docs/
│   ├── BinanceBot_Full_Documentation.md
│   ├── Markdown_Recommendations.md
│   ├── router_reboot_test.md
│   └── TODO.md
├── .env                    # Environment variables
├── .env.example
├── config.py               # Configuration settings
├── ip_monitor.py           # External IP monitoring
├── main.py                 # Entry point
├── pair_selector.py        # Dynamic pair selection
├── push_to_github.bat
├── README.md
├── requirements.txt        # Dependencies
├── start_bot.bat
├── stats.py                # Performance statistics and reports
├── tp_logger.py            # Trade logging
├── tp_optimizer.py         # TP optimization and filter analysis
├── trader.py               # Trade execution and risk management
├── utils_core.py           # General utility functions
└── utils_logging.py        # Logging and Telegram API responses
---

## 🔧 Requirements

- **Python 3.8+**
- **Binance USDC-M Futures account**
- **Telegram bot token**

Install dependencies by running:

```bash
pip install -r requirements.txt
````

Create a `.env` file with the following content:

```
API_KEY=your_binance_api_key
API_SECRET=your_binance_api_secret
TELEGRAM_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

Then, customize `config.py` to adjust:

- Trading pairs and leverage settings
- TP1/TP2/SL levels
- Risk settings and DRY_RUN mode
- Filter thresholds (e.g., ATR, ADX)
- Trailing stop, break-even, and mode toggles

---

## 🚀 Run the Bot

Launch the bot with:

```bash
python main.py
```

---

## 🧠 Core Features

### 📈 Strategy & Filters

- **Multi-indicator signals:** RSI, EMA, MACD, ATR, ADX, Bollinger Bands
- **Higher timeframe confirmation:** 1h EMA trend check
- **Volatility & time filters:** Avoid choppy markets
- **Per-symbol Long/Short filters:** Configurable via `FILTER_THRESHOLDS[symbol]["long"]` or `["short"]`
- **Score-based signal filtering:** With logging to `score_history.csv`

### 🎯 TP / SL / Risk Management

- **Multi-TP setup:** TP1 + TP2 with integrated break-even logic
- **Adaptive trailing stop:** ADX-aware for optimized exits
- **Dynamic risk-based position sizing:** Adjusted to balance and market conditions
- **Auto-safe mode:** Reduced risk after losses
- **Timeout-based auto-close:** With extensions near TP1

### 🧠 Self-Optimization

- **Trade outcome logging:** All TP1/TP2/SL events saved to `tp_performance.csv`
- **Weekly TP optimization:** Auto-adjust TP levels via `tp_optimizer.py`
- **Auto filter adjustment:** Tailored per symbol (ATR/ADX/BB)
- **Smart pair rotation:** Updates every 4 hours (managed by `pair_selector.py`)
- **Full auto-backup and restore:** Safeguards configuration

### 📊 Stats & Telegram

- **Daily reports:** Sent at 21:00 Bratislava time
- **Real-time alerts:** For entries, exits, trailing stops, SL hits, and break-even events
- **Clean, MarkdownV2-safe messages:** With emojis for clarity
- **Comprehensive Telegram command interface**

---

## 📱 Telegram Commands

| Command          | Description                                        |
| ---------------- | -------------------------------------------------- |
| `/help`          | List all available commands                        |
| `/summary`       | Show session stats (PnL, winrate, streak)          |
| `/status`        | Display runtime status and open positions          |
| `/open`          | List current trades                                |
| `/last`          | Show details of the last closed trade              |
| `/mode`          | View current mode (SAFE/AGGRESSIVE)                |
| `/pause`         | Pause new trade entries                            |
| `/resume`        | Resume trading operations                          |
| `/stop`          | Stop the bot after closing all positions           |
| `/shutdown`      | Fully exit the bot after closing positions         |
| `/panic`         | Force-close all trades (confirmation required)     |
| `/log`           | Send the daily log and report                      |
| `/router_reboot` | Enable IP monitoring for 30 mins (safe reboot)     |
| `/cancel_reboot` | Cancel reboot monitoring                           |
| `/ipstatus`      | Display current/previous IP and reboot status      |
| `/forceipcheck`  | Force an immediate IP change check                 |
| `/pairstoday`    | Show today's active trading pairs                  |
| `/cancel_stop`   | Cancel a pending stop after `/stop`                |
| `/debuglog`      | Display the last 50 log lines (DRY_RUN only)       |
| `/close_dry`     | Close a DRY position (e.g., `/close_dry BTC/USDC`) |

---

## 📌 Active Features (v1.2, April 2025)

- ✅ Smart daily symbol rotation
- ✅ Adaptive trailing stop (ADX-aware)
- ✅ TP1/TP2/SL logging and optimizer
- ✅ Panic close via Telegram with confirmation
- ✅ DRY_RUN and verbose mode support
- ✅ Smart switching to stronger signals
- ✅ Auto-extension near TP1 on timeout
- ✅ MarkdownV2-safe alerts (using `escape_markdown_v2`)
- ✅ External IP monitoring and auto-stop (`ip_monitor.py`)
- ✅ Full Telegram control with command system
- ✅ Score-based filtering with history logging
- ✅ Deposit/withdrawal detection
- ✅ Backtesting module (15m timeframe for BTC/ETH)

---

## 🔭 Roadmap Priorities

- 🟡 Transition to Binance WebSocket for real-time data (in `strategy.py`)
- 🟡 Mini-deployment with loss control (starting with 50-100 USDC)
- 🟡 Simplification of Telegram logic (in `telegram_utils.py`)
- 🟡 Cleanup of `config.py` (e.g., merging volatility parameters)
- 🟡 Auto-reconnect on API failures (in `utils.py`)
- 🟡 PnL and balance charts in Telegram (optional feature)

> **Note**: The bot currently supports **USDC-M perpetuals** only.
> **Testing Tip:** Use `DRY_RUN = True` for simulation and safe testing.

For detailed documentation and remaining tasks, please refer to:

- [BinanceBot_Full_Documentation.md](docs/BinanceBot_Full_Documentation.md)
- [TODO.md](docs/TODO.md)

---

## 🔍 Code Quality

Run the following commands to automatically format and lint the code:

```bash
ruff check --fix .
isort .
```

---

**Enjoy adaptive, intelligent, and safe trading!** ⚡
