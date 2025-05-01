BinanceBot — Полный Master Plan оптимизации и развития (Апрель 2025)
Реальная структура проекта (актуальная)

BINANCEBOT/
├── core/
│ ├── aggressiveness_controller.py
│ ├── balance_watcher.py
│ ├── binance_api.py
│ ├── engine_controller.py
│ ├── entry_logger.py
│ ├── exchange_init.py
│ ├── risk_utils.py
│ ├── score_evaluator.py
│ ├── score_logger.py
│ ├── strategy.py
│ ├── symbol_processor.py
│ ├── tp_utils.py
│ ├── trade_engine.py
│ ├── volatility_controller.py
├── data/
│ ├── bot_state.json
│ ├── dry_entries.csv
│ ├── dynamic_symbols.json
│ ├── entry_log.csv
│ ├── last_ip.txt
│ ├── last_update.txt
│ ├── score_history.csv
│ ├── tp_performance.csv
├── docs/
│ ├── BinanceBot — Project Plan (v1.6.3, April 2025).md
│ ├── BinanceBot Developer Guide — v1.6.3.md
│ ├── BinanceBot TODO — v1.6.3 Roadmap (April 2025).md
│ ├── plan_optimization_updated.md
│ ├── PracticalGuideStrategyAndCode.md
│ ├── router_reboot_dry_run.md
│ ├── router_reboot_real_run.md
│ ├── Syntax & Markdown Guide.md
│ ├── to_fix_real_run_updated.md
├── telegram/
│ ├── telegram_commands.py
│ ├── telegram_handler.py
│ ├── telegram_ip_commands.py
│ ├── telegram_utils.py
├── .env
├── .env.example
├── config.py
├── debug_log.txt
├── htf_optimizer.py
├── ip_monitor.py
├── main.py
├── pair_selector.py
├── push_log.txt
├── push_to_github.bat
├── pyproject.toml
├── README.md
├── requirements.txt
├── score_heatmap.py
├── start_bot.bat
├── stats.py
├── telegram_log.txt
├── test_api.py
├── tp_logger.py
├── tp_optimizer.py
├── tp_optimizer_ml.py
├── update_from_github.bat
├── utils_core.py
├── utils_logging.py

📋 Структурный аудит проекта
✅ Основные модули:

main.py, core/_, telegram/_, config.py

✅ Основная логика запуска:

main.py инициализирует engine_controller, pair_selector, telegram_handler.

✅ Риски:

Частые вызовы API → риск блокировок,

Ошибки синхронизации в потоках,

Дублирование логов,

Отсутствие безопасного переключения Testnet.

🚨 Основные проблемы и их исправления

Проблема Решение
Дублирование записей сделок Проверка уникальности ID сделки в tp_logger.py.
Превышение лимита позиций Проверка MAX_POSITIONS в engine_controller.py перед каждым входом.
Ошибки NoneType при расчетах Ввод строгой проверки всех данных перед использованием (Decimal, float).
Отсутствие учёта комиссий Включить расчёт комиссий в tp_logger.py, stats.py.
Фиксированные TP/SL Переход на динамический расчет через ATR в trade_engine.py.
Нет режима Testnet Добавить USE_TESTNET в config.py и переключение в exchange_init.py.
🚀 Стратегия оптимизации
Краткосрочные цели (1–2 недели)
Внедрить поддержку Testnet.

Исправить лимиты позиций и ошибки маржи.

Динамическая настройка TP/SL через ATR.

Исправить команды /stop, /panic в Telegram.

Среднесрочные цели (1–2 месяца)
Внедрение расширенной аналитики (hold time, slippage, dynamic score).

Добавление фильтров пар (volatility + liquidity).

Улучшение адаптивного риска в зависимости от баланса.

Долгосрочные цели (3–6 месяцев)
Переход на базу данных для хранения сделок (SQLite, PostgreSQL).

Внедрение ML-кластеризации для выбора лучших пар.

Поддержка нескольких бирж (Bybit, OKX).

🏃 Форсированный чек-лист на 14 дней

День Задачи
1-2 Внедрить флаг USE_TESTNET, переключение API.
3 Исправить лимит открытых позиций в engine_controller.py.
4-5 Динамическая адаптация TP/SL через ATR.
6 Учёт комиссий в логах прибыли.
7 Исправление корректной остановки через /stop, /panic.
8 Проверка всех потоков и исправление ошибок блокировок.
9 Оптимизация кода для fetch_balance и fetch_positions (safe retries).
10 Улучшение обработки ошибок API.
11-12 Тестирование DryRun на реальных данных.
13-14 Финальное тестирование в режиме Testnet.
✨ Особые акценты
Безопасность API: отдельные ключи для LIVE и TESTNET.

Многопоточность: обязательно использование Lock для всех разделяемых ресурсов.

Динамическое обновление списка пар каждые 60 минут.

Ведение расширенных логов ошибок.

Вот готовые куски кода, которые нужно вставить в твой проект для реализации нашего Master Plan.

1. ➔ Добавление поддержки Testnet в exchange_init.py
   exchange_init.py:

import ccxt
from config import API_KEY, API_SECRET, USE_TESTNET

exchange_class = ccxt.binanceusdm_testnet if USE_TESTNET else ccxt.binanceusdm
exchange = exchange_class({
'apiKey': API_KEY,
'secret': API_SECRET,
'enableRateLimit': True,
'options': {
'defaultType': 'future',
'adjustForTimeDifference': True,
}
})
✅ Обязательно добавь переменную USE_TESTNET в config.py!

2. ➔ Вставка в config.py
   config.py:

# API

API_KEY = 'your_api_key'
API_SECRET = 'your_api_secret'

# Testnet переключатель

USE_TESTNET = False # True для тестовой торговли на Binance Testnet

# Риск-менеджмент

RISK_PERCENT = 0.01 # 1% риска на сделку
MAX_POSITIONS = 3
MIN_NOTIONAL_OPEN = 20 # Минимальная сумма сделки 3. ➔ Обновление TP/SL через ATR в trade_engine.py
trade_engine.py (функция расчёта TP/SL):

def calculate*tp_sl(entry_price, atr_value):
tp1 = entry_price + (atr_value * 1.0)
tp2 = entry*price + (atr_value * 2.0)
sl = entry_price - (atr_value \* 1.5)
return tp1, tp2, sl
(для short-позиций сделай зеркально)

4. ➔ Учёт комиссии в tp_logger.py
   tp_logger.py (при записи результата сделки):

# Учитываем комиссии

commission = 0.0002 if order*type == 'maker' else 0.0005
real_profit = (exit_price - entry_price) * quantity - (entry*price * quantity _ commission) - (exit_price _ quantity \* commission) 5. ➔ Безопасная остановка через /stop в telegram_commands.py
telegram_commands.py:

@bot.message_handler(commands=['stop'])
def stop_bot(message):
if not stopping.is_set():
stopping.set()
send_telegram_message("Stopping bot gracefully... Waiting for open positions to close.")
else:
send_telegram_message("Stop already initiated.")
✅ Поставить флаг stopping, дождаться закрытия всех позиций и только потом завершать работу бота.

6. ➔ Защита потоков с помощью Lock (если ещё не везде добавлено)
   Пример для любой общей переменной:

from threading import Lock

balance_lock = Lock()

with balance_lock: # Работа с балансом
available_balance = fetch_balance()

# 📢 Расширенная версия Master Plan (v2.0)

Master Plan BinanceBot v2.0
Архитектура проекта
Проект BinanceBot имеет модульную структуру. Точка входа — main.py, который запускает потоки для торгового цикла (engine_controller.py), ротации пар (pair_selector.py), Telegram-уведомлений (telegram_handler.py) и отчётов (stats.py).
Основные модули:

trade_engine.py — вход/выход из сделок, TP/SL, безубыток, трейлинг-стоп,

symbol_processor.py — проверка маржи/нотионала,

strategy.py — генерация сигналов на основе MACD, RSI, ATR, ADX, Bollinger Bands,

tp_logger.py — логирование сделок,

config.py — параметры стратегии (RISK_PERCENT, MAX_POSITIONS, MIN_NOTIONAL_OPEN и др.),

utils_core.py — кэширование вызовов API и управление состоянием,

telegram_commands.py — обработка /stop, /panic, /status и т.д.

Данные (логи, текущие списки символов) хранятся в каталоге data/.
Модули взаимодействуют через чётко определённые зависимости.
Уязвимые места: частые вызовы fetch_balance()/fetch_positions() без кэширования, неполная защита потоков (Lock), дублирование записей в логах сделок, избыточный DEBUG-лог, конфликт флагов /stop, /panic, stopping, shutdown.

Стратегия оптимизации
Краткосрочный этап (2–4 недели):

Добавить поддержку Testnet (USE_TESTNET в config.py, exchange_init.py).

Исправить критические баги: дубли логов, лимиты позиций, ошибки маржи/NoneType, Telegram-команды.

Настроить динамический TP/SL через ATR с учётом комиссий.

Среднесрочный этап (~1–2 месяца):

Расширить аналитику (stats.py — винрейт, время удержания, проскальзывание).

Фильтрация в pair_selector.py (ATR/ADX/VWAP, корреляция пар).

Масштабирование MAX_POSITIONS и RISK_PERCENT при росте депозита.

Долгосрочный этап (~3–6 месяцев):

(Опционально) Миграция на SQL-базу (SQLite/PostgreSQL) для истории сделок.

Внедрение ML (кластеризация символов, регрессия TP/SL).

Добавление поддержки других бирж (Bybit, OKX).

Тактический план по дням
День 1:

В config.py добавить флаг USE_TESTNET.

В exchange_init.py реализовать переключение на Testnet (ccxt.binanceusdm_testnet).

День 2:

Проверить загрузку правильных API-ключей Testnet и работу переключения.

День 3:

В engine_controller.py исправить проверку MAX_POSITIONS.

День 4:

В trade_engine.py и tp_utils.py внедрить расчет TP/SL через ATR:

SL = 1.5 _ ATR, TP1 = 1 _ ATR, TP2 = 2 \* ATR.

Учитывать комиссии (maker 0.02%, taker 0.05%).

День 5:

В tp_logger.py, stats.py добавить учёт комиссий в PnL.

День 6:

В telegram_commands.py исправить /stop, /panic.

В main.py реализовать graceful shutdown.

День 7:

Устранить дублирование записей в tp_performance.csv.

Добавить safe_call_retry для Binance API.

День 8:

Оптимизировать многопоточность (Lock на счётчики и логи).

День 9:

Провести тестирование DRY_RUN 2–3 часа.

День 10:

Развернуть и проверить Testnet торговлю.

День 11:

Настроить фильтрацию торговых пар (pair_selector.py).

День 12:

Добавить новые индикаторы в strategy.py (RSI, Stochastic).

День 13:

Экспортировать логи, сделки, ошибки.

День 14:

Проанализировать результаты тестирования.

(Дальнейшие задачи: ML, БД — после стабилизации базовой логики.)

Улучшение индикаторов и сигналов
Базовые: EMA, MACD, RSI, ATR, ADX, BB Width.

Рекомендации:

Добавить VWAP для оценки активности рынка.

Подтверждать сигналы увеличением объёма.

Проверять тренд на старшем ТФ (4ч через htf_optimizer).

Отлавливать дивергенции RSI/MACD.

Позже внедрить ML-регрессию для TP/SL и кластеризацию пар.

Защита капитала
SL: 1–1.5% от депозита или 1.5\*ATR.

TP1/TP2: 70%/30% с минимальным профитом.

Break-Even: после достижения TP1.

Trailing Stop: адаптивный по ATR.

Soft Exit: частичное закрытие при ослаблении тренда.

Остановка торговли: при просадке >5% депозита.

Фильтрация: обязательное соотношение риск/прибыль минимум 1:1.5.

Дополнительные рекомендации
Реализовать Safe API Retries и кэширование вызовов.

Использовать Lock для глобальных переменных и логов.

Настроить контроллер агрессивности (aggressiveness_controller.py).

Расширить аналитику в stats.py.

SQL-базу внедрять опционально в будущем.

Настроить мониторинг IP и критических ошибок.

## Кодовые блоки для вставки

# config.py: флаг Testnet

USE_TESTNET = False # True для подключения к Binance Testnet

# exchange_init.py: переключение на Testnet

import ccxt
from config import API_KEY, API_SECRET, USE_TESTNET

exchange_class = ccxt.binanceusdm_testnet if USE_TESTNET else ccxt.binanceusdm
exchange = exchange_class({
'apiKey': API_KEY,
'secret': API_SECRET,
'enableRateLimit': True,
'options': {
'defaultType': 'future',
'adjustForTimeDifference': True,
}
})
if USE_TESTNET:
exchange.set_sandbox_mode(True)

# tp_logger.py: логирование сделок с проверкой на дубликат

from threading import Lock

logged_trades = set()
logged_trades_lock = Lock()

def log_trade_result(...):
...
with logged_trades_lock:
if trade_id in logged_trades:
return
logged_trades.add(trade_id)
...

# utils_core.py: Safe Retry для API вызовов

import time
from functools import wraps
from ccxt.base.errors import NetworkError, RequestTimeout

def safe_retry(func):
@wraps(func)
def wrapper(*args, \*\*kwargs):
retries = 3
for attempt in range(retries):
try:
return func(*args, \*\*kwargs)
except (NetworkError, RequestTimeout):
time.sleep(1)
continue
raise
return wrapper

# Пример использования Lock в многопоточности

from threading import Lock

data_lock = Lock()

def update_shared_resource():
with data_lock: # Критическая секция
shared_counter += 1

## 📋 Что нужно добавить в Master Plan v2.1 по предложению Грока

1. Добавить в Стратегию и Долгосрочные цели:
   ✏️ Хеджирование:

"Долгосрочная цель — разработать механизм хеджирования: открытие противоположной позиции на коррелирующем активе при просадке >5% на основном активе."

✏️ Фильтрация дивергенций RSI/MACD:

"Добавить выявление и фильтрацию дивергенций RSI/MACD в strategy.py для повышения качества входов. Планируемый день внедрения — день 12."

✏️ Уточнение ML-целей:

"Использовать K-Means кластеризацию для отбора перспективных пар в pair_selector.py и линейную регрессию для прогнозирования оптимальных TP/SL."

✏️ Аналитика проскальзывания:

"Расширить stats.py для анализа проскальзывания ордеров (разница между ожидаемой и фактической ценой исполнения). Планируемый день внедрения — день 14."

2. Уточнить мелкие моменты:
   ✏️ Риск-менеджмент:

Убрать фиксированное упоминание риска 5% в PracticalGuideStrategyAndCode.md → заменить на адаптивный риск 1–5%, как указано в Master_Plan.md v2.0.

✏️ Проверить /restart:

Проверить, есть ли команда /restart в telegram_commands.py. Если нет — либо добавить её, либо убрать упоминание из Mini_Hints.md.

✏️ Буфер маржи 90%:

Добавить в symbol_processor.py расчёт безопасности на уровне маржи: использовать только 90% доступной маржи для открытия новых позиций (например, через available_margin \* 0.9).

3. Код для вставки (от Грока — про хеджирование):

# trade_engine.py

def hedge_position(symbol, qty, side):
correlated_symbol = get_correlated_symbol(symbol) # Реализовать метод поиска коррелирующей пары
if correlated_symbol:
opposite_side = "sell" if side == "buy" else "buy"
safe_call_retry(exchange.create_market_order, correlated_symbol, opposite_side, qty \* 0.5)
send_telegram_message(f"Hedged {symbol} with {correlated_symbol}", force=True)
(Добавить в долгосрочные задачи, не срочно.)

📋 Итоговые изменения в Master_Plan v2.1:

Блок Что добавить или изменить
Долгосрочные цели Хеджирование, ML уточнение, аналитика проскальзывания
Стратегия по дням День 12: дивергенции, День 14: анализ проскальзывания
Мелкие корректировки Риск 1–5%, /restart в Mini_Hints.md, буфер маржи 90%
Кодовые блоки Пример функции hedge_position
