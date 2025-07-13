# 📁 PROJECT_STRUCTURE.md — BinanceBot (июль 2025)

Полная структура проекта с описанием назначения каждого файла, ключевых функций и логики.

---

## 🔧 Основные файлы и контроллеры

### `main.py`

> Главная точка запуска бота: цикл сканирования, входа, мониторинга.

-   Загружает runtime config и Telegram-команды
-   Вызывает `run_trading_cycle()`
-   Поддерживает shutdown через state

### `engine_controller.py`

> Управляет циклом: выбор пар, проверка условий, попытка входа.

-   `run_trading_cycle()` — основной цикл торговли
-   Контролирует лимиты, пропуски, фильтры и входы

### `symbol_processor.py`

> Обрабатывает каждый символ:

-   Вызывает `should_enter_trade(...)`
-   При необходимости вызывает `enter_trade(...)`

### `trade_engine.py`

> Основная логика торговли:

-   `enter_trade()` — расчёт объема, вход, TP/SL
-   `monitor_active_position()` — TP/SL/step/exit
-   `record_trade_result()` — логирование результатов

### `strategy.py`

> Реализация торговой логики:

-   `should_enter_trade()` — принимает решение о входе
-   `passes_1plus1()`, score-функции, антифлуд, TP-фильтры

---

## ⚙️ Конфигурация и состояние

### `runtime_config.json`

> Конфигурация бота во время исполнения.

-   max_concurrent_positions, step_tp_levels, SL_PERCENT и пр.

### `utils_core.py`

> Утилиты и кеши:

-   Баланс/позиции, state, config update
-   `safe_call_retry()`, `get_runtime_config()`

### `config_loader.py`

> Пути и переменные окружения

-   `CONFIG_FILE`, `EXPORT_PATH`, лог-файл, параметры dry run и пр.

### `constants.py`

> Пути к CSV/JSON файлам (tp_log, state, stats и др.)

### `.env`

> Ключи API и Telegram, переменные окружения.

---

## 📈 Управление позициями и рисками

### `risk_utils.py`

-   Расчёт позиции, qty, stop-loss и risk amount
-   `calculate_position_size()`, `calculate_order_quantity()`

### `risk_guard.py`

-   Проверка лимитов: capital utilization, max positions

### `position_manager.py`

-   Обновление позиций, удаление, проверка закрытий

### `leverage_config.py`

-   Установка кредитного плеча (авто или фикс)

### `order_utils.py`

-   Маркет/лимит ордера, FOK, reduceOnly, postOnly
-   Обработка `filled_qty == 0` и fallback логики

### `binance_api.py`

-   Binance-специфичные запросы: OHLCV, symbol info, precision

### `exchange_init.py`

-   Инициализация CCXT exchange (testnet/mainnet)

---

## 🧠 Логика выбора и приоритетов

### `pair_selector.py`

-   Отбор пар по объёму, ATR, fixed_pairs, исключения

### `priority_evaluator.py`

-   Оценка динамики счёта, адаптация TP/объёма по equity

### `scalping_mode.py`

-   Поддержка режима Scalp/HFT: активация параметров, фильтров

### `signal_utils.py`

-   MACD, RSI, волатильность, direction, свечные сигналы

### `open_interest_tracker.py`

-   Получение open interest по символу с Binance

---

## 🧪 Тесты, анализ и отладка

### `test_api.py`

-   Проверка, какие пары Binance поддерживают 3m/5m/15m OHLCV

### `debug_tools.py`

-   Дополнительные функции отладки: тест символов, вывод баланса и др.

### `continuous_scanner.py`

-   Альтернативный сканер с непрерывным сканированием и логом

---

## 📊 Логгеры и статистика

### `entry_logger.py`

-   Логирует попытки входа: success, reject, breakdown

### `tp_sl_logger.py`

-   Сохраняет TP1/TP2/SL и fallback в CSV + Telegram уведомления

### `tp_optimizer.py`

-   Анализирует TP статистику и адаптирует уровни TP1/TP2

### `tp_utils.py`

-   Расчёт TP уровней, SL, trailing, распределения qty

### `stats.py`

-   Расчёт дневной/часовой статистики (PnL, TP rate, SL rate)

### `runtime_stats.py`

-   Контроль активных сделок, макс. допустимых позиций, стопов

### `fail_stats_tracker.py`

-   Трекер провалов сигналов, попадания в SL и др.

### `failure_logger.py`

-   Логирование ошибок сигналов (direction, qty, объем и т.п.)

### `component_tracker.py`

-   Отслеживает влияние фильтров (MACD, volume и др.)

### `missed_tracker.py`

-   Логирует missed opportunities + причины отказа от входа

---

## 📬 Telegram и команды

### `telegram_utils.py`

-   Отправка сообщений, форматирование, логика force=True и markdown

### `telegram_handler.py`

-   Обработка Telegram-команд: `/start`, `/stop`, `/status` и т.п.

### `telegram_commands.py`

-   Реализация логики каждой команды (stopbot, getlog, force_enter)

### `registry.py`

-   Реестр всех Telegram-команд (для избежания циклических импортов)

---

## 🧠 Вспомогательное

### `ip_monitor.py`

-   Обнаружение смены IP-адреса, Telegram-уведомления

### `runtime_state.py`

-   Работа с флагами: shutdown, stopping, control state.json

### `notifier.py`

-   Отправка кастомных Telegram-уведомлений (при ошибках и пр.)

---

## ✅ Структура данных и логов (из constants.py)

-   `data/runtime_config.json` — ключевая конфигурация
-   `data/tp_performance.csv` — TP/SL статистика
-   `data/entry_log.csv` — лог попыток входа
-   `data/fail_stats.json` — аналитика провалов
-   `data/missed_opportunities.json` — missed входы
-   `data/bot_state.json` — флаги shutdown, stopping
-   `data/backups/` — бэкапы конфигов
-   `data/parameter_history.json` — история изменений config

---

## 🟢 Входные и выходные точки

-   `main.py` → `engine_controller.run_trading_cycle()` → `symbol_processor`
-   Вход: `should_enter_trade` → `enter_trade`
-   Мониторинг: `monitor_active_position`
-   Выход: `record_trade_result`, Telegram

---

## 🟡 Удалённые / неиспользуемые

-   Все загруженные файлы **актуальны**, мёртвых импортов **нет**
-   `_min_step_hit_required` в `monitor_active_position` — зарезервировано, можно удалить

---

## 🔚 Готово к запуску

Проект полностью структурирован и синхронизирован. Можно использовать для запуска и масштабирования.
