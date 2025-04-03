# 🤖 Binance USDC Futures Smart Bot — 2025 Summary

A fully autonomous Binance Futures trading bot for **USDC-M perpetuals**, with adaptive strategy, dynamic risk, multi-TP, self-optimization, and Telegram integration.

---

## 📁 Project Structure

```
BINANCEBOT/
├── main.py             # Entry point
├── config.py           # Settings and thresholds
├── trader.py           # Main loop and control
├── telegram_handler.py # Telegram alerts
├── telegram_commands.py# Commands interface
├── stats.py            # Reports, PnL, deposits
├── tp_logger.py        # TP/SL logging
├── tp_optimizer.py     # TP/filter/stats optimizer
├── utils.py            # Helpers
├── core/
│   ├── strategy.py     # Signal logic & indicators
│   └── trade_engine.py # Execution, TP/SL, trailing
├── data/
│   ├── tp_performance.csv   # Per-trade results
│   ├── score_history.csv    # Signal score logging
│   ├── dynamic_symbols.json # Daily active pairs
│   ├── backups/             # Auto backups
└── .env / requirements.txt / .env.example
```

---

## 🔧 Requirements

- Python 3.10+
- Binance USDC-M Futures account
- Telegram bot token

```bash
pip install -r requirements.txt
```

---

## 🔑 Configuration

Create a `.env` file:

```env
API_KEY=your_key
API_SECRET=your_secret
TELEGRAM_TOKEN=bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

Then edit `config.py` to define:

- Symbols & leverage
- TP1 / TP2 / SL %
- Risk and dry-run mode
- Smart filters, score threshold
- Safe mode, trailing, break-even

---

## 🚀 Running the Bot

```bash
python main.py
```

---

## 🧠 Core Features

### 📈 Strategy & Filters

- Multi-indicator signal (RSI, EMA, MACD, ATR, ADX, BB)
- HTF EMA trend confirmation (1h)
- Volatility and time filters (avoid chop)
- Long/Short filters separately (configurable)
- Smart scoring system (score-based entry)

### 🎯 TP / SL / Risk Management

- Multi-TP: TP1 + TP2 with break-even logic
- Trailing stop (ADX-aware, adaptive distance)
- Adaptive position sizing by risk %
- Daily loss protection (auto safe mode)
- Auto shutdown / pause if needed
- Timeout close + extension if near TP1

### 🧠 Self-Optimization

- Logs every TP1/TP2/SL to CSV
- Optimizer: adjusts TP1/TP2 weekly
- Auto-updates filters per symbol (ATR, ADX, BB)
- Tracks symbol performance → disables or boosts
- Auto-backup and restore of config

---

## 📊 Stats & Telegram

- Daily and weekly reports via Telegram (21:00)
- /summary, /status, /open, /last, /mode, /log
- Alerts: Entry, TP1, TP2, SL, break-even, trailing
- MarkdownV2 formatting with emoji support
- Minimal, clear messages in English

---

## 📱 Commands

```
/help        - List commands
/summary     - Session stats (PnL, winrate, streak)
/status      - Runtime status & position info
/open        - Show open trades
/last        - Last closed trade
/mode        - View current mode
/pause       - Pause new entries
/resume      - Resume entries
/stop        - Stop bot after closing all
/shutdown    - Exit fully (after all closed)
/log         - Force send report + log
/panic       - Emergency close all positions
```

---

## 📌 Active Features (v1.0, 2025)

- ✅ Smart rotation of symbols (daily)
- ✅ Adaptive trailing by ADX
- ✅ Panic Close with Telegram confirmation
- ✅ DRY_RUN + verbose mode
- ✅ Fixed and dynamic pair list
- ✅ Smart Switching (stronger signal override)
- ✅ TP1/TP2/SL logging + optimizer
- ✅ Score-based filtering (auto-adjustable)
- ✅ Full Telegram control + file sending
- ✅ Auto-detect deposits/withdrawals (excluded from PnL)
- ✅ Timeout close + auto-extension
- ✅ MarkdownV2 formatting for messages

---

## 🧭 Current Priorities

- 🟡 Long/Short filter config (per symbol)
- 🟡 score_history.csv logging
- 🟡 Backtest module (15m, BTC/ETH)
- 🟡 Intra-day smart rotation (every 4h)
- 🟡 Full MarkdownV2 compliance in messages
- 🟡 (Optional) PnL charts, balance graph

---

**Note:** Bot trades only **USDC-M perpetuals** on Binance.
Use `DRY_RUN = True` in config to simulate signals safely.

---

Enjoy safe, adaptive, and intelligent trading ⚡
