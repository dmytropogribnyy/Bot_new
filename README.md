## Binance USDC Futures Bot (v2.3) - PRODUCTION READY ✅

Полностью функциональный бот для USDT‑маржинальных фьючерсов Binance. Протестирован на testnet, готов к продакшену. Основные цели: стабильность, адаптивность, минимизация рисков и работа 24/7 с контролем через Telegram.

-   Документ с финальным концептом и дорожной картой: [`USDC_FUTURES_FINAL_CONCEPT_AND_ROADMAP.md`](USDC_FUTURES_FINAL_CONCEPT_AND_ROADMAP.md)
-   **Статус проекта:** ✅ **ГОТОВ К ПРОДАКШЕНУ** (09.08.2025)
    -   Тестирование на Binance Futures Testnet: **УСПЕШНО ЗАВЕРШЕНО**
    -   Все системы проверены: **РАБОТАЮТ**
    -   Emergency shutdown (Ctrl+C): **РЕАЛИЗОВАН**
    -   Автоматическое закрытие позиций: **РАБОТАЕТ**
    -   Очистка висячих ордеров: **РЕАЛИЗОВАНА**

### 📂 Ключевая структура

-   `main.py` — точка входа (async), инициализация компонентов, основной цикл
-   `core/`
    -   `config.py` — унифицированная конфигурация (Pydantic, .env, runtime JSON)
    -   `exchange_client.py` — ccxt (async), кэш, retry, health-check
    -   `order_manager.py` — открытие позиций, TP/SL, мониторинг, emergency
    -   `symbol_manager.py` — выбор/ротация символов USDC (нормализация через `core/symbol_utils.py`)
    -   `strategy_manager.py` — координация стратегий
    -   `unified_logger.py` — логирование: консоль, файл, SQLite, Telegram
    -   `trade_engine_v2.py` — лёгкий движок сканирования/оценки/входа (интегрирован в `main.py`)
-   `strategies/`
    -   `base_strategy.py`, `scalping_v1.py`
-   `telegram/telegram_bot.py` — уведомления и команды управления
-   `tests/*.py` — базовые и интеграционные тесты
-   `data/` — конфиги и БД (`data/trading_bot.db`, `data/runtime_config.json`)

### ⚙️ Возможности

-   Асинхронная архитектура (asyncio), модульность
-   Управление риском: лимит позиций, дневной лимит убытков, авто‑паузы по SL‑серии
-   TP/SL: ступенчатый TP, обязательный SL, уборка зависших ордеров
-   Символы USDC: фильтры по объёму/волатильности, ротация
-   Telegram: статус, резюме, пауза/резюм, emergency стоп
-   Логи и аналитика: файл, SQLite, агрегаты и runtime‑статус

### 🚀 Быстрый старт

#### 1️⃣ Зависимости

```bash
pip install -r requirements.txt
```

📋 Блок для README.md:
markdown## 🔐 Управление конфигурацией (.env)

### 📁 Структура конфигурации

Бот использует каскадную загрузку настроек:
.env → os.environ → TradingConfig → runtime

### 🛠️ Утилиты для работы с .env

#### **manage_keys.py** - Полный менеджер конфигурации

````bash
# Показать статус конфигурации
python manage_keys.py status

# Установить переменную
python manage_keys.py set-var BINANCE_TESTNET true
python manage_keys.py set-var DRY_RUN false

# Показать все переменные (с маскировкой секретов)
python manage_keys.py print-env

# Создать шаблон .env
python manage_keys.py template

# Валидировать конфигурацию
python manage_keys.py validate

# Переключить профиль (.env.testnet → .env)
python manage_keys.py switch testnet
quick_keys.py - Быстрая настройка
bash# Интерактивная установка API ключей
python quick_keys.py set-api

# Интерактивная настройка Telegram
python quick_keys.py set-telegram

# Проверка статуса
python quick_keys.py status
📝 Основные переменные окружения
ПеременнаяОписаниеПримерBINANCE_API_KEYAPI ключ Binanceyour_api_keyBINANCE_API_SECRETСекретный ключyour_secretBINANCE_TESTNETРежим тестнетаtrue/falseTELEGRAM_TOKENТокен бота от @BotFather123456:ABC...TELEGRAM_CHAT_IDID чата для уведомлений383821734DRY_RUNРежим симуляцииtrue/falseMAX_POSITIONSМакс. позиций3LEVERAGE_DEFAULTДефолтное плечо5STOP_LOSS_PERCENTСтоп-лосс (%)2.0TAKE_PROFIT_PERCENTТейк-профит (%)1.5
🚀 Быстрый старт конфигурации
1. Создать .env из шаблона:
bashcp .env.example .env
# или
python manage_keys.py template
2. Настроить API ключи:
bash# Вариант 1: Интерактивно
python quick_keys.py set-api

# Вариант 2: Командная строка
python manage_keys.py set-var BINANCE_API_KEY your_key
python manage_keys.py set-var BINANCE_API_SECRET your_secret
3. Настроить режим работы:
bash# Для тестнета
python manage_keys.py set-var BINANCE_TESTNET true
python manage_keys.py set-var DRY_RUN false

# Для продакшена
python manage_keys.py set-var BINANCE_TESTNET false
python manage_keys.py set-var DRY_RUN false
4. Проверить конфигурацию:
bashpython manage_keys.py validate
python manage_keys.py status
💻 Работа с конфигурацией в коде
python# Загрузить конфигурацию из .env
from core.config import TradingConfig
config = TradingConfig.from_env()

# Проверить режим работы
if config.testnet:
    print("Работаем на тестнете")
if config.dry_run:
    print("Режим симуляции")

# Программное изменение .env
from simple_env_manager import SimpleEnvManager
manager = SimpleEnvManager()
env_vars = manager.load_env_file()
env_vars["MAX_POSITIONS"] = "5"
manager.save_env_file(env_vars)
🔍 Диагностика
bash# Проверить синхронизацию с .env.example
python tests/test_env_sync.py

# Проверить загрузку конфигурации
python -c "from core.config import TradingConfig; c = TradingConfig.from_env(); print(f'API: {bool(c.api_key)}, Testnet: {c.testnet}')"

# Посмотреть конкретную переменную
python manage_keys.py get-var BINANCE_TESTNET
⚠️ Безопасность

.env файл НЕ должен попадать в git (добавлен в .gitignore)
Используйте .env.example как шаблон без секретных данных
Все утилиты автоматически маскируют секретные ключи при выводе
Создаётся автоматический backup при изменении .env

📂 Файловая структура
BinanceBot/
├── .env                    # Основная конфигурация (не в git)
├── .env.example           # Шаблон с примерами
├── .env.backup            # Автоматический бэкап
├── manage_keys.py         # Полный менеджер .env
├── quick_keys.py          # Быстрые команды
├── simple_env_manager.py  # Менеджер без зависимостей
└── core/
    ├── config.py          # TradingConfig класс
    ├── env_editor.py      # Редактор с python-dotenv
    └── env_manager.py     # Основной EnvManager
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
````

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

## 🧹 Repository Maintenance

### Stage A: Smart Repo Hygiene

Clean and organize repository structure:

```bash
# Preview changes (recommended first step)
./tools/hygiene.sh --dry-run

# Apply changes
./tools/hygiene.sh --force
```

This script will:

-   Archive documentation and media files to `references_archive/YYYY-MM/`
-   Remove unused binaries and temporary files
-   Prepare `core/legacy/` folder for future refactoring
-   Clean Python caches (pycache, .mypy_cache, etc.)
-   Update `.gitignore` with necessary entries

The script checks if files are referenced in the codebase before moving/deleting them.

## Testing Commands

After implementation, run these commands:

```bash
# 1. Make script executable
chmod +x tools/hygiene.sh

# 2. Preview changes
./tools/hygiene.sh --dry-run

# 3. Review output, then apply if looks good
./tools/hygiene.sh --force

# 4. Check git status
git status

# 5. Stage and commit
git add -A
git commit -m "chore(stage-a): implement smart repo hygiene

- Add tools/hygiene.sh with --dry-run and --force modes
- Archive docs/media to references_archive/YYYY-MM/
- Clean unused binaries and caches
- Prepare core/legacy/ for future refactoring
- Update .gitignore with repository structure"
```

Acceptance Criteria

✅ Script runs in dry-run mode without errors
✅ Script creates `references_archive/YYYY-MM/` and `core/legacy/`
✅ Documents/media are archived, not deleted
✅ Unused binaries are removed
✅ Referenced files are kept in place
✅ `.gitignore` is updated
✅ No import errors after cleanup
✅ Git history preserved where possible

IMPORTANT: Do not move any Python modules from `core/` to `core/legacy/` in this stage. That will be done in a future stage after proper dependency analysis.

### 🛡️ Безопасность и контроль

#### ⚠️ Emergency Shutdown (Ctrl+C)

-   **Автоматическое закрытие всех позиций** при остановке бота
-   **Отмена всех висячих ордеров** (TP/SL)
-   **Telegram уведомления** о критических ситуациях
-   **Принудительный выход** при сетевых ошибках

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

-   Источники: `.env` → `data/runtime_config.json` → значения по умолчанию (`core/config.py`)
-   Ключевые флаги: `BINANCE_TESTNET`, `DRY_RUN`, `LOG_LEVEL`, `max_positions`, `stop_loss_percent`, `take_profit_percent`
-   Пары: USDC‑фьючерсы, авто‑отбор через `SymbolManager`

### 📱 Команды Telegram (основные)

`/status`, `/summary`, `/config`, `/debug`, `/risk`, `/signals`, `/performance`, `/pause`, `/resume`, `/panic`, `/logs`, `/health`, `/info`

### 🧪 Testnet (USDⓈ‑M USDT)

-   Настройки `.env`:
    -   `BINANCE_TESTNET=true`, `DRY_RUN=false`
    -   Тестнет‑ключи с правом Futures; пополнить тестовыми USDT
-   Что изменено в коде для testnet:
    -   Используются FAPI урлы: `https://testnet.binancefuture.com/fapi`
    -   Отбор символов по USDT; дефолт‑лист USDT
    -   Баланс в статусе: USDT (прод: USDC)
    -   Параметр `test` у ордеров ставится только при `DRY_RUN=true` (валидция без создания)
-   Запуск:

```bash
python manage_keys.py update
python main.py
```

-   Траблшутинг: проверьте Futures‑perm у ключей и наличие USDT; логи должны содержать
    “Exchange connection initialized successfully” и “Loaded N USDT symbols”.
-   Справка: [Binance USDⓈ‑M Futures — General Info](https://developers.binance.com/docs/derivatives/usds-margined-futures/general-info)

### 🔑 Работа с .env (безопасно)

-   Показать статус: `python manage_keys.py status`
-   Печать .env (скрывает секреты): `python manage_keys.py print`
-   Установить переменную: `python manage_keys.py set-var BINANCE_TESTNET true`
-   Прочитать переменную (скрывает секреты): `python manage_keys.py get-var BINANCE_API_KEY`
-   Быстрое переключение профилей: `python manage_keys.py switch testnet` (использует `.env.testnet` → `.env`)

### 📌 Текущее состояние и план

-   Финальный концепт и Roadmap: см. `USDC_FUTURES_FINAL_CONCEPT_AND_ROADMAP.md` (раздел «Пошаговый план внедрения»)
-   Аудит структуры и план чистки: см. `docs/PROJECT_AUDIT_2025-08-08.md`
-   Текущий этап: Stage 2 — выполнено; переходим к Stage 3 (DRY RUN / Testnet)
-   Что уже сделано:
    -   Фильтры USDC (quote/settle == USDC, swap/future), нормализация символов
    -   Унификация API `SymbolManager↔ExchangeClient` (`get_markets/get_ticker/get_ohlcv`)
    -   Интегрирован `core/trade_engine_v2.py` в `main.py`
    -   Нормализованы типы ордеров TP/SL в клиенте биржи (SL → STOP_MARKET, TP → TAKE_PROFIT, оба с reduceOnly) — требуется валидация на testnet
    -   Встроен RiskGuard‑гейт: cooldown входов по символу (`entry_cooldown_seconds` в конфиге)
    -   Усилен фильтр объёма в `SymbolManager` (толерантен к разным полям объёма тикера)
-   Ближайшие задачи:
    -   Валидация TP/SL на testnet (STOP/STOP_MARKET/TAKE_PROFIT, reduceOnly, timeInForce)
    -   Обогащение Telegram-команд живыми данными (позиции, PnL, риск)
    -   RiskGuard MVP: добавить SL‑streak pause и дневной лимит; интегрировать max hold в engine
    -   DRY RUN/Testnet и проверка прав API (Futures, IP whitelist)
    -   Runtime статус и метрики (баланс, позиции, UPnL, аптайм; агрегаты в БД)
    -   Минимальные размеры/ноционал: проверить `min_position_size_usdt` и требования `MIN_NOTIONAL` для USDC рынков
    -   Опционально позже: WebSocket (включить после стабилизации; по умолчанию REST на Windows)

### 🔒 Безопасность

-   Ключи только в `.env`. Никогда не коммитить реальные ключи
-   Включать реальную торговлю только после успешного DRY RUN и тестнета

—

© Binance USDC Futures Bot v2.2 — актуальная документация и статус поддерживаются в этом README и сопроводительных `.md` файлах.
