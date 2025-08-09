# Binance USDC Futures Bot (v2.3) — Release Candidate (RC1)

Лёгкий торговый бот для USDⓈ‑Margined фьючерсов Binance.
**Prod:** USDC‑контракты. **Testnet:** USDT‑контракты. Все расчёты размеров, баланса и PnL ведутся в **quote‑коине** (USDC/USDT).

Материал носит образовательный характер и **не является инвестиционным советом**.

-   Финальная концепция и Roadmap: [`USDC_FUTURES_FINAL_CONCEPT_AND_ROADMAP.md`](USDC_FUTURES_FINAL_CONCEPT_AND_ROADMAP.md)
-   **Статус проекта:** RC1 (09.08.2025)

    -   Тестнет‑прогон: выполнен
    -   Emergency shutdown (Ctrl+C): реализован
    -   Автозакрытие позиций и уборка «висячих» ордеров: реализованы
    -   Продовые WS‑стримы включаются после стабилизации (по умолчанию REST)

## 🧭 Doc Map

-   **Spec:** [USDC_FUTURES_FINAL_CONCEPT_AND_ROADMAP.md](USDC_FUTURES_FINAL_CONCEPT_AND_ROADMAP.md)
-   **Execution:** _USDC Futures Bot — Execution Plan (Stages)_
-   **Operator:** _README.md_

---

## 📂 Структура

-   `main.py` — точка входа (async), инициализация, основной цикл
-   `core/`

    -   `config.py` — конфигурация (Pydantic + .env + runtime JSON)
    -   `exchange_client.py` — слой биржи: `ccxt.binanceusdm`, sandbox/testnet, тайм‑синхронизация, бэкофф/ретраи
    -   `symbol_utils.py` — нормализация символов: \`perp_symbol(base, coin) -> f"{base}/{coin}:{coin}"
    -   `symbol_manager.py` — загрузка и фильтрация рынков (contract + settle/quote)
    -   `order_manager.py` — идемпотентные `create/replace/cancel`, `clientOrderId`, логирование
    -   `risk.py` — лимиты: `risk_per_trade_pct`, `daily_drawdown_pct`, `max_concurrent_positions`
    -   `sizing.py` — размер позиции в quote‑коине
    -   `unified_logger.py` — логи: консоль/файл/SQLite/Telegram
    -   `trade_engine_v2.py` — скан/сигналы/вход; интеграция со стратегией

-   `strategies/`

    -   `base_strategy.py`, `scalping_v1.py`

-   `telegram/telegram_bot.py` — уведомления и команды управления
-   `tests/*.py` — базовые и интеграционные тесты
-   `data/` — конфиги и БД (`data/trading_bot.db`, `data/runtime_config.json`)

---

## ⚙️ Возможности

-   Асинхронная архитектура (asyncio), модульность
-   Управление риском: дневной лимит, ограничение одновременно открытых позиций, обязательный SL
-   Ступенчатый TP, уборка зависших ордеров
-   Символы под USDC/USDT: фильтры по контрактности/объёму/волатильности
-   Telegram‑команды: статус, пауза/резюм, emergency‑стоп
-   Логи и аналитика: файл, SQLite, агрегаты и runtime‑снапшоты
-   Режимы: DRY‑RUN / TESTNET (USDT) / PROD (USDC)

---

## ✅ Требования

-   Python 3.11+
-   `ccxt`, `pydantic`, `websockets`, `python-dotenv`, `uvloop` (Linux/macOS), `ruff`, `mypy`

---

## 🔧 Установка

```bash
pip install -r requirements.txt
cp .env.example .env
# заполните API ключи; TESTNET=true для тестнета
```

### Переменные окружения (.env)

```env
# Binance API
API_KEY=...
API_SECRET=...

# Окружение
TESTNET=true            # true → USDT и sandbox; false → прод
QUOTE_COIN=USDC         # по умолчанию USDC; при TESTNET=true можно опустить — будет USDT
SETTLE_COIN=USDC

# Торговые настройки
LEVERAGE_DEFAULT=5
RISK_PER_TRADE_PCT=0.5
DAILY_DRAWDOWN_PCT=3.0
MAX_CONCURRENT_POSITIONS=2
MIN_POSITION_SIZE=10.0   # в quote-коине (USDC/USDT)
```

---

## 🧰 Пример инициализации ccxt

```python
import asyncio, ccxt.async_support as ccxt

API_KEY = "..."
API_SECRET = "..."
TESTNET = True  # False для продакшена

async def init():
    ex = ccxt.binanceusdm({
        "apiKey": API_KEY,
        "secret": API_SECRET,
        "enableRateLimit": True,
        "options": {"adjustForTimeDifference": True},
    })
    ex.set_sandbox_mode(TESTNET)
    await ex.load_markets()

    quote = "USDT" if TESTNET else "USDC"
    symbol = f"BTC/{quote}:{quote}"
    await ex.set_leverage(5, symbol, {"marginMode": "isolated"})
    return ex, symbol

asyncio.run(init())
```

---

## ▶️ Запуск

```bash
# Dry‑run
python main.py --dry

# Testnet (USDT)
export TESTNET=true
python main.py

# Prod (USDC)
export TESTNET=false
python main.py
```

### Быстрый чек (Testnet)

1. `python quick_check.py` — проверка рынков/плеча/доступов.
2. Создание/отмена тестового ордера; проверка статусов через WS.
3. Перезапуск — сверка позиций/ордеров.

---

## 🧪 Тесты

-   Юнит‑тесты: `perp_symbol`, фильтрация рынков, сайзинг/риск.
-   Интеграционные (Testnet): place/cancel, приём событий WS, реконнект + ресинк.

---

## 🚀 Деплой

-   Dockerfile (+ optional compose), переменные окружения через `.env`.
-   Логи: ротация.
-   Алерты: Telegram/Email/Slack (по желанию).

---

## ⚠️ Безопасность

-   Ключи только в `.env`. Никогда не коммитить реальные ключи.
-   Включать реальную торговлю только после успешного DRY RUN и тестнета.

—

© Binance USDC Futures Bot v2.3 — актуальная документация и статус поддерживаются в этом README и сопроводительных `.md` файлах.
