# Binance USDC Futures Smart Bot — Full Documentation

**Version**: 1.5-dev
**Last Updated**: April 2025

This document provides a full technical overview of the Binance USDC Futures Smart Bot — an advanced, autonomous trading system for Binance USDC-M perpetual futures. Designed for adaptive growth, robust safety, and modular extensibility.

---

## 🔧 Overview

The bot combines multi-indicator signals, per-symbol TP/SL logic, adaptive risk management, automatic learning, and seamless Telegram integration — all packed into a clean modular architecture.

### ✅ Highlights

- **Modular architecture**: Separated into `core/`, `telegram/`, `data/`, `docs/`
- **Multi-indicator strategy**: RSI, EMA, MACD, ADX, ATR, Bollinger Bands
- **Score-based filtering**: Logs signals to `score_history.csv`
- **Dynamic pair selection**: 15–30 daily pairs based on volatility/volume
- **Smart TP/SL**: TP1/TP2 with break-even + trailing stop (ADX-aware)
- **Auto-timeout logic**: Closes stale trades with optional extension
- **HTF confirmation**: 1h EMA check — auto-enabled/disabled based on winrate
- **Auto-persistence**: DRY_RUN logs to `entry_log.csv`, real trades to `tp_performance.csv`
- **Smart Switching**: Auto-exit weaker trades to favor higher-score setups
- **ML TP Optimizer**: Suggests TP1/TP2 based on per-symbol trade stats
- **Auto-adaptive thresholds**: Learns and updates ML config dynamically
- **Telegram bot**: Commands, reports, notifications — MarkdownV2 safe
- **IP monitoring**: Handles forced disconnects + router reboot mode

---

## 🚦 Strategy Overview

- Entry signals based on:
  - RSI oversold/overbought
  - MACD cross
  - EMA trend direction
  - ADX strength filter
  - ATR + Bollinger Band volatility filters
- Scoring system from 1–5 — must reach threshold to trade
- Optional HTF filter confirms entry based on 1h EMA trend (adaptive)

---

## 📊 Logging & Optimization

- **entry_log.csv**: Entry signals and their context (score, indicators, HTF)
- **tp_performance.csv**: All exits (TP1/TP2/SL) with PnL and duration
- **tp_optimizer.py**: Winrate-based weekly optimization
- **tp_optimizer_ml.py**: ML analysis per symbol with:
  - TP1/TP2 winrate
  - Avg PnL
  - Dynamic suggestion of TP values
  - Auto rewrite of config
  - Auto-adjusts thresholds like `TP_ML_THRESHOLD`
- **htf_optimizer.py**: Enables/disables HTF logic based on split winrate
- **stats.py**: Sends daily, weekly, monthly, 3M, 6M, and yearly reports

---

## 🛡️ Risk & Execution

- Position sizing based on risk % of balance
- Trailing Stop + Break-even combo
- Timeout exit logic with extensions
- SAFE mode after SL streaks
- Max open positions limit (e.g., 5 trades simultaneously)

---

## 📬 Telegram Features

- Commands:
  - `/summary`, `/log`, `/stop`, `/cancel_stop`
  - `/ipstatus`, `/router_reboot`, `/cancel_reboot`, `/forceipcheck`
- Notifications:
  - Entry, Exit, TP1/TP2/SL hits, trailing stop, timeout exit
- MarkdownV2-safe messaging
- Daily report at 21:00 Bratislava time
- Logs config changes (e.g., TP1 updates, HTF toggle)

---

## 🔁 System Management

- DRY_RUN support: Simulates trades with real logic
- Full recovery on reboot: Resumes symbol rotation + logs
- IP monitor: Detects external IP change → triggers safe stop
- Reboot Mode: Safe 30m delay during router restarts

---

## 📌 Current Priorities (v1.5 Roadmap)

1. PnL Graphs in Telegram (daily/weekly/monthly equity)
2. Signal heatmap visual + score analytics
3. REST API for monitoring / remote management
4. Strategy fine-tuning (filters, HTF, score logic)
5. WebSocket integration (market stream upgrade)

---

## 🧪 Sample Logic

### Score-based Entry (`strategy.py`)

```python
score = 0
if rsi < 30 and direction == "long": score += 1
if macd > signal: score += 1
if adx > 15: score += 1
if atr > threshold: score += 1
if htf_confirms: score += 1
```

### Entry Logging (`entry_logger.py`)

```python
row = {
  "Time": now,
  "Symbol": symbol,
  "Side": side,
  "Score": score,
  "HTF Confirmed": htf_confirmed,
  "Indicators": json.dumps(indicators),
}
```

### Auto-Adaptive ML (`tp_optimizer_ml.py`)

```python
if winrate < 0.4:
  rewrite_config_param("TP_ML_THRESHOLD", 0.08)
else:
  rewrite_config_param("TP_ML_THRESHOLD", 0.05)
```

---

## 🧠 Summary

The bot now operates with full adaptive logic, autonomous risk control, Telegram command interface, and smart optimization.

> It learns, adapts, and evolves — engineered for long-term, low-risk crypto futures trading.
