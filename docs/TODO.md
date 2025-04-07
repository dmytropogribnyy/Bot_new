# ✅ Binance USDC Futures Smart Bot — TODO.md

_Last updated: April 2025 — v1.3.1 STABLE_

---

## 🟢 Completed (v1.3.1)

- Modular core structure: `core/`, `telegram/`, `data/`
- Refactored main cycle into `engine_controller.py`
- DRY_RUN support + Telegram notification system
- Entry logging to `entry_log.csv` (with status & mode)
- Centralized notifier system for Telegram + logs
- Balance watcher: detects deposits/withdrawals
- Smart Switching: score-based re-entry logic
- Symbol rotation every 4h with anchor pairs
- Safe IP monitoring + `/router_reboot`, `/cancel_stop`
- TP1/TP2/SL system with trailing and break-even
- Auto-close timeout logic with extension near TP1
- Score filtering + `score_history.csv` logging
- Adaptive TP optimization (`tp_optimizer.py`)
- Daily & weekly Telegram stats
- MarkdownV2-safe messaging for all outputs
- Telegram command set: `/stop`, `/shutdown`, `/open`, `/summary`, etc.

---

## 🔄 In Progress

- WebSocket price feed integration (Binance stream)
- Telegram stats: PnL charts and summary graphs
- Config cleanup: centralize volatility settings
- Improve risk heuristics with filter-based scaling

---

## 🟡 Planned

- GUI or web dashboard for monitoring
- Signal replay + score heatmap
- Auto-reconnect logic on API failures
- Cross-symbol correlation filters
- Telegram-based real-time logs for strategy insights

---

## 🧪 Optional (Post-Production Ideas)

- REST API for external dashboard or mobile integration
- Strategy trainer: local backtest + learn loop
- Paper trading backend for dry testing at scale
- Discord alerts mirror

---

## 📎 Notes

- All strategy logic centralized in `core/strategy.py`
- Pair logic & scoring in `core/symbol_processor.py`
- Entry logic is DRY_RUN-safe and logs even failed entries
- Telegram and Markdown escaping fully stable
