## Binance USDC Futures Bot — Final Concept and Roadmap (v2.2)

### Goals and KPIs
- Start: 400 USDC
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
- USDC market detection: ensure quote == USDC and correct market type (swap/future)
- Unify `SymbolManager` with `ExchangeClient` API (get_markets/get_ticker/get_ohlcv)
- Add `TradeEngine` and integrate into main loop
- Normalize symbol format across modules

### Critical Code References (current repo)
- USDC symbols filter (fix quote check):
  - File: `core/exchange_client.py`
  - Current snippet indicates USDT filter inside a method intended for USDC:
    ```
    async def get_usdc_futures_symbols(self) -> List[str]:
        # ...
        for symbol, market in markets.items():
            if (market['type'] == 'future' and
                market['quote'] == 'USDT' and   # <-- should be 'USDC'
                market['active']):
                usdc_symbols.append(symbol)
    ```
  - Action: change `'USDT'` → `'USDC'`; verify `type` ('swap' vs 'future') per ccxt market schema and include both where needed.
- API mismatch: `SymbolManager` uses `fetch_markets()` but `ExchangeClient` provides `get_markets()`.
  - File: `core/symbol_manager.py` calling `self.exchange.fetch_markets()`.
  - Action: either add `fetch_markets()` wrapper in `ExchangeClient` or replace usage with `get_markets()` to keep single API.
- Main loop lacks entry path (no TradeEngine scan):
  - File: `main.py`, trading loop calls only monitors/timeouts.
  - Action: implement `core/trade_engine.py` and call it per tick to scan/evaluate/execute.

### What we adopt from V2 (References)
- Robust retry/rate-limit/caching patterns (simplified)
- RiskManager ideas (SL-streak, daily loss, adaptive later)
- LeverageManager concept for ATR/win-rate (post-MVP)
- WebSocketManager pattern with strict fallback (post-stability)

### Roadmap
Stage 1 — Stabilize Core (Day 1–2)
- Fix USDC filters; unify markets/ticker/ohlcv API; symbol normalization
Acceptance: ≥25 valid USDC symbols; tests pass (basic, strategy integration)

Stage 2 — TradeEngine + Pipeline (Day 3–4)
- Implement `core/trade_engine.py`, integrate into `main.py`
Acceptance: DRY RUN creates 2–3 simulated entries, TP/SL placed, logs + Telegram OK

Stage 3 — RiskGuard MVP (Day 5)
- SL-streak pause, daily loss limit, max positions, max hold
Acceptance: auto-pause on SL-streak, daily limit stop, visible in Telegram

Stage 4 — Telegram UX (Day 6)
- Live data for `/status`, `/summary`, `/performance`, `/positions`, `/pause`, `/resume`, `/panic`, `/aggression`
Acceptance: all commands return actual data; alerts on executions

Stage 5 — Runtime & Logging (Day 7)
- Periodic runtime status: balance, positions, PnL, uptime; DB aggregates
Acceptance: periodic logs and on-demand summaries

Stage 6 — Real Data (Week 2)
- Testnet first, then small prod; safe limits
Acceptance: stable markets/tickers/ohlcv; successful testnet orders

Stage 7 — Profit Optimization (Week 3)
- Tune strategy thresholds; add LeverageManager; refine stepped TP
Acceptance: net-positive PnL, win-rate ≥ 55%

Stage 8 — Optional WebSocket (Week 4)
- Realtime ticker with robust fallback
Acceptance: no regressions; stable on VPS/Linux

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
- [ ] Fix USDC filter in `core/exchange_client.py`
- [ ] Unify SymbolManager API usage
- [ ] Implement `core/trade_engine.py` and wire into `main.py`
- [ ] Enrich Telegram commands with live data from DB/Exchange
- [ ] Add SymbolUtils normalization
- [ ] Validate TP/SL order types on USDC futures via ccxt

### Risks & Mitigations
- Windows + WS: keep REST default; enable WS only where safe
- Binance rate limits: use recvWindow, caching, retries
- Odd symbols (1000SHIB, test): explicit blacklist/whitelist

### Success Metrics
- Technical: 24h uptime, no unhandled exceptions; loop ≤ 2–3s
- Trading: win-rate ≥ 55%, positive PnL on conservative profile

### Next Action Items
- Fix USDC filter; unify SymbolManager↔ExchangeClient; add symbol utils
- Implement TradeEngine and wire into `main.py`
- Enrich Telegram commands with live data

Generated: 2025-08-08

