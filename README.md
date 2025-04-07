# 🤖 Binance USDC Futures Smart Bot

**Version**: 1.3.1 STABLE
**Last Updated**: April 2025

A fully autonomous trading bot for **Binance USDC-M Futures perpetuals**, featuring an adaptive multi-indicator strategy, dynamic risk management, multi-TP/SL, self-optimization, and full Telegram integration.

---

## 📁 Project Structure

```
BinanceBot/
├── core/
│   ├── strategy.py           # Trading strategy and filters
│   ├── trade_engine.py       # Trade management
│   ├── balance_watcher.py    # Balance tracking and deposit alerts
│   ├── engine_controller.py  # Main trading loop (refactored)
│   ├── entry_logger.py       # Logs entries to CSV
│   ├── notifier.py           # Centralized Telegram notifications
│   └── symbol_processor.py   # Per-symbol signal analysis
├── telegram/
│   ├── telegram_commands.py     # Command handling
│   ├── telegram_ip_commands.py  # IP-related commands
│   ├── telegram_handler.py      # Incoming message processing
│   └── telegram_utils.py        # Message utilities (MarkdownV2 escaping, sending)
├── data/
│   ├── bot_state.json
│   ├── dry_entries.csv
│   ├── dynamic_symbols.json
│   ├── last_ip.txt
│   ├── last_update.txt
│   └── entry_log.csv
├── docs/
│   ├── BinanceBot_Full_Documentation.md
│   ├── Markdown_Recommendations.md
│   ├── router_reboot_test.md
│   └── TODO.md
├── .env                    # Environment variables
├── .env.example
├── config.py               # Configuration settings
├── ip_monitor.py           # External IP monitoring
├── main.py                 # Entry point (refactored)
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
```

---

## 🚀 Run the Bot

Launch the bot with the new modular architecture:

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

### ⚙️ Modular Core System

- Clean separation of strategy, symbol analysis, trade engine, and notifications
- Per-trade logging to `entry_log.csv` (including DRY_RUN signals)
- Centralized error handling and Telegram alerts
- Safe shutdown logic via `/stop` and `/shutdown`

### 📊 Stats & Telegram

✅ Modular architecture (core separation of logic)
✅ Per-trade logging to `entry_log.csv`
✅ Centralized Telegram notifications (via `notifier.py`)

- **Daily reports:** Sent at 21:00 Bratislava time
- **Real-time alerts:** For entries, exits, trailing stops, SL hits, and break-even events
- **Clean, MarkdownV2-safe messages:** With emojis for clarity
- **Comprehensive Telegram command interface**

...
