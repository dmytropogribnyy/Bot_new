# Binance USDC Futures Bot — Final Concept & Roadmap (v2.4, RC1.1)

> **Source of Truth:** Specification / Architecture.
> Пошаговый план выполнения — в _USDC Futures Bot — Execution Plan (Stages) — RC1.1_.
> Операторские инструкции — в _README.md_.

**Prod:** USDC‑контракты на USDⓈ‑Margined фьючах Binance.
**Testnet:** USDT‑контракты на Binance Futures Testnet.
Все расчёты размеров, баланса и PnL ведутся в **quote‑коине** (USDC/USDT).

Материал носит образовательный характер и **не является инвестиционным советом**.

---

## Execution order (RC1.1, Safety‑first)

**A → D (B‑lite) → F → Smoke (testnet) → B (full) → C (full) → E → G/H/I/J**

-   **B‑lite в Stage D:** в конфиг добавляются **только** `tp_order_style`, `working_type`. Полная унификация конфига и нормализация символов выполняются позже (Stage B/C full).

---

## 1) Цели и принципы

-   **Прозрачность:** минимальная архитектура; один источник правды для конфигурации.
-   **Безопасность:** обязательный SL, дневной стоп, отсутствие мартингейла, строгие лимиты плеча и notional.
-   **Предсказуемость:** идемпотентный OMS, детерминированный сайзинг, одинаковое поведение в Testnet/Prod.
-   **Надёжность:** health‑чек, ретраи с бэкоффом, корректное восстановление состояния после рестартов.

---

## 2) Операционные режимы

-   **DRY‑RUN** — без реальных ордеров; валидация логики.
-   **TESTNET (USDT)** — sandbox: `set_sandbox_mode(True)`; `quote_coin=USDT`.
-   **PROD (USDC)** — реальная торговля: `set_sandbox_mode(False)`; `quote_coin=USDC`.

Автопереключение: если `TESTNET=true` и `QUOTE_COIN` не задан — использовать `USDT`; иначе `USDC`.

---

## 3) Архитектура и ключевые компоненты

### 3.1 Config (Pydantic)

Ключевые поля `.env`/runtime (RC1.1):

-   `TESTNET`, `QUOTE_COIN`, `SETTLE_COIN`, `LEVERAGE_DEFAULT`, `RISK_PER_TRADE_PCT`, `DAILY_DRAWDOWN_PCT`, `MAX_CONCURRENT_POSITIONS`.
-   `working_type`: `MARK_PRICE` или `CONTRACT_PRICE`.
-   `tp_order_style`: `limit` или `market`.
-   API ключи, флаги логирования, алертов и DRY‑RUN.

### 3.2 Символы и рынки

-   Нормализация: `perp_symbol(base, coin) -> f"{base}/{coin}:{coin}"`.
-   Фильтр по контракту и валютам settle/quote.
-   Дефолт: BTC, ETH, BNB, SOL, ADA.

### 3.3 Exchange Layer

-   CCXT (async), `set_sandbox_mode`, `load_markets()`.
-   Параметры клиента: `enableRateLimit=True`, `adjustForTimeDifference=True`.
-   Установка плеча, reduceOnly=True, `workingType` и стиль TP.
-   Ретраи с экспоненциальным бэкоффом.

### 3.4 User Data Stream / WS

-   Keepalive \~30 мин, подписки на `ORDER_TRADE_UPDATE` и `ACCOUNT_UPDATE`.
-   Реконнект с полной REST‑сверкой.
-   WS можно держать выключенным до стабилизации REST.

### 3.5 OMS

-   Идемпотентные операции с `clientOrderId`.
-   Атомарность TP/SL; уборка зависших ордеров при рестарте.

### 3.6 Risk & Sizing

-   RiskGuard: проверка SL‑streak, дневных лимитов.
-   Сайзинг по `RISK_PER_TRADE_PCT` от эквити, учёт `tickSize/stepSize`.

### 3.7 Strategy

-   Подключена `scalping_v1` через `SymbolManager`.

### 3.8 Логи и наблюдаемость

-   Консоль/файл, SQLite‑агрегаты, runtime_config.json.
-   Алерты в Telegram/Email/Slack.

---

## 4) Поток выполнения (Runtime)

1. Загрузка конфига.
2. Инициализация биржи.
3. Фильтрация рынков, установка плеча.
4. Запуск стратегий через OMS.
5. Health‑чек, уборка ордеров.
6. Graceful shutdown.

---

## 5) Безопасность и отказоустойчивость

-   Emergency shutdown: отмена ордеров, закрытие позиций.
-   Холодный старт: полная ресинхронизация.
-   Ограничения по убыткам.

---

## 6) Roadmap (RC1.1 → GA)

1. Stage 1 — TP/SL параметризация.
2. Stage 2 — RiskGuard.
3. Stage 3 — WS/REST.
4. Stage 4 — Emergency shutdown.
5. Stage P0–P5 — GPT Perspectives.

---

## 7) Open Tasks Checklist

-   WS в проде.
-   Расширение тестов сайзинга.
-   Обновить quick_check.py.
-   Финальный аудит Risk/OMS.

---

## 8) Процедуры запуска

### Testnet smoke‑test

-   Проверка базовых операций и синхронизации.

### Prod go‑live (микролот)

-   Минимальный объём, проверка логов и алертов.
-   Включение WS после стабилизации.

---

## GPT Perspectives — интеграция

**Цели:** объяснимость решений и аудит, формализация риск‑допущений и доходности.

-   Trader Lens, Risk Lens, Execution/SRE Lens, Capital Lens, Compliance Lens.
-   Правила auto‑rationale, откаты при превышении лимитов, деградация WS→REST.
-   Tier A/B/C со своим профилем риска и TP/SL.
-   Артефакты: decision_record, audit.jsonl.

**Acceptance:** параметр strategy.tier, откаты, сводки при shutdown.

---

**Примечание:** Материал носит образовательный характер и не является финансовым советом.
