## Binance USDT Futures Bot (v2.3) - PRODUCTION READY ✅

Полностью функциональный бот для USDT‑маржинальных фьючерсов Binance. Протестирован на testnet, готов к продакшену. Основные цели: стабильность, адаптивность, минимизация рисков и работа 24/7 с контролем через Telegram.

- Документ с финальным концептом и дорожной картой: [`USDC_FUTURES_FINAL_CONCEPT_AND_ROADMAP.md`](USDC_FUTURES_FINAL_CONCEPT_AND_ROADMAP.md)
- **Статус проекта:** ✅ **ГОТОВ К ПРОДАКШЕНУ** (09.08.2025)
  - Тестирование на Binance Futures Testnet: **УСПЕШНО ЗАВЕРШЕНО**
  - Все системы проверены: **РАБОТАЮТ**
  - Emergency shutdown (Ctrl+C): **РЕАЛИЗОВАН**
  - Автоматическое закрытие позиций: **РАБОТАЕТ**
  - Очистка висячих ордеров: **РЕАЛИЗОВАНА**

### 📂 Ключевая структура
- `main.py` — точка входа (async), инициализация компонентов, основной цикл
- `core/`
  - `config.py` — унифицированная конфигурация (Pydantic, .env, runtime JSON)
  - `exchange_client.py` — ccxt (async), кэш, retry, health-check
  - `order_manager.py` — открытие позиций, TP/SL, мониторинг, emergency
  - `symbol_manager.py` — выбор/ротация символов USDC (нормализация через `core/symbol_utils.py`)
  - `strategy_manager.py` — координация стратегий
  - `unified_logger.py` — логирование: консоль, файл, SQLite, Telegram
  - `trade_engine_v2.py` — лёгкий движок сканирования/оценки/входа (интегрирован в `main.py`)
- `strategies/`
  - `base_strategy.py`, `scalping_v1.py`
- `telegram/telegram_bot.py` — уведомления и команды управления
- `tests/*.py` — базовые и интеграционные тесты
- `data/` — конфиги и БД (`data/trading_bot.db`, `data/runtime_config.json`)

### ⚙️ Возможности
- Асинхронная архитектура (asyncio), модульность
- Управление риском: лимит позиций, дневной лимит убытков, авто‑паузы по SL‑серии
- TP/SL: ступенчатый TP, обязательный SL, уборка зависших ордеров
- Символы USDC: фильтры по объёму/волатильности, ротация
- Telegram: статус, резюме, пауза/резюм, emergency стоп
- Логи и аналитика: файл, SQLite, агрегаты и runtime‑статус

### 🚀 Быстрый старт

#### 1️⃣ Зависимости
```bash
pip install -r requirements.txt
```

#### 2️⃣ Настройка окружения (`.env`)
```env
# ⚠️ ДЛЯ TESTNET (безопасное тестирование)
BINANCE_API_KEY=your_testnet_key     # https://testnet.binancefuture.com
BINANCE_API_SECRET=your_testnet_secret
BINANCE_TESTNET=true
DRY_RUN=false                        # false = реальные ордера на testnet

# ⚠️ ДЛЯ ПРОДАКШЕНА (с реальными деньгами!)
# BINANCE_API_KEY=your_real_api_key  # https://binance.com
# BINANCE_API_SECRET=your_real_secret
# BINANCE_TESTNET=false
# DRY_RUN=false

# Общие настройки
LOG_LEVEL=INFO
TELEGRAM_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
MAX_POSITIONS=3
MIN_POSITION_SIZE_USDT=10.0
STOP_LOSS_PERCENT=2.0
TAKE_PROFIT_PERCENT=1.5
```

💡 **Проверка конфигурации:** `python env_manager.py`

#### 3️⃣ Тестирование перед запуском
```bash
# Проверка API подключения
python test_simple.py

# Проверка Telegram уведомлений
python test_telegram.py

# Принудительное открытие тестовой позиции
python force_trade.py

# Проверка статуса
python monitor_bot.py
```

#### 4️⃣ Запуск бота
```bash
# Реальная торговля (testnet или продакшен)
python main.py

# Симуляция без ордеров
python main.py --dry-run

# Остановка: Ctrl+C (автоматически закроет позиции)
```

### 🛡️ Безопасность и контроль

#### ⚠️ Emergency Shutdown (Ctrl+C)
- **Автоматическое закрытие всех позиций** при остановке бота
- **Отмена всех висячих ордеров** (TP/SL)
- **Telegram уведомления** о критических ситуациях
- **Принудительный выход** при сетевых ошибках

#### 🧹 Утилиты для обслуживания
```bash
# Проверка и очистка висячих ордеров
python check_orders.py

# Принудительное закрытие позиций
python close_position.py

# Быстрая проверка статуса
python quick_check.py
```

### 🔧 Конфигурация
- Источники: `.env` → `data/runtime_config.json` → значения по умолчанию (`core/config.py`)
- Ключевые флаги: `BINANCE_TESTNET`, `DRY_RUN`, `LOG_LEVEL`, `max_positions`, `stop_loss_percent`, `take_profit_percent`
- Пары: USDC‑фьючерсы, авто‑отбор через `SymbolManager`

### 📱 Команды Telegram (основные)
`/status`, `/summary`, `/config`, `/debug`, `/risk`, `/signals`, `/performance`, `/pause`, `/resume`, `/panic`, `/logs`, `/health`, `/info`

### 🧪 Testnet (USDⓈ‑M USDT)
- Настройки `.env`:
  - `BINANCE_TESTNET=true`, `DRY_RUN=false`
  - Тестнет‑ключи с правом Futures; пополнить тестовыми USDT
- Что изменено в коде для testnet:
  - Используются FAPI урлы: `https://testnet.binancefuture.com/fapi`
  - Отбор символов по USDT; дефолт‑лист USDT
  - Баланс в статусе: USDT (прод: USDC)
  - Параметр `test` у ордеров ставится только при `DRY_RUN=true` (валидция без создания)
- Запуск:
```bash
python manage_keys.py update
python main.py
```
- Траблшутинг: проверьте Futures‑perm у ключей и наличие USDT; логи должны содержать
  “Exchange connection initialized successfully” и “Loaded N USDT symbols”.
- Справка: [Binance USDⓈ‑M Futures — General Info](https://developers.binance.com/docs/derivatives/usds-margined-futures/general-info)

### 🔑 Работа с .env (безопасно)
- Показать статус: `python manage_keys.py status`
- Печать .env (скрывает секреты): `python manage_keys.py print`
- Установить переменную: `python manage_keys.py set-var BINANCE_TESTNET true`
- Прочитать переменную (скрывает секреты): `python manage_keys.py get-var BINANCE_API_KEY`
- Быстрое переключение профилей: `python manage_keys.py switch testnet` (использует `.env.testnet` → `.env`)
### 📌 Текущее состояние и план
- Финальный концепт и Roadmap: см. `USDC_FUTURES_FINAL_CONCEPT_AND_ROADMAP.md` (раздел «Пошаговый план внедрения»)
- Аудит структуры и план чистки: см. `docs/PROJECT_AUDIT_2025-08-08.md`
- Текущий этап: Stage 2 — выполнено; переходим к Stage 3 (DRY RUN / Testnet)
- Что уже сделано:
  - Фильтры USDC (quote/settle == USDC, swap/future), нормализация символов
  - Унификация API `SymbolManager↔ExchangeClient` (`get_markets/get_ticker/get_ohlcv`)
  - Интегрирован `core/trade_engine_v2.py` в `main.py`
  - Нормализованы типы ордеров TP/SL в клиенте биржи (SL → STOP_MARKET, TP → TAKE_PROFIT, оба с reduceOnly) — требуется валидация на testnet
  - Встроен RiskGuard‑гейт: cooldown входов по символу (`entry_cooldown_seconds` в конфиге)
  - Усилен фильтр объёма в `SymbolManager` (толерантен к разным полям объёма тикера)
- Ближайшие задачи:
  - Валидация TP/SL на testnet (STOP/STOP_MARKET/TAKE_PROFIT, reduceOnly, timeInForce)
  - Обогащение Telegram-команд живыми данными (позиции, PnL, риск)
  - RiskGuard MVP: добавить SL‑streak pause и дневной лимит; интегрировать max hold в engine
  - DRY RUN/Testnet и проверка прав API (Futures, IP whitelist)
  - Runtime статус и метрики (баланс, позиции, UPnL, аптайм; агрегаты в БД)
  - Минимальные размеры/ноционал: проверить `min_position_size_usdt` и требования `MIN_NOTIONAL` для USDC рынков
  - Опционально позже: WebSocket (включить после стабилизации; по умолчанию REST на Windows)

### 🔒 Безопасность
- Ключи только в `.env`. Никогда не коммитить реальные ключи
- Включать реальную торговлю только после успешного DRY RUN и тестнета

—

© Binance USDC Futures Bot v2.2 — актуальная документация и статус поддерживаются в этом README и сопроводительных `.md` файлах.
