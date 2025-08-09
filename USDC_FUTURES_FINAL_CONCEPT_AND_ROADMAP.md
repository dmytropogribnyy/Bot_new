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

-   **B‑lite в Stage D:** в конфиг добавляются **только** два поля — `tp_order_style`, `working_type`. Полная унификация конфига и нормализация символов выполняются позже (Stage B/C full).

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

## 3) Архитектура

### 3.1 Config (Pydantic)

Ключевые поля `.env`/runtime (RC1.1):

-   `TESTNET: bool` — окружение
-   `QUOTE_COIN: Literal["USDT","USDC"]` — quote (по умолчанию `USDC`)
-   `SETTLE_COIN: str` — обычно `USDC` (для USDⓈ‑M USDC совпадает с quote)
-   `LEVERAGE_DEFAULT: int` — плечо по умолчанию
-   `RISK_PER_TRADE_PCT: float` — риск на сделку от эквити в quote
-   `DAILY_DRAWDOWN_PCT: float` — дневной стоп
-   `MAX_CONCURRENT_POSITIONS: int` — параллельные позиции
-   **`working_type: Literal["MARK_PRICE","CONTRACT_PRICE"] = "MARK_PRICE"`** — тип цены для триггера SL/TP
-   **`tp_order_style: Literal["limit","market"] = "limit"`** — стиль TP (`TAKE_PROFIT` vs `TAKE_PROFIT_MARKET`)
-   Ключи API и тех. флаги (логирование, алерты, DRY‑RUN)

### 3.2 Символы и рынки

-   Нормализация: `perp_symbol(base, coin) -> f"{base}/{coin}:{coin}"`.
-   После `load_markets()` фильтр: `market["contract"] is True` **и** (`market["settle"] == SETTLE_COIN` или `market["quote"] == QUOTE_COIN`).
-   `default_symbols(coin)` → стартовый набор: BTC, ETH, BNB, SOL, ADA.

### 3.3 Exchange Layer

-   `ccxt.binanceusdm` (async), `set_sandbox_mode(TESTNET)`, `load_markets()`.
-   Установка плеча: `set_leverage(LEVERAGE_DEFAULT, symbol, {"marginMode": "isolated"})`.
-   Опции: `enableRateLimit=True`, `options.adjustForTimeDifference=True`.
-   **SL/TP:** всегда `reduceOnly=True`; `params["workingType"]=config.working_type`.
-   **TP стиль:** `"limit" → TAKE_PROFIT (price=tp, stopPrice=tp)`; `"market" → TAKE_PROFIT_MARKET (price=None, stopPrice=tp)`.
-   Ретраи и экспоненциальный бэкофф на сетевые/429/5xx.

### 3.4 User Data Stream / WS

-   `listenKey` (REST), keepalive \~30 мин.
-   Подписки: `ORDER_TRADE_UPDATE`, `ACCOUNT_UPDATE`.
-   Реконнект; после восстановления — **полная REST‑сверка** (ордера/позиции/баланс).
-   В RC1.1 допустимо держать WS выключенным до стабилизации REST.

### 3.5 OMS (Order Manager)

-   Единая точка `create/replace/cancel`, идемпотентный `clientOrderId`.
-   Повторы с джиттером; таймауты; чёткое логирование статусов.
-   Атомарные операции по TP/SL; уборка зависших ордеров при рестарте.
-   **TP параметризован через `tp_order_style` (limit/market).**
-   **SL/TP всегда с `reduceOnly=True` и `workingType` из конфигурации.**

### 3.6 Risk & Sizing

-   **RiskGuard:** централизованная проверка перед входом (`SL‑streak`, дневной убыток); блокирует новые входы.
-   Обязательный SL; дневной стоп блокирует новые входы.
-   Сайзинг по `RISK_PER_TRADE_PCT` от эквити в `QUOTE_COIN`, учёт `tickSize/stepSize`.
-   Лимиты: `MAX_CONCURRENT_POSITIONS`, максимум плеча, notional per symbol.

### 3.7 Strategy

-   Интерфейс Strategy (сигнал → вход/выход/кулдаун).
-   Подключена `scalping_v1`; выбор символов через `SymbolManager`.

### 3.8 Логи и наблюдаемость

-   Консоль/файл + SQLite‑агрегаты; снэпшоты `data/runtime_config.json`.
-   Алерты (Telegram/Email/Slack) для критических событий.

---

## 4) Поток выполнения (Runtime)

1. Загрузка конфига (`.env` → Pydantic → runtime JSON), автоподстановка `USDT` при `TESTNET=true`.
2. Инициализация `binanceusdm`, `set_sandbox_mode(TESTNET)`, `load_markets()`.
3. Фильтрация рынков; список символов; установка плеча.
4. Стратегии → `OrderManager`: всегда SL; TP по стилю конфигурации.
5. Health‑чек; уборка висячих ордеров; graceful shutdown.

---

## 5) Безопасность и отказоустойчивость

-   **Emergency shutdown:** отмена ордеров, закрытие позиций.
-   Холодный старт: полная ресинхронизация.
-   Ограничение убытка: per‑trade и per‑day; пауза входов после триггера.

---

## 6) Roadmap (RC1.1 → GA)

### Приоритетный порядок (Safety‑first)

1. **Фаза A** — Гигиена репозитория (**DONE/ONGOING**)
2. **Фаза D** — Клиент биржи + TP/SL параметризация (**ONGOING**)
3. **Фаза F** — Risk & Sizing + **RiskGuard** (**ONGOING**)
4. **Testnet smoke test**
5. **Фаза B** — Единый конфиг (**full**)
6. **Фаза C** — Символы и рынки (**full**)
7. **Фаза E** — User Data / WS
8. **Фазы G‑J** — по плану

— Дополнительно: тесты/CI, утилиты и деплой движутся параллельными мини‑этапами по готовности.

---

## 7) Open Tasks Checklist

-   [ ] Внедрить WS в проде: keepalive, реконнект, full sync после восстановления.
-   [ ] Расширить тесты сайзинга (`stepSize/tickSize`).
-   [ ] Обновить/добавить `quick_check.py` и команды Telegram.
-   [ ] Финальный аудит Risk/OMS (Opus 4.1) → GA.

---

## 8) Процедуры запуска

### 8.1 Testnet smoke‑test

1. `TESTNET=true` → sandbox; `load_markets()`; проверка `BTC/USDT:USDT`.
2. Тестовое place/cancel; корректные события (REST/WS).
3. Перезапуск: сверка ордеров/позиций; нет «висячих» заявок.

### 8.2 Prod go‑live (микролот)

1. `TESTNET=false`, `QUOTE_COIN=USDC`, `SETTLE_COIN=USDC`.
2. Проверить `*/USDC:USDC`; установить плечо.
3. Открыть/закрыть микролот; проверить логи/PnL; алерты.
4. Включить WS после 48 ч стабильности (RC1.2).

---

**Статус документа:** RC1.1. Синхронизирован с Execution Plan RC1.1; дальнейшие правки — через PR.
