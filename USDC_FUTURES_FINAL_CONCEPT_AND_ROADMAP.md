# Binance USDC Futures Bot — Final Concept & Roadmap (v2.3, RC1)

> **Source of Truth:** Specification / Architecture.
> Подробный пошаговый план выполнения — в документе _USDC Futures Bot — Execution Plan (Stages)_.
> Операторские инструкции и запуск — в _README.md_.

**Prod:** USDC‑контракты на USDⓈ‑Margined фьючах Binance.
**Testnet:** USDT‑контракты на Binance Futures Testnet.
Все расчёты размеров, баланса и PnL ведутся в **quote‑коине** (USDC/USDT).

Материал носит образовательный характер и **не является инвестиционным советом**.

---

## 1) Цели и принципы

-   **Прозрачность**: минимальная, читаемая архитектура; один источник правды для конфигурации.
-   **Безопасность**: обязательный SL, дневной стоп, отсутствие мартингейла, строгие лимиты плеча и notional.
-   **Предсказуемость**: идемпотентный OMS, детерминированный сайзинг, одинаковое поведение в Testnet/Prod.
-   **Надёжность**: health‑чек, ретраи с бэкоффом, корректное восстановление состояния после рестартов.

---

## 2) Операционные режимы

-   **DRY‑RUN** — без реальных ордеров; валидация логики.
-   **TESTNET (USDT)** — sandbox: ордера создаются на `binanceusdm` с `set_sandbox_mode(True)`; `quote_coin=USDT`.
-   **PROD (USDC)** — реальная торговля на USDC‑контрактах; `set_sandbox_mode(False)`, `quote_coin=USDC`.

Автопереключение: если `TESTNET=true` и `QUOTE_COIN` не задан — использовать `USDT`; иначе `USDC`.

---

## 3) Архитектура

### 3.1 Config (Pydantic)

Ключевые поля `.env`/runtime:

-   `TESTNET: bool` — окружение.
-   `QUOTE_COIN: str` — `USDT|USDC` (по умолчанию `USDC`).
-   `SETTLE_COIN: str` — `USDC` (совпадает с quote для USDⓈ‑M USDC).
-   `LEVERAGE_DEFAULT: int` — плечо по умолчанию.
-   `RISK_PER_TRADE_PCT: float` — риск на сделку от эквити в quote.
-   `DAILY_DRAWDOWN_PCT: float` — дневной стоп.
-   `MAX_CONCURRENT_POSITIONS: int` — параллельные позиции.
-   Ключи API и технические флаги (логирование, алерты, DRY‑RUN).

### 3.2 Символы и рынки

-   Нормализация: `perp_symbol(base, coin) -> f"{base}/{coin}:{coin}"`.
-   После `load_markets()` фильтр: `market["contract"] is True` **и** (`market["settle"] == SETTLE_COIN` или `market["quote"] == QUOTE_COIN`).
-   `default_symbols(coin)` → стартовый набор: BTC, ETH, BNB, SOL, ADA.

### 3.3 Exchange Layer

-   `ccxt.binanceusdm` (async), `set_sandbox_mode(TESTNET)`, `load_markets()`.
-   Установка плеча: `set_leverage(LEVERAGE_DEFAULT, symbol, {"marginMode": "isolated"})`.
-   Опции: `enableRateLimit=True`, `options.adjustForTimeDifference=True`.
-   Ретраи и экспоненциальный бэкофф на сетевые/429/5xx.

### 3.4 User Data Stream / WS

-   Создание `listenKey` (REST), keepalive каждые \~30 мин.
-   Подписки: `ORDER_TRADE_UPDATE`, `ACCOUNT_UPDATE`.
-   Реконнект с бэкоффом; после восстановления — **полная сверка** состояния по REST (открытые ордера, позиции, баланс).
-   В RC1 по умолчанию допускается REST‑обновление; WS включается после стабилизации.

### 3.5 OMS (Order Manager)

-   Единая точка `create/replace/cancel`, идемпотентный `clientOrderId`.
-   Повторы с джиттером; таймауты; чёткое логирование статусов.
-   Атомарные операции по TP/SL; уборка зависших ордеров при рестарте.

### 3.6 Risk & Sizing

-   Обязательный SL; дневной стоп блокирует новые входы.
-   Сайзинг по `RISK_PER_TRADE_PCT` от эквити в `QUOTE_COIN`, учёт `tickSize/stepSize`.
-   Лимиты: `MAX_CONCURRENT_POSITIONS`, максимум плеча, notional per symbol.

### 3.7 Strategy

-   Интерфейс Strategy (сигнал → вход/выход/кулдаун).
-   Подключена `scalping_v1`; выбор символов через `SymbolManager`.

### 3.8 Логи и наблюдаемость

-   Консоль/файл + SQLite агрегаты, снэпшоты `data/runtime_config.json`.
-   Алерты (Telegram/Email/Slack) для критических событий.

---

## 4) Поток выполнения (Runtime)

1. Загрузка конфига (`.env` → Pydantic → runtime JSON), автоподстановка `USDT` при `TESTNET=true`.
2. Инициализация `binanceusdm`, `set_sandbox_mode(TESTNET)`, `load_markets()`.
3. Фильтрация рынков; сбор стартового списка символов; установка плеча.
4. Запуск стратегий → сигнал → `OrderManager` (всегда с SL; опциональный TP).
5. Периодический health‑чек; уборка висячих ордеров; graceful shutdown.

---

## 5) Безопасность и отказоустойчивость

-   **Emergency shutdown** по Ctrl+C с отменой ордеров и закрытием позиций.
-   Холодный старт: полная ресинхронизация позиций/ордеров.
-   Ограничение убытка: per‑trade и per‑day; пауза входов после триггера.

---

## 6) Roadmap (RC1 → GA)

### Фаза A — Гигиена репозитория (DONE/ONGOING)

-   Чистка дублей, исключение `references ...` из рантайма, фикс версии Python, `ruff/mypy` строгий профиль.

### Фаза B — Единый конфиг (DONE)

-   Поля `TESTNET/QUOTE_COIN/SETTLE_COIN`, автопереключение USDT в тестнете, `.env.example`.

### Фаза C — Символы и рынки (DONE)

-   `perp_symbol`, фильтры по контрактности/settle, `default_symbols`.

### Фаза D — Клиент биржи (DONE/ONGOING)

-   `binanceusdm`, sandbox‑режим, `load_markets`, плечо/маржа, бэкофф/ретраи.

### Фаза E — User Data / WS (NEXT)

-   Подключить WS в проде: keepalive, реконнект, полная сверка; алерты деградации.
    **Критерий готовности:** стабильная работа 7 дней без рассинхронизации.

### Фаза F — Risk & Sizing (ONGOING)

-   Тонкая настройка сайзинга, проверка граничных случаев `stepSize/tickSize`, стресс‑тест дневного стопа.

### Фаза G — Strategy (ONGOING)

-   Включение альтернативных фильтров волатильности/объёма; кулдаун после SL‑серии.

### Фаза H — Утилиты/скрипты (NEXT)

-   `quick_check.py` (health‑чек), расширение Telegram‑команд.

### Фаза I — Тесты (ONGOING)

-   Юниты + интеграция на тестнете (place/cancel, WS, реконнект/ресинк).
    **Критерий готовности:** зелёные прогоны в CI для USDT (testnet) и USDC (prod‑конфиг).

### Фаза J — Деплой (NEXT)

-   Dockerfile/compose, лог‑ротация, оповещения, базовый мониторинг.

---

## 7) Open Tasks Checklist (синхронизировано с README)

-   [ ] Завершить внедрение WS в проде: keepalive, реконнект, post‑reconnect full sync.
-   [ ] Расширить тесты сайзинга: валидация `stepSize/tickSize` и граничных значений.
-   [ ] Добавить `quick_check.py` и команды Telegram: `/status`, `/pause`, `/resume`, `/panic`.
-   [ ] Вынести метрики PnL/эквити в отдельный агрегат (для дашборда).
-   [ ] Финальный аудит Risk/OMS (точечно через Opus 4.1) → GA.

---

## 8) Процедуры запуска

### 8.1 Testnet smoke‑test

1. `TESTNET=true` → инициализация `binanceusdm` в sandbox.
2. `load_markets()`; валидация наличия `BTC/USDT:USDT`.
3. Создать/отменить тестовый ордер; убедиться в корректных событиях (REST/WS, если включён).
4. Перезапуск: сверка открытых ордеров/позиций; отсутствуют «висячие» заявки.

### 8.2 Prod go‑live (микролот)

1. `TESTNET=false`, `QUOTE_COIN=USDC`, `SETTLE_COIN=USDC`.
2. Загрузить рынки; убедиться в наличии `*/USDC:USDC` для выбранных базовых активов.
3. Открыть/закрыть микролот; проверить логи/PnL; алерты не сработали.
4. Включить WS после 48 часов стабильности (этап RC1.1).

---

## 9) Приложения

### 9.1 Символьный формат (шпаргалка)

-   Прод: `BTC/USDC:USDC`, `ETH/USDC:USDC`, ...
-   Тестнет: `BTC/USDT:USDT`, `ETH/USDT:USDT`, ...

### 9.2 Мини‑пример ccxt

```python
import asyncio, ccxt.async_support as ccxt

async def boot(testnet: bool):
    ex = ccxt.binanceusdm({
        "apiKey": API_KEY,
        "secret": API_SECRET,
        "enableRateLimit": True,
        "options": {"adjustForTimeDifference": True},
    })
    ex.set_sandbox_mode(testnet)
    await ex.load_markets()
    quote = "USDT" if testnet else "USDC"
    symbol = f"BTC/{quote}:{quote}"
    await ex.set_leverage(5, symbol, {"marginMode": "isolated"})
    return ex
```

—

**Статус документа:** RC1. Обновления вносятся синхронно с `README.md`. Доп. заметки и решения фиксируются в коммит‑сообщениях и CHANGELOG.
