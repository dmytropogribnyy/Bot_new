## Project Audit — Structure, Cleanup, and Optimization (2025-08-08)

### Scope
Comprehensive revision of the repository to ensure modules are cohesive, consistent, optimized, and only essential code remains on the critical runtime path.

### Critical Runtime Path (keep)
- core/config.py — unified config (Pydantic, .env, runtime JSON)
- core/unified_logger.py — logging to console/file/SQLite/Telegram
- core/exchange_client.py — async ccxt client, USDC markets
- core/symbol_manager.py — USDC symbols discovery & volume filter
- core/order_manager.py — entries + TP/SL + monitoring + emergency
- core/trade_engine_v2.py — lightweight orchestrator
- core/risk_guard.py — simple SL-streak/cooldown helpers (to be expanded)
- strategies/scalping_v1.py — signal generation
- main.py — async entrypoint with loop and Telegram integration
- telegram/telegram_bot.py — runtime control

### Requires Fix/Update (high priority)
- core/order_manager.py
  - Validate/adjust TP/SL order types for Binance USDⓈ-M futures:
    - Use STOP/STOP_MARKET with `stopPrice` and `reduceOnly` for SL.
    - For TP, prefer TAKE_PROFIT/TAKE_PROFIT_MARKET (or limit + reduceOnly) per ccxt/binance schema.
  - Ensure partial TP shares map to actual quantities (not only ratios) and respect min notional.

- core/exchange_client.py
  - `create_stop_loss_order`/`create_take_profit_order` should pass correct `type` and `params` (STOP/STOP_MARKET, TAKE_PROFIT*); avoid mixing `type` in both arg and params.
  - `get_ticker()` volume field may be `info["quoteVolume"]` or `baseVolume`; add tolerant extraction.

- core/symbol_manager.py
  - In `get_symbols_with_volume_filter()`, gracefully handle tickers without `quoteVolume` and fallback to `baseVolume * last` when needed.

- main.py
  - Add runtime summaries to Telegram (positions, PnL, risk state) after implementing live data endpoints.

### Legacy/Redundant (archive out of critical path)
Move to `core/legacy/` (or remove) to prevent accidental imports:
- core/trade_engine.py — superseded by trade_engine_v2
- core/binance_api.py — replaced by exchange_client
- core/exchange_init.py — replaced by exchange_client
- core/order_utils.py
- core/engine_controller.py
- core/position_manager.py
- core/priority_evaluator.py
- core/risk_adjuster.py
- core/risk_utils.py
- core/fail_stats_tracker.py
- core/failure_logger.py
- core/entry_logger.py
- core/component_tracker.py
- core/signal_utils.py
- core/scalping_mode.py
- core/tp_sl_logger.py
- core/missed_signal_logger.py
- core/notifier.py
- core/balance_watcher.py
- core/runtime_state.py
- core/runtime_stats.py
- core/strategy.py
- core/symbol_processor.py
- core/tp_utils.py (strongly tied to legacy stack, references missing modules like `common.config_loader`)

Root-level legacy scripts (archive or update to new API):
- pair_selector.py, tp_logger.py, tp_optimizer.py, debug_tools.py, utils_core.py (partial), tools/continuous_scanner.py

Notes:
- These files are not used by the new runtime (`main.py` + v2 path). Keeping them in place risks confusion and accidental imports.

### Missing/Opportunity
- RiskGuard MVP integration in `trade_engine_v2.py` (pre-entry checks for SL-streak pause, daily-loss stop, max hold).
- Telegram live endpoints for `/status`, `/summary`, `/performance`, `/positions`, `/risk`, `/logs` (use `UnifiedLogger` DB).
- Tests for TP/SL order type validation against ccxt on testnet.

### Suggested Unifications
- Centralize TP/SL computation and order placement in `OrderManager` only.
- Prefer `UnifiedLogger` everywhere; avoid `utils_logging` usage in any active code.
- Ensure symbol normalization via `core/symbol_utils.py` across all active modules.

### Cleanup Tasks (actionable)
- [ ] Adjust TP/SL order types in `core/exchange_client.py` and `core/order_manager.py` (STOP/STOP_MARKET, TAKE_PROFIT* + reduceOnly/timeInForce).
- [ ] Harden volume filtering in `core/symbol_manager.py` (tolerant ticker volumes).
- [ ] Implement RiskGuard checks in `trade_engine_v2.py` before `place_position_with_tp_sl`.
- [ ] Enrich Telegram commands with live data sourced from `UnifiedLogger` database and `OrderManager`.
- [ ] Archive legacy modules into `core/legacy/` and mark deprecated in docs.
- [ ] Add testnet smoke tests for order placement (market/TP/SL) and symbol discovery.

### Safety Plan for Archiving
1) Create `core/legacy/` and move listed legacy files.
2) Run tests: smoke + integration. Ensure no imports from legacy path in active runtime/tests.
3) Optionally leave thin stubs in old paths raising descriptive ImportError to guide developers.

### Current Status
- Critical path files are consistent and cohesive.
- Main functional gaps: TP/SL order type validation, RiskGuard integration in engine, Telegram live data.



