# Binance USDC Futures Bot (v2.4) — Release Candidate (RC1.1)

Лёгкий торговый бот для USDⓈ‑Margined фьючерсов Binance.
**Prod:** USDC‑контракты. **Testnet:** USDT‑контракты. Все расчёты размеров, баланса и PnL ведутся в **quote‑коине** (USDC/USDT).

Материал носит образовательный характер и **не является инвестиционным советом**.

-   **Финальная концепция и Roadmap:** [`USDC_FUTURES_FINAL_CONCEPT_AND_ROADMAP.md`](USDC_FUTURES_FINAL_CONCEPT_AND_ROADMAP.md) (RC1.1)
-   **Execution Plan:** [`USDC Futures Bot — Execution Plan (Stages) — RC1.1`](USDC%20Futures%20Bot%20%E2%80%94%20Execution%20Plan%20%28Stages%29%20%E2%80%94%20RC1.1.md)
-   **GPT Perspectives & Strategies:** [`GPT PERSPECTIVES & STRATEGIES INCOME.md`](GPT%20PERSPECTIVES%20%26%20STRATEGIES%20INCOME.md)
-   **Статус проекта:** RC1.1 (09.08.2025)

    -   Тестнет‑прогон: выполнен
    -   Emergency shutdown (Ctrl+C): реализован
    -   Автозакрытие позиций и уборка «висячих» ордеров: реализованы
    -   TP/SL параметризация: реализована
    -   RiskGuard: реализован
    -   GPT Perspectives (Tier A/B/C, auto‑rationale, audit trail): реализованы частично (P0–P2)
    -   Продовые WS‑стримы включаются после стабилизации (по умолчанию REST)

---

## 🧭 Doc Map

-   **Spec:** `USDC_FUTURES_FINAL_CONCEPT_AND_ROADMAP.md`
-   **Execution:** `USDC Futures Bot — Execution Plan (Stages) — RC1.1.md`
-   **Perspectives:** `GPT PERSPECTIVES & STRATEGIES INCOME.md`
-   **Operator:** _README.md_ (этот файл)

---

## 📂 Структура

-   `main.py` — точка входа (async), инициализация, основной цикл
-   `core/`

    -   `config.py` — конфигурация (Pydantic + .env + runtime JSON)
    -   `exchange_client.py` — слой биржи (ccxt.binanceusdm, sandbox/testnet, тайм‑синхронизация, бэкофф/ретраи)
    -   `symbol_utils.py` / `symbol_manager.py` — нормализация и фильтрация рынков
    -   `order_manager.py` — идемпотентные операции, clientOrderId, логирование
    -   `risk.py` / `risk_guard.py` — лимиты, SL‑streak/daily‑loss блокировки
    -   `sizing.py` — размер позиции в quote‑коине
    -   `audit_logger.py` — аудит‑лог с sha256‑цепочкой (P4)
    -   `trade_engine_v2.py` — логика сигналов и исполнения

-   `strategies/` — базовые стратегии (`base_strategy.py`, `scalping_v1.py`)
-   `telegram/` — уведомления и команды управления
-   `tests/` — юнит‑ и интеграционные тесты
-   `data/` — конфиги и БД (`runtime_config.json`, `trading_bot.db`)

---

## ⚙️ Возможности

-   Асинхронная модульная архитектура
-   Управление риском: дневной лимит, ограничение позиций, обязательный SL
-   **RiskGuard:** блокировка после SL‑streak и при дневном убытке
-   **TP/SL параметризация:** limit/market, `workingType` для триггеров
-   Символы под USDC/USDT с фильтрацией
-   Telegram‑команды: статус, пауза/резюм, emergency‑стоп
-   Логи: файл, SQLite, агрегаты, runtime‑снапшоты
-   **GPT Perspectives:**

    -   Trader/Risk/Execution/Capital/Compliance Lens
    -   Автоматическое обоснование действий (Decision Rationale)
    -   Audit trail с sha256
    -   Tier A/B/C стратегии

-   Режимы: DRY‑RUN / TESTNET (USDT) / PROD (USDC)

---

## ✅ Требования

-   Python 3.12+
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
API_KEY=...
API_SECRET=...
TESTNET=true
QUOTE_COIN=USDC
SETTLE_COIN=USDC
LEVERAGE_DEFAULT=5
RISK_PER_TRADE_PCT=0.5
DAILY_DRAWDOWN_PCT=3.0
MAX_CONCURRENT_POSITIONS=2
MIN_POSITION_SIZE=10.0
WORKING_TYPE=MARK_PRICE
TP_ORDER_STYLE=limit
MAX_SL_STREAK=3
STRATEGY_TIER=A
```

> `STRATEGY_TIER`: A — консервативная, B — сбалансированная, C — агрессивная.

---

## 🧰 Пример инициализации ccxt

```python
import asyncio, ccxt.async_support as ccxt

async def init():
    ex = ccxt.binanceusdm({
        "apiKey": "...",
        "secret": "...",
        "enableRateLimit": True,
        "options": {"adjustForTimeDifference": True},
    })
    ex.set_sandbox_mode(True)
    await ex.load_markets()
    symbol = "BTC/USDT:USDT"
    await ex.set_leverage(5, symbol, {"marginMode": "isolated"})
    return ex, symbol

asyncio.run(init())
```

---

## ▶️ Запуск

```bash
python main.py --dry         # Dry-run
export TESTNET=true && python main.py   # Testnet
export TESTNET=false && python main.py  # Prod
```

---

## 🧪 Тесты

-   Юнит‑тесты: конфиг, символы, RiskGuard, sizing
-   Интеграционные: Testnet place/cancel, WS поток, реконнект + ресинк

---

## 🚀 Деплой

-   Dockerfile/compose
-   Логи: ротация
-   Алерты: Telegram/Email/Slack

---

## ⚠️ Безопасность

-   Ключи только в `.env`
-   Прод включать только после DRY RUN и тестнета

---

© Binance USDC Futures Bot v2.4 RC1.1
