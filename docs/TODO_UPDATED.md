# ✅ Binance USDC Futures Smart Bot — TODO.md
_Last updated: April 2025 — v1.6-dev_

## 🟢 Completed (v1.6-dev)
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
- ✅ Auto-adaptive thresholds (`TPML*` variables) with full fallback logic
- ✅ Config backup before ML rewrites (`config_backup.py.TIMESTAMP`)
- ✅ Auto-resume from previous state after restarts (symbol, DRY_RUN, logs)

## 🔄 In Progress
- 📊 Telegram stats: real-time PnL Graphs (Daily, Weekly, Monthly)
- 🌡️ Signal Heatmap: score-based visual + top-pair metrics
- 🔁 Config cleanup: unify volatility filters (ATR/ADX/BB) logic
- 🧠 ML learning loop for TP1/TP2 optimization feedback
- 🌐 REST API for external monitoring / dashboards

## 🟡 Planned
- WebSocket Feed Integration
- Open Interest (OI) Integration
- Soft Exit Logic
- Auto-Scaling Position Size
- Re-entry after timeout or manual exit
- Live Signal Statistics

## 🔧 Key Improvements & Current Tasks
### Clean Architecture + DRY_RUN separation
- ✅ All file writes skipped in DRY_RUN mode
- ✅ All modules use `core/binance_api.py` + `safe_call()`
- ✅ Telegram fallback on exchange errors

### Adaptive Score System
- ✅ `score_evaluator.py` with indicator-based score + breakdown
- ✅ Adaptive thresholds based on winrate + trade count
- ✅ `/score_debug` planned

### Aggressiveness System
- ✅ `aggressiveness_controller.py`: EMA-smoothed adaptive factor
- ✅ Used in trailing stop, TP, and Smart Switching
- ✅ `/aggressive_status` planned

## 🚧 Next Steps
- [ ] Finalize `main.py`: use `api.*`, verify DRY_RUN logic
- [ ] Check `ip_monitor.py`, `telegram_ip_commands.py` for fallback errors
- [ ] Add `/score_debug`, `/aggressive_status` commands
- [ ] Run real-mode test with full entry/exit logging
- [ ] Finish `websocket_manager.py` module
- [ ] Plan and start `oi_tracker.py` module
- [ ] Design `soft_exit` logic inside `trade_engine.py`