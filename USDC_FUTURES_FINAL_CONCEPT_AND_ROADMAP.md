# Binance USDC Futures Bot — Final Concept & Roadmap (v2.4, RC1.2)

> **Role:** Specification / Architecture.
> **Exec plan:** см. _USDC Futures Bot — Execution Plan (Stages) — RC1.2_.
> **Ops:** см. _README.md_.

## 1) One-liner
USDC Futures Bot — торговый бот для Binance Futures с безопасной архитектурой (RiskGuard, Audit), унифицированным конфигом и корректными TP/SL режимами. CI контролирует структуру и async-тесты.

## 2) Architecture overview
- **Core**: OrderManager, Strategy, RiskGuard (лимиты, стрик), Unified Config.
- **Exchange Client**: параметры исполнения (`working_type`, `tp_order_style`, `reduceOnly`), UM-эндпоинты, listenKey.
- **WS/REST**: WS с keepalive и fallback на REST.
- **Audit (P-block)**: tamper-evident журнал (hash-цепочка), UTC-метки, редакция секретов.
- **Tests**: pytest + pytest-asyncio; валидатор структуры.

## 3) Execution order (Safety-first, RC1.2)
- **A — Repo Hygiene:** выполнено (cleanup/validate, структура тестов).
- **D — Exchange Client (B-lite):** `tp_order_style`, `working_type` — **выполнено (подтверждено CI)**.
- **F — Risk & Sizing:** выполнено (RiskGuard, precision-gate).
- **B/C — Unified Config & Symbols:** выполнено (тесты зелёные).
- **E — WS → OMS:** осталось оформить события и acceptance-тесты.
- **P0–P5 — GPT Perspectives:** после E.

## 4) Configuration (high-level)
- **Unified Config** (env→model): строгая валидация, сохранение/загрузка, миграция.
- `working_type`: _MARK_PRICE_ / _LAST_PRICE_ (по умолчанию из конфига).
- `tp_order_style`: _TAKE_PROFIT_ / _TAKE_PROFIT_MARKET_.
- Risk-параметры: дневной лимит, SL-стрик, minNotional/precision-гейты.

## 5) Order execution (B-lite, done)
- Все TP/SL ставятся `reduceOnly=True`.
- Режим `workingType` читается из конфига.
- Поддержка `TAKE_PROFIT` и `TAKE_PROFIT_MARKET`.
- Интеграционные async-тесты в CI зелёные.

## 6) WebSocket → OMS (pending)
- Цель: события `ORDER_TRADE_UPDATE`, `ACCOUNT_UPDATE` попадают в OMS и обновляют состояние (позиции, баланс).
- Keepalive listenKey, авто-релистен; безопасный shutdown.
- **Acceptance:** тесты с моками событий зелёные; fallback WS→REST задокументирован.

## 7) Residual items (к закрытию ближайшим PR)
- Stage E: провести проводку событий WS→OMS + добавить acceptance-тесты.
- Deprecation cleanup (наша сторона): `datetime.utcnow()` → `datetime.now(datetime.UTC)`; Pydantic v2 `.dict()` → `.model_dump()`; заменить `return` в тестах на `assert`; закрыть `Unclosed client session` фикстурой `await exchange.close()`.

## 8) CI/CD baseline
- **requirements-dev.txt**: `pytest`, `pytest-asyncio`, `pytest-mock` (и линтеры/тайпчекеры — по желанию).
- **pytest.ini**: `asyncio_mode = auto`, регистрация маркера `asyncio`.
- **CI.yml**: установка prod+dev deps (или fallback), `env.PYTHONPATH` на корень, `validate_project.py`, `pytest -v`, sanity-grep против жёстких USDC→dapi/dstream привязок.
- **Кнопка Run workflow** (`workflow_dispatch`) и `concurrency` для избежания гонок.

## 9) Acceptance gates (release-ready)
- CI зелёный (включая async-тесты и валидатор).
- WS→OMS протестирован моками событий; fallback WS→REST задокументирован.
- RiskGuard отсекает вход после превышения лимитов; precision/notional-гейты стабильны.
- Audit-лог непрерывен (hash-цепочка), UTC-метки корректны.

## 10) Operability (pre-testnet)
- `.env` — только тестнет-ключи; без прод-секретов.
- `python main.py --dry-run` → OK; `python main.py --once` → OK.
- Логи ротируются; audit-лог активен; emergency-shutdown корректен.
