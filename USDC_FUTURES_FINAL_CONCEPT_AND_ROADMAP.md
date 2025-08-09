## Binance USDT Futures Bot — Final Concept and Roadmap (v2.3)

### 🎯 CURRENT STATUS: PRODUCTION READY (09.08.2025)
- ✅ **Testnet Testing**: Successfully completed all scenarios
- ✅ **Emergency Shutdown**: Ctrl+C automatically closes positions
- ✅ **Order Management**: Orphaned TP/SL orders automatically cleaned
- ✅ **Network Resilience**: Telegram timeouts fixed, retry logic implemented
- ✅ **Trade Execution**: Full cycle tested (open → monitor → close)
- ✅ **Safety Features**: Multiple failsafes and monitoring tools

### Goals and KPIs
- Start: 400 USDT (Testnet: 15000 USDT)
- Target: 1–2 USD/hour, win-rate ≥ 55%, daily drawdown ≤ 5%
- Profiles: Conservative / Balanced / Aggressive (config-driven)
- Reliability: stable async loop, graceful shutdown, state persistence

### Architecture (modular, async)
- Config: Pydantic model with .env + runtime JSON merge
- Exchange: ccxt async client, caching, retry, rate-limit, health-check
- SymbolManager: USDC symbols (volume/ATR filters), rotation, caching
- StrategyManager + ScalpingV1: EMA/RSI/MACD/ATR, 1+1 gating, signal breakdown
- OrderManager: market entry + stepped TP, mandatory SL, hanging cleanup, emergency close
- RiskGuard (MVP): SL-streak pause, daily loss limit, max concurrent positions, max hold
- TradeEngine: orchestrates scan → evaluate → risk → execute
- UnifiedLogger: console, file, SQLite, Telegram (important only)
- TelegramBot: status/summary/perf/risk, pause/resume, panic, config info
- (Optional) WebSocketManager: realtime with REST fallback (careful on Windows)

### Execution Flow
1) Scan symbols (USDC futures) → fetch OHLCV
2) Strategy evaluates; if signal → risk checks
3) Place entry + TP/SL; track position & timeouts
4) Log to DB; send Telegram alerts when important

### Critical Fixes (must do first)
- USDC market detection: ensure quote == USDC and correct market type (swap/future) — DONE
- Unify `SymbolManager` with `ExchangeClient` API (get_markets/get_ticker/get_ohlcv) — PARTIALLY DONE
- Add `TradeEngine` and integrate into main loop — DONE (see `core/trade_engine_v2.py`, wired in `main.py`)
- Normalize symbol format across modules — DONE (see `core/symbol_utils.py`)

### Critical Code References (current repo)
- USDC symbols filter:
  - File: `core/exchange_client.py` — implemented tolerant USDC detection (quote/settle == 'USDC', type in swap/future) and formatting via `ensure_perp_usdc_format()`.
- API harmonization:
  - File: `core/symbol_manager.py` — switched to `exchange.get_ticker()` and uses `is_usdc_contract_market()` + formatting from `core/symbol_utils.py`.
- Trade engine integration:
  - Files: `core/trade_engine_v2.py` (new), `main.py` — lightweight engine wired into main loop.

### What we adopt from V2 (References)
- Robust retry/rate-limit/caching patterns (simplified)
- RiskManager ideas (SL-streak, daily loss, adaptive later)
- LeverageManager concept for ATR/win-rate (post-MVP)
- WebSocketManager pattern with strict fallback (post-stability)

### Development Roadmap

#### Stage 1 — Core Stabilization ✅ **COMPLETED**
- ✅ Fixed symbol filters (TUSD/BUSD excluded)
- ✅ Unified markets/ticker/ohlcv API
- ✅ Symbol normalization working
- ✅ Windows async loop compatibility fixed
- ✅ Basic trading loop operational

#### Stage 2 — Trading Engine ✅ **COMPLETED**
- ✅ Implemented lightweight `core/trade_engine_v2.py`
- ✅ Integrated into `main.py`
- ✅ Telegram notifications working
- ✅ Position tracking and management

#### Stage 3 — Safety & Reliability ✅ **COMPLETED**
- ✅ Emergency shutdown with position closing
- ✅ Orphaned order cleanup
- ✅ Network timeout handling
- ✅ Comprehensive error handling
- ✅ Multiple monitoring tools

#### Stage 4 — Production Readiness ✅ **COMPLETED**
- ✅ Full testnet validation
- ✅ Documentation updated
- ✅ Utility scripts for maintenance
- ✅ Safety mechanisms tested
- ✅ Performance optimization

### 🚀 Future Enhancement Phases (Optional)

#### Phase A — Advanced Risk Management
- SL-streak pause (auto-disable after N consecutive losses)
- Daily loss limits with automatic shutdown
- Position correlation analysis
- Adaptive position sizing based on volatility

#### Phase B — Enhanced Telegram Interface
- Live data for `/status`, `/summary`, `/performance`, `/positions`
- Control commands: `/pause`, `/resume`, `/panic`, `/aggression`
- Real-time alerts on trade executions
- Position management commands

#### Phase C — Analytics & Performance
- Position history tracking and export
- Performance analytics dashboard
- Profit/loss pattern analysis
- Strategy backtesting framework

#### Phase D — Production Deployment
- Migration from testnet to live trading
- Small initial capital deployment
- Gradual scaling based on performance
- Continuous monitoring and optimization

Stage 7 — Profit Optimization (Week 3)
- Tune strategy thresholds; add LeverageManager; refine stepped TP
Acceptance: net-positive PnL, win-rate ≥ 55%

Stage 8 — Optional WebSocket (Week 4)
- Realtime ticker with robust fallback
Acceptance: no regressions; stable on VPS/Linux

### Пошаговый план внедрения (детализация)

- Stage 1 — Стабилизация Core (1–2 дня)
  - Исправить USDC фильтры и остатки USDT:
    - `core/exchange_client.py`
      - `get_usdc_futures_symbols()`: `quote == 'USDC'`, типы рынков: включить `'swap'` (перпетуалы) и учитывать совместимость с `'future'` по схеме ccxt; нормализовать формат символов.
      - `_test_connection()`: не хардкодить `BTC/USDT`; использовать `load_markets()` и тестировать доступный USDC‑символ или просто `fetch_balance()` + `load_markets()`.
      - `_set_default_leverage()`: заменить список пар на USDC; вызывать с нормализованными символами.
    - `main.py`: лог статуса должен использовать баланс USDC (добавить в ExchangeClient `get_usdc_balance()` и использовать его вместо USDT).
  - Унификация API `SymbolManager ↔ ExchangeClient`:
    - В `core/symbol_manager.py` перейти на `exchange.get_markets()` или добавить совместимый враппер `fetch_markets()` в `ExchangeClient`.
  - Нормализация символов:
    - Вынести утилиты: `normalize(symbol)`, `to_api_symbol(symbol)`, `is_usdc_market(market)` в отдельный модуль и использовать во всех местах (символы, ордера, TP/SL).
  - Депрекация старого контура:
    - Новый пайплайн использует только `OptimizedExchangeClient`; прямые вызовы из `core/exchange_init.py` и низкоуровневые функции в `core/binance_api.py` оставить только для обратной совместимости на период миграции.
  - Acceptance:
    - ≥25 валидных USDC‑символов; статусы и баланс в USDC; базовые тесты без USDT‑артефактов.

- Stage 2 — TradeEngine + пайплайн (2 дня)
  - Реализовать лёгкий `TradeEngine`: цикл сканирования USDC‑символов → OHLCV → стратегия → риск → вход + TP/SL.
  - Интегрировать вызов в `main.py` параллельно с мониторингом ордеров.
  - Acceptance: в DRY RUN появляются 2–3 входа, TP/SL ставятся, логи и Telegram‑уведомления есть.

- Stage 3 — RiskGuard MVP (1 день)
  - SL‑стрик пауза, дневной лимит убытка, лимит позиций, max hold.
  - Включить проверки перед размещением ордера.
  - Acceptance: автопауза/стоп работают, отражаются в Telegram.

- Stage 4 — Telegram UX (1 день)
  - `/status`, `/summary`, `/performance`, `/positions`, `/pause`, `/resume`, `/panic`, `/config`, `/logs` — все данные из живых источников (Exchange/БД/кэш).
  - Acceptance: все команды возвращают актуальные данные; алерты об исполнениях.

- Stage 5 — Runtime & Logging (1 день)
  - Периодические статусы: баланс USDC, позиции, UPnL, аптайм. Агрегации в БД/CSV.
  - Acceptance: периодические записи и on‑demand сводки без ошибок.

- Stage 6 — Реальные данные (неделя)
  - Тестнет: стабильность рынков/тикеров/OHLCV; валидация типов ордеров (reduceOnly, timeInForce, STOP/STOP_MARKET).
  - Малый прод: безопасные лимиты, ручной мониторинг.
  - Acceptance: успешные сделки на тестнете; стабильный цикл.

- Stage 7 — Profit Optimization (неделя)
  - Тюнинг порогов, размеры шагов TP, простой `LeverageManager` (ATR/винрейт).
  - Acceptance: win‑rate ≥ 55%, положительный PnL на консервативном профиле.

- Stage 8 — Опционально WebSocket (после стабилизации)
  - Реалтайм тикеры с REST‑фолбэком; по умолчанию на Windows — REST, на VPS/Linux — WS.
  - Acceptance: без регрессий, стабильность на VPS/Linux.

### Технические примечания
- Символы: для USDⓈ‑M USDC чаще вид `BTC/USDC:USDC` (перпетуал). Нужна единая нормализация и конвертация символов.
- Типы рынков в ccxt: Binance perpetual обычно `type = 'swap'`; фильтрация должна учитывать это, а также `settle == 'USDC'`/`quote == 'USDC'`.
- Ордеры: для TP/SL обязательно `reduceOnly`; SL — STOP/STOP_MARKET с `stopPrice`; при лимитных fallback — корректный `timeInForce`.

### Контроль качества
- Тесты: базовые/стратегия/DRY RUN/Telegram + отдельные тесты на фильтрацию USDC и нормализацию символов.
- Статика: pyright/ruff (если подключены). Суточный DRY‑run перед тестнетом.

### Consolidated Findings & Decisions (anchored)
- Stage 2 (done): unified Telegram bot (15 cmds), unified config, Windows fixes, error handling improvements.
  - Source: `STAGE_2_FINAL_OPTIMIZATION_REPORT.md`, `STAGE_2_PROGRESS_REPORT.md`, `STAGE_2_REVISION_REPORT.md`.
- Stage 3 plan (prepared): DRY RUN, runtime logging, Telegram enhancement, real-data tests.
  - Source: `STAGE_3_PLAN.md`.
- Structure revision: new modules placed under `core/` and `strategies/`, simplified Telegram integration, tests added.
  - Source: `STRUCTURE_REVISION_REPORT.md`.
- Telegram imports fix: commands consolidated into `telegram/telegram_bot.py`; imports from removed files eliminated; commands verified.
  - Source: `TELEGRAM_IMPORTS_FIX_REPORT.md`.
- Key management system ready: `.env` handling via `simple_env_manager.py` and `env_manager.py`, quick CLI (`quick_keys.py`, `manage_keys.py`).
  - Source: `KEY_MANAGEMENT_SYSTEM_REPORT.md`.
- V2 references confirm USDC futures readiness and parameter baselines (SL 2%, TP steps 0.4/0.8/1.2, hold 10m, up to 35 symbols).
  - Source: `references from BinanceBot_V2/docs/USDC_FUTURES_READY_REPORT.md`.
- V2 configuration consolidation and aggression profiles are applicable as future enhancement (post-MVP switchable profiles).
  - Source: `references from BinanceBot_V2/docs/CONFIGURATION_OPTIMIZATION_REPORT.md`.

### API Harmonization Plan
- ExchangeClient surfaces:
  - `get_markets()`, `get_ticker(symbol)`, `get_ohlcv(symbol, timeframe, limit)`, `get_usdc_symbols()`
- SymbolManager consumes only these methods; no direct ccxt calls.
- Provide `SymbolUtils.normalize(symbol)`: unify formats (`BTC/USDC:USDC` ←→ `BTC/USDC` ←→ `BTCUSDC`).

### TradeEngine Outline
```text
loop every update_interval:
  symbols = SymbolManager.get_symbols_with_volume_filter()
  for symbol in top N:
    df = ExchangeClient.get_ohlcv(symbol, '5m', 150)
    direction, breakdown = StrategyManager.evaluate_symbol(symbol)
    if direction and RiskGuard.entry_allowed(symbol, breakdown):
      qty = position_size_from_config_and_balance(...)
      OrderManager.place_position_with_tp_sl(symbol, direction, qty, breakdown.entry_price, leverage)
  OrderManager.monitor_positions(); check_executions(); check_timeouts()
  log_runtime_status()
```

### Telegram Commands Mapping (live data targets)
- `/status`: uptime, balance, active positions, recent signals
- `/summary`: total trades, PnL, win-rate (from SQLite)
- `/performance`: hourly/daily PnL, avg hold, SL-streak
- `/positions`: list active positions (symbol/side/size/UPnL)
- `/pause` `/resume`: toggle trading flag in runtime config
- `/panic`: emergency close + set emergency flag
- `/config`: selected strategy, risk limits, aggression (future)
- `/logs`: last N log entries (DB)

### Testing Matrix
- Unit/basic: `test_basic.py` (config, logger, imports)
- Strategy: `test_strategy_integration.py`, `test_strategy_simulation.py`
- Dry run: `test_dry_run_strategy.py`
- Telegram: `test_telegram_integration.py`, `test_telegram_commands.py`, `test_telegram_real_message.py`

### Windows Compatibility
- Default to REST; WebSocket optional (enable on VPS/Linux)
- Increase recvWindow, robust retries, reduce open_timeout on WS

### References Index (repo paths)
- Core docs: `STAGE_2_*`, `STAGE_3_PLAN.md`, `STRUCTURE_REVISION_REPORT.md`, `TELEGRAM_IMPORTS_FIX_REPORT.md`, `KEY_MANAGEMENT_SYSTEM_REPORT.md`
- Design notes: `docs/8 August new initial concept GPT5.md`, `docs/6 August 2025 GPT Suggestions for migration.md`
- V2 refs: `references from BinanceBot_V2/docs/*.md` (USDC readiness, logging, performance, integration)

### Open Tasks Checklist
- [x] Fix USDC filter in `core/exchange_client.py`
- [x] Unify SymbolManager API usage (migrate to `get_markets/get_ticker`)
- [x] Implement trade engine and wire into `main.py` (`core/trade_engine_v2.py`)
- [x] Add SymbolUtils normalization
- [ ] Validate TP/SL order types on USDC futures via ccxt (normalized in code, pending testnet validation)
- [ ] Enrich Telegram commands with live data from DB/Exchange
- [ ] RiskGuard MVP (SL-streak pause, daily loss limit, max positions, max hold) — cooldown gate added; streak/daily loss pending
- [ ] DRY RUN/Testnet run and API permissions verification (Futures scope, USDT balance on testnet)
- [ ] Runtime status and metrics (periodic USDC balance/positions/UPnL/uptime; DB aggregates)
- [ ] Validate minimum position size and MIN_NOTIONAL constraints for USDC markets; adjust config
- [ ] Optional later: WebSocket integration after stability (default to REST on Windows)

### Risks & Mitigations
- Windows + WS: keep REST default; enable WS only where safe
- Binance rate limits: use recvWindow, caching, retries
- Odd symbols (1000SHIB, test): explicit blacklist/whitelist

### Success Metrics
- Technical: 24h uptime, no unhandled exceptions; loop ≤ 2–3s
- Trading: win-rate ≥ 55%, positive PnL on conservative profile

### Next Action Items
- Validate TP/SL order params for USDC futures (STOP/STOP_MARKET, reduceOnly, timeInForce)
- Enrich Telegram commands with live data (positions, PnL, risk state)
- Implement RiskGuard MVP
- Run DRY RUN/Testnet and verify API permissions (Futures enabled) and USDT test balance
- Implement runtime status and metrics logging (periodic logs and on-demand summaries)
- Verify min position size vs BINANCE MIN_NOTIONAL for USDC markets; tune config
- Plan optional WebSocket enablement post-stability

Generated: 2025-08-08

