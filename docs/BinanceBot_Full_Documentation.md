# Binance USDC Futures Smart Bot — Full Documentation

**Version**: 1.2 STABLE
**Last Updated**: April 2025

This document provides a detailed overview of the Binance USDC Futures Smart Bot, including its functionality, architecture, and development roadmap. It’s designed for developers, optimizers, and strategists to understand the project’s current state and future direction.

---

## 🔧 Overview

The Binance USDC Futures Smart Bot is an advanced, autonomous trading bot for Binance USDC-M Futures perpetuals. It combines a multi-indicator strategy, adaptive risk management, and Telegram integration to deliver a robust, user-friendly trading experience.

### Key Features

- ✅ Modular architecture: clean separation into `core/`, `telegram/`, `data/`
- ✅ Per-trade logging to `entry_log.csv` for both DRY_RUN and real trades
- ✅ Centralized Telegram notifications using `notifier.py`
- **📊 Multi-Indicator Strategy**: RSI, EMA, MACD, ATR, ADX, Bollinger Bands for signal generation.
- **🧠 Signal Strength**: Score-based filtering with logging to `score_history.csv`.
- **⚖️ Adaptive Risk Management**: Per-trade risk calculation, drawdown protection, SAFE/AGGRESSIVE modes.
- **🎯 TP1/TP2/SL**: Break-even, ADX-aware trailing stop, time-based limits with auto-extension.
- **📂 Dynamic Pair Selection**: 15–30 active pairs, auto-selected by volatility and volume.
- **📬 Telegram Integration**: Commands, notifications, and reports with MarkdownV2 formatting.
- **📈 Trade Tracking**: Logs trades to `tp_performance.csv`.
- **🔀 Self-Learning**: Auto-updates TP levels, filters, and pair statuses.
- **🧪 DRY_RUN Mode**: Simulates trading with softened filters, retaining real-mode logic.

---

## 📌 Current Priorities

1. **Binance WebSocket**: Replace polling with real-time data (`strategy.py`).
2. **PnL Graphs and Signal Reporting**: Enhance Telegram stats with visuals.
3. **Telegram Logic**: Simplify `telegram_utils.py`.
4. **Config Cleanup**: Merge volatility params in `config.py`.
5. **API Reliability**: Add auto-reconnect logic.

---

## ✅ Project Status (v1.2 STABLE)

- **Core Features**: Fully functional (strategy, Telegram, IP monitoring, TP/SL).
- **Stability**: Ready for real-mode with robust error handling.
- **Architecture**: Modular (e.g., `main.py`, `strategy.py`, `ip_monitor.py`).

---

## 📝 Example Code

### Long/Short Filters (`config.py`)

```python
FILTER_THRESHOLDS = {
"BTC/USDC": {
   "long": {"atr": 0.0015, "adx": 7, "bb": 0.008},
   "short": {"atr": 0.0017, "adx": 8, "bb": 0.009},
},
}
filters = FILTER_THRESHOLDS[symbol]["long" if result == "buy" else "short"]
```

### MarkdownV2 Escaping (`telegram_utils.py`)

```python
def escape_markdown_v2(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    return "".join("\\" + char if char in escape_chars else char for char in str(text))
```

### Signal Scoring (`strategy.py`)

```python
def should_enter_trade(symbol, df):
    direction = "long" if last["close"] > last["ema"] else "short"
    filters = FILTER_THRESHOLDS.get(symbol, default_filters)[direction]
    score = 0
    if direction == "long" and last["rsi"] < 30: score += 1
    if direction == "short" and last["rsi"] > 70: score += 1
    if last["macd"] > last["signal"]: score += 1
    with open("data/score_history.csv", "a") as f:
        f.write(f"{datetime.now()},{symbol},{score}\n")
    return "buy" if direction == "long" and score >= MIN_TRADE_SCORE else "sell"
```

---

## 📋 Testing the Bot

Run:

```bash
python main.py
```

Verify:

- Starts in DRY_RUN without errors.
- Logs dry entries (e.g., "Dry entry log: BUY on BTC/USDC at 12345.67890").
- Test commands: `/help`, `/summary`, `/forceipcheck`.
- Stop with Ctrl+C: "🛑 Bot manually stopped".

Check Logs:

- No MarkdownV2 errors.
- Confirm "✅ Message sent successfully" in logs.

---

## 🗓 Next Steps

- Transition to WebSocket for real-time performance.
- Deploy with 50–100 USDC to validate in real mode.
- Refine Telegram logic and configuration for scalability.
