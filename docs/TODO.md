# ✅ Binance USDC Futures Smart Bot — TODO.md

_Last updated: April 2025 — v1.5-dev_

---

## 🟢 Completed (v1.5-dev)

- ✅ Modular architecture: `core/`, `telegram/`, `data/`
- ✅ Full DRY_RUN support with accurate logic
- ✅ Centralized Telegram integration with MarkdownV2 escaping
- ✅ Entry logging to `entry_log.csv` + score/history tracking
- ✅ Smart Switching: dynamic replacement of low-score trades
- ✅ TP1/TP2/SL + trailing stop + break-even + timeout logic
- ✅ Auto-extension near TP1, configurable per trade
- ✅ Symbol rotation with fixed + dynamic pair logic
- ✅ Balance watcher + auto-detect deposits/withdrawals
- ✅ Safe shutdown logic via `/stop`, `/cancel_stop`, `/shutdown`
- ✅ IP Monitor + Router Reboot Safe Mode
- ✅ Daily + Weekly + Monthly + Quarterly + Yearly Telegram reports
- ✅ `tp_optimizer.py`: winrate-based TP optimization
- ✅ `tp_optimizer_ml.py`: per-symbol ML TP logic + auto config updates
- ✅ `htf_optimizer.py`: auto-toggle HTF filter based on winrate split
- ✅ Auto-adaptive thresholds (TP*ML*\* variables) with full fallback logic
- ✅ Config backup before ML rewrites (`config_backup.py.TIMESTAMP`)
- ✅ Auto-resume from previous state after restarts (symbol, DRY_RUN, logs)

---

## 🔄 In Progress

- 📊 Telegram stats: real-time **PnL Graphs** (Daily, Weekly, Monthly)
- 🌡️ Signal Heatmap: score-based visual + top-pair metrics
- 🔁 Config cleanup: unify volatility filters (ATR/ADX/BB) logic
- 🧠 ML learning loop for TP1/TP2 optimization feedback
- 🌐 REST API for external monitoring / dashboards

---

## 🟡 Planned

- Web UI / GUI dashboard (charts, logs, control panel)
- Backtest mode with replayed real signals
- Advanced risk profiler (dynamic volatility clusters)
- Telegram: strategy insights per trade (real-time)
- WebSocket feed integration (Binance stream)
- HTF volatility auto-tuner

---

## 🧪 Optional (Post-Production Ideas)

- Signal grouping across correlated symbols
- Discord integration (alerts, summaries)
- Paper trading mode with full backend tracking
- Notebook dashboard / auto-push to Google Sheets

---

## 📎 Notes

- All signal logic lives in `core/strategy.py`
- Per-symbol score tracking: `core/symbol_processor.py`
- TP/SL result storage: `data/tp_performance.csv`
- Telegram logic fully MarkdownV2-safe
- Daily cycle rotates symbols + reevaluates active set
