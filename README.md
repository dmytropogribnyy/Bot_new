# 🤖 Binance USDC Futures Smart Bot

**Version**: 1.2 STABLE
**Last Updated**: April 2025

A fully autonomous trading bot for **Binance USDC-M Futures perpetuals**, featuring adaptive multi-indicator strategy, dynamic risk management, multi-TP/SL, self-optimization, and full Telegram integration.

---

## 📁 Project Structure

```
BinanceBot/
├── core/
│   ├── trade/
│   │   ├── __init__.py
│   │   ├── execution.py
│   │   ├── stop_loss.py
│   │   └── results.py
│   ├── strategy.py
│   └── trade_engine.py
├── telegram/
│   ├── __init__.py
│   ├── control.py
│   ├── info.py
│   ├── telegram_commands.py
│   ├── telegram_handler.py
│   └── telegram_utils.py
├── data/
│   ├── filter_thresholds.json
│   ├── bot_state.json
│   ├── dynamic_symbols.json
│   ├── last_ip.txt
│   ├── last_update.txt
│   ├── tp_performance.csv
│   └── backups/
├── docs/
│   ├── BinanceBot_Full_Documentation.md
│   └── TODO.md
├── cache.py
├── logging.py
├── notifications.py
├── state.py
├── .env
├── .env.example
├── config.py
├── ip_monitor.py
├── main.py
├── pair_selector.py
├── push_to_github.bat
├── README.md
├── requirements.txt
├── router_reboot_test.md
├── start_bot.bat
├── stats.py
├── tp_logger.py
├── tp_optimizer.py
└── utils.py
```

---

## 🔧 Requirements

- Python 3.8+
- Binance USDC-M Futures account
- Telegram bot token

```bash
pip install -r requirements.txt
```

Create a `.env` file:

```
API_KEY=your_binance_api_key
API_SECRET=your_binance_api_secret
TELEGRAM_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

Edit `config.py` to set:

- Trading pairs, leverage
- TP1/TP2/SL levels
- Risk and DRY_RUN mode
- Filters and score thresholds
- Trailing stop, break-even, safe mode

---

## 🚀 Run the Bot

```bash
python main.py
```

---

## 🧠 Core Features

### 📈 Strategy & Filters

- Multi-indicator signals: **RSI**, **EMA**, **MACD**, **ATR**, **ADX**, **Bollinger Bands**
- HTF EMA confirmation (1h)
- Volatility & time filters to avoid choppy markets
- Long/Short filter per symbol
- Score-based signal filtering

### 🎯 TP / SL / Risk Management

- Multi-TP: **TP1 + TP2** with break-even logic
- Adaptive **trailing stop** (ADX-aware)
- Dynamic risk-based position sizing
- Auto safe mode after losses
- Timeout-based auto-close with extension logic

### 🧠 Self-Optimization

- Logs all TP1/TP2/SL to `tp_performance.csv`
- Weekly optimizer adjusts TP levels
- Auto filter adjustment per symbol (ATR/ADX/BB)
- Symbol performance tracking
- Full auto-backup and restore

### 📊 Stats & Telegram

- Daily Telegram report (21:00 Bratislava)
- Real-time alerts: entries, exits, trailing, SL, break-even
- Clean English messages with emoji & MarkdownV2
- Full Telegram command interface

---

## 📱 Telegram Commands

| Command          | Description                                |
| ---------------- | ------------------------------------------ |
| `/help`          | List all commands                          |
| `/summary`       | Show session stats (PnL, winrate, streak)  |
| `/status`        | Runtime status and positions               |
| `/open`          | Show current trades                        |
| `/last`          | Last closed trade details                  |
| `/mode`          | View current mode (SAFE/AGGRESSIVE)        |
| `/pause`         | Pause new trades                           |
| `/resume`        | Resume trading                             |
| `/stop`          | Stop bot after closing all positions       |
| `/shutdown`      | Fully exit after closing positions         |
| `/panic`         | Force-close all trades (with confirmation) |
| `/log`           | Force send log and report                  |
| `/router_reboot` | Monitor IP for 30 mins (safe reboot)       |
| `/cancel_reboot` | Cancel reboot monitoring                   |
| `/ipstatus`      | Show current/previous IP, reboot status    |
| `/forceipcheck`  | Force IP change check                      |
| `/pairstoday`    | Show today's active trading pairs          |
| `/cancel_stop`   | Cancel pending stop after /stop            |

---

## 📌 Active Features (v1.2, 2025)

- ✅ Smart daily symbol rotation
- ✅ Adaptive trailing stop (ADX-aware)
- ✅ TP1/TP2/SL logging and optimizer
- ✅ Panic close via Telegram with confirmation
- ✅ DRY_RUN and verbose mode support
- ✅ Smart switching to stronger signals
- ✅ Auto-extension near TP1 on timeout
- ✅ MarkdownV2-safe alerts
- ✅ External IP monitoring and auto-stop
- ✅ Full Telegram control with command system
- ✅ Score-based filtering with auto-tuning
- ✅ Deposit/withdrawal detection (PnL safe)

---

## 🧭 Roadmap Priorities

- 🟡 Per-symbol Long/Short filters
- 🟡 `score_history.csv` signal logging
- 🟡 Backtest module (BTC/ETH, 15m)
- 🟡 Intra-day symbol re-rotation (every 4h)
- 🟡 PnL and balance charts (optional)
- 🟡 Enhanced MarkdownV2 compliance

---

> **Note**: Only supports **USDC-M perpetuals**. Use `DRY_RUN = True` for testing.
> For strategy details and full architecture, see the internal documentation.

---

**Enjoy adaptive, intelligent, and safe trading!** ⚡
