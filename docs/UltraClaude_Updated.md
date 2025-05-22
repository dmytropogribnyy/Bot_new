# UltraClaude Updated — Оптимизированный план развития BinanceBot

## Введение

Этот документ является полной заменой прежнего `ultra_claude.md`. Он разработан на основе объединённого анализа от GPT-4 и Claude Sonnet, содержит чёткую стратегию и архитектуру, направленную на решение главных проблем проекта BinanceBot: "торгового болота", перегрузки индикаторами и нестабильных сигналов.

## Структура проекта

BINANCEBOT/
├── .env, .env.example # Переменные окружения для API-ключей, режимов и конфигов
├── .gitignore, README.md # Git-игнор и основная инструкция
├── pyproject.toml, requirements.txt # Зависимости проекта
├── main.py # Точка входа, запуск всех процессов
├── config.py # Статичные конфигурации по умолчанию
├── restore_backup.py # Восстановление состояния после сбоя
├── clean_cache.py, safe_compile.py # Очистка кэша и безопасная пересборка
├── score_heatmap.py # Генерация визуальных score-карт по символам
├── stats.py # Статистика TP/SL/Winrate по сделкам
├── refactor_imports.py # Автоперенос импортов и структурировка
├── start_bot.bat, push_to_github.bat, update_from_github.bat # Скрипты запуска и синхронизации

├── core/ # Основная логика торговли
│ ├── aggressiveness_controller.py # Адаптация риска по TP2 winrate
│ ├── balance_watcher.py # Мониторинг баланса и расчёт роста
│ ├── binance_api.py # Обёртка над Binance USDC Futures API
│ ├── candle_analyzer.py # Анализ свечей по MTF (3m, 5m, 15m)
│ ├── dynamic_filters.py # Гибкая адаптация ATR и объёма
│ ├── engine_controller.py # Smart Switching, soft-exit логика
│ ├── entry_logger.py # CSV-лог всех входов в позиции
│ ├── exchange_init.py # Подключение к Binance и валидация API
│ ├── fail_stats_tracker.py # Учёт ошибок, decay и risk factor
│ ├── failure_logger.py # Подробные причины отказов
│ ├── filter_adaptation.py # Управление relax_factor'ом
│ ├── notifier.py # Telegram-уведомления
│ ├── order_utils.py # Построение ордеров (TP1, SL, post-only)
│ ├── position_manager.py # Учёт открытых позиций и лимитов
│ ├── risk_utils.py # Drawdown, расчет экспозиции, стопы
│ ├── score_evaluator.py # Сбор и агрегирование всех score-компонент
│ ├── score_logger.py # Логирование значений score по символу
│ ├── signal_feedback_loop.py # Адаптация параметров в runtime (score, momentum и др.)
│ ├── status_logger.py # Обновление /status и логов состояния
│ ├── strategy.py # Основная стратегия сигналов (RSI, EMA, MACD, VWAP, ATR)
│ ├── symbol_priority_manager.py # Приоритеты символов для маленьких балансов
│ ├── symbol_processor.py # Обработка и сопровождение одной пары
│ ├── tp_utils.py # Логика TP1/TP2, break-even, trailing stop
│ ├── trade_engine.py # Основной цикл входа и сопровождения сделок
│ └── volatility_controller.py # Вычисление рыночной волатильности

├── tools/
│ ├── continuous_scanner.py # Проверка неактивных символов каждые 15 минут

├── telegram/
│ ├── telegram_utils.py # Отправка сообщений и MarkdownV2
│ ├── telegram_handler.py # Обработка всех Telegram-запросов
│ ├── telegram_commands.py # /status, /summary, /hot, /failstats и др.
│ └── telegram_ip_commands.py # /ipstatus, /router_reboot и мониторинг IP

├── data/ # Хранилище всех временных и аналитических данных
│ ├── bot_state.json # Статус бота (стоп/работает/завершён)
│ ├── dry_entries.csv # Лог попыток входа в DRY_RUN режиме
│ ├── dynamic_symbols.json # Список активных пар на сессию
│ ├── entry_log.csv # Журнал реальных сделок
│ ├── failure_stats.json # Ошибки по символам (для расчёта риска)
│ ├── failure_decay_timestamps.json # Метки времени decay для ошибок
│ ├── filter_adaptation.json # Relax-параметры по символам
│ ├── initial_balance.json # Баланс при старте сессии
│ ├── initial_balance_timestamps.json # Метка времени инициализации баланса
│ ├── last_ip.txt # Последний IP-адрес
│ ├── last_update.txt # Время последнего обновления системы
│ ├── missed_opportunities.json # Неоткрытые сделки с потенциалом
│ ├── pair_performance.json # Winrate/TP2 успехи по символам
│ ├── parameter_history.json # История runtime параметров (TP, score и др.)
│ ├── runtime_config.json # Активная конфигурация стратегии
│ ├── score_history.csv # История score по парам
│ ├── signal_failures.json # Причины отказа в сигналах
│ ├── symbol_signal_activity.json # Активность сигналов за последние часы
│ ├── tp_performance.csv # История TP1/TP2/SL по сделкам
│ └── trade_statistics.json # Общая PnL-статистика и риски

├── docs/ # Документация и справочные материалы
│ ├── UltraClaude_Updated.md # 📌 Основной файл: описание стратегии и архитектуры
│ ├── Master_Plan.md # Roadmap + задачи по фазам
│ ├── File_Guide.md # Описание структуры проекта
│ ├── Syntax_and_Markdown_Guide.md # Markdown + синтаксис Telegram
│ ├── PracticalGuideStrategyAndCode.md# Обзор стратегии и архитектуры
│ ├── Mini_Hints.md, project_cheatsheet.txt
│ ├── router_reboot_dry_run.md # Поведение в DRY_RUN
│ ├── router_reboot_real_run.md # Поведение в реальных условиях
│ └── Archive/ # Старые версии документации

├── logs/
│ └── main.log # Главный лог работы бота

├── tp_logger.py # Логирование TP/SL, break-even и trailing stop
├── tp_optimizer.py # Базовая TP оптимизация по статистике
├── tp_optimizer_ml.py # ML-подход к адаптации TP1/TP2
├── htf_optimizer.py # Адаптация high timeframe фильтра
├── missed_tracker.py # Учёт missed opportunities
├── ip_monitor.py # Мониторинг IP и реакция на смену
├── symbol_activity_tracker.py # Отслеживание сигналов и активности символов
├── utils_core.py # Общие вспомогательные функции
└── utils_logging.py # Форматирование и уровни логов

## ✅ Overall Assessment — v1.6.5-opt-stable

BinanceBot — устойчивый, самонастраивающийся фьючерсный торговый бот, оптимизированный под малые депозиты и короткие сделки (scalping). Архитектура модульная, легко масштабируется, включает адаптивное управление риском, динамическую фильтрацию сигналов и продвинутую систему ротации символов.

🧩 Implementation Quality
Модульная структура (core/, tools/, telegram/, data/, docs/)

Полная изоляция режима DRY_RUN (без записи логов, чисто консоль)

Централизованная конфигурация (config_loader.py, runtime_config.json)

Безопасная остановка бота и автоматическое восстановление состояния

Поддержка Telegram-управления: команды, отчёты, статус, настройка

Runtime-адаптация: TP, SL, Score, Risk, Filters

Thread-safe потоки: блокировки, флаги, Telegram не дублируется

💡 Key Strengths
✅ Small Deposit Optimization
Новый балансный порог: < 300 USDC (раньше был < 150)

Tier-based логика (0–119, 120–249, 250–499…)

Подбор безопасных приоритетных пар

Ограничение одновременных позиций по балансу

Ротация только сильных и подходящих символов

Минимизируется нагрузка на малые депозиты

Micro-size + Smart Switching = стабильный скальпинг

✅ Advanced Risk Management
Graduated Risk System: позиция открывается с учётом risk_factor (0.1–1.0)

Decay-система: ошибка снижает вес пары, со временем восстанавливается

Полная замена binary-blocking

TP2 winrate влияет на max_concurrent_positions и риск

Drawdown-защита: остановка при просадке

Notional-check: нет сделок с чрезмерным объёмом

✅ Market Adaptability
MultiTimeframe: 1m, 3m, 5m, 15m, 1h

Адаптивные фильтры по ATR, объёму, волатильности

Open Interest используется как фактор усиления сигнала

Momentum + RSI + EMA + MACD + Volume = расчёт Score (0–5)

Score-теплокарта и компоненты сохраняются в логи

✅ Continuous Operation
ContinuousScanner обновляет список кандидатов каждые 15 мин

Auto-recovery логика, fallback по приоритетным парам (BTC/ETH/SOL…)

Telegram-команда /regenpriority перегенерирует приоритеты

/failstats и /signalblocks — оценка здоровья системы

/statuslog и /summary — регулярный мониторинг

Нет полной блокировки: даже "плохие" пары могут торговаться с 0.2x объёмом

✅ Reliable Reporting
Единый Telegram handler: без дублирования сообщений

Ежедневные, еженедельные, ежемесячные отчёты

MarkdownV2 экранирование + логика fallback (в случае ошибки API)

Все уведомления логируются с указанием риска, размера, TP/SL и причины выхода

✅ Current Status Summary
Параметр Значение
Версия v1.6.5-opt-stable
Режим REAL_RUN
Активных пар 7–15 (динамически)
Ошибки Отсутствуют
Ротация Активна (15 мин)
Обновление фильтров Адаптивное, по missed / vol
Статус бота Проверен и стабилен

📌 Основные цели стратегии
Исключить “болото” заблокированных пар (no binary blocking)

Обеспечить постоянную активность: 7–10 торгуемых символов

Выдавать только качественные подтверждённые сигналы

Избегать жёстких условий и перегрузки фильтрами

Мгновенно адаптироваться под волатильность, объём, прибыль

🔁 Symbol Priority System
Убраны блокировки block_until — теперь risk_factor ∈ [0.1 – 1.0]

Функция get_symbol_risk_factor() рассчитывает текущее доверие к символу

Прогрессивное понижение риска без исключения символа из торговли

Автоматический decay каждые 3 часа, без ручного вмешательства

/failstats и графики по TP2 winrate помогают оптимизировать приоритет

🔄 Symbol Rotation Engine
ContinuousScanner обновляет неактивные пары на основе:

Волатильности, объёма, missed opportunities

Сигнальной активности из symbol_signal_activity.json

PriorityFallback: при нехватке активных пар добавляются BTC/ETH/SOL

select_active_symbols() выбирает 5–20 лучших символов каждые 60 мин

🔬 Filter Optimization
Только: RSI(9), EMA(9/21), MACD, ATR, Volume

Исключено: BB, ADX, сложные свечные модели

Адаптация фильтров: ATR, объём, relax_boost

Введён adaptive_filters_enabled: true

Теплокарта score_heatmap.py визуализирует результаты

🧠 Scalping Mode
Включается при балансе < 300 или глобальном флаге

Входы на 3m/5m, подтверждение по 15m/1h

TP/SL авторасчитываются по ATR

Aggressiveness рассчитывается на основе TP2 winrate

Кол-во одновременных позиций зависит от баланса

📈 Telegram Integration
Команды: /start, /stop, /status, /summary, /failstats, /regenpriority, /signalconfig, /ipstatus, /hot, /missedlog, /signalblocks, /scorelog (WIP)

Все уведомления централизованы, без повторов

Все риски, TP/SL, входы и выходы — логируются

Сигналы со сниженным риск-фактором помечаются ⚠️

## Архитектура по фазам

# UltraClaude Updated — Финальный План BinanceBot (v1.6.2-final)

Этот документ заменяет все старые версии UltraClaude и представляет собой текущую, проверенную и завершённую структуру фаз, логики, компонентов и следующих шагов по проекту BinanceBot.

---

## ✅ Завершённые фазы

### ✅ Phase 1 — Symbol Management

-   `symbol_priority_manager.py` — логика приоритетов символов
-   `pair_selector.py` — выбор активных пар на основе объёма, волатильности
-   `fail_stats_tracker.py` — decay + прогрессивная блокировка символов
-   `continuous_scanner.py` — мониторинг неактивных символов (по расписанию)

### ✅ Phase 1.5 — Critical Optimizations

-   Post-only ордера, safe capital utilization
-   `adjust_score_relax_boost()` — автокоррекция score threshold
-   `ip_monitor`, `router_reboot`, `/cancel_stop`, `/ipstatus` и др.

### ✅ Phase 2 — Signal Optimization

-   `fetch_data_optimized()` — упрощённый и быстрый фреймворк индикаторов
-   Удалены: Bollinger Bands, ADX, BB Width, rel_volume, momentum
-   Стратегия работает на: RSI(9), EMA(9/21), MACD, VWAP, ATR
-   `calculate_score()` — нормализованная шкала 0–5, log в `score_components.csv`
-   `determine_strategy_mode()` + `dynamic_scalping_mode()` реализованы
-   `passes_filters_optimized()` используется при скальпинге
-   Всё централизовано через `should_enter_trade()`

### ✅ Phase 2.5 — Adaptive Runtime & Feedback

-   `/signalconfig` — Telegram-команда для просмотра актуальной конфигурации
-   `update_runtime_config()` с Markdown-уведомлением в Telegram + `parameter_history.json`
-   `adjust_from_missed_opportunities()` — динамическое смягчение условий входа по missed_log
-   `record_trade_result()` теперь включает `exit_reason`: TP / SL / FLAT / soft_exit
-   Auto-Profit: `check_auto_profit()` учитывает `tp1_hit`, duration < 60m, pnl >= threshold

---

## 🔜 Предстоящие фазы (Phase 2.6 → 3.0)

### 🟡 Phase 2.6 — Visualization & Analytics

-   `score_heatmap.py` — визуализация эффективности сигналов (7 дней, symbol/time/grid)
-   Расширенный TP/SL Pattern Analyzer — частота TP2, тайминги, early exit кластеризация
-   Расширение логики `missed_opportunities` и активности символов
-   Объединение `score_components.csv` + `tp_performance.csv` + `missed_log.json`
-   Telegram: новые команды — `/heatmap`, `/scorestats`, `/topmissed`

### 🔜 Phase 3.0 — Advanced Strategy Enhancements

-   Re-entry logic (многократный вход после сигнала)
-   Smart scaling: адаптация объёма входа по агрессивности и статистике
-   Layered Signals: сигналы с разных слоёв (HTF, MTF, price action)
-   Enhanced feedback loop: обучение на TP/SL и missed паттернах
-   Поддержка Open Interest (через WebSocket)

---

## 📦 Архитектура (актуальное состояние)

| Компонент              | Статус                                                              |
| ---------------------- | ------------------------------------------------------------------- |
| `strategy.py`          | ✅ очищен от legacy индикаторов                                     |
| `trade_engine.py`      | ✅ поддерживает flat exit, soft_exit, auto-profit                   |
| `telegram_commands.py` | ✅ команды `/statuslog`, `/signalconfig`, `/filters`, `/pairstoday` |
| `utils_core.py`        | ✅ логика config, missed, runtime, history                          |
| `score_evaluator.py`   | ✅ нормализация score, логика по компонентам                        |
| `status_logger.py`     | ✅ лог в консоль и Telegram каждые 10 мин                           |

---

## Current state

✅ BinanceBot Risk-Aware System Audit – Май 2025

🔴 Актуальный статус (Phase 2.6 — завершение):

Все ключевые компоненты новой адаптивной архитектуры успешно реализованы и протестированы. Система окончательно ушла от бинарных блокировок, введён механизм graduated risk, адаптивные фильтры, защита от массовых провалов по парам, а также адаптирован ротационный механизм под скальпинг-режим.

✅ Завершённые ключевые фичи:

🧠 Graduated Risk System:

Заменён механизм block_symbol() → get_symbol_risk_factor() с risk_factor от 0.1 до 1.0

Учёт total_failures из fail_stats.json

Все торговые действия теперь масштабируются по risk_factor

Полное удаление blocked_symbols из runtime_config.json

is_symbol_blocked() всегда возвращает False и больше не влияет на стратегию

Telegram-команда /signalblocks показывает уровень риска по парам, а не блокировки

⚖️ Failure Decay & Recovery:

Каждое срабатывание фильтра/ошибки увеличивает fail_stats

risk_factor плавно снижается (до 0.1) и восстанавливается по decay (раз в 60 мин)

apply_failure_decay() теперь вызывается с ускорением, если больше 30% пар имеют риск < 0.25

Telegram-уведомление при критическом уровне риска (>50%)

📏 Position Sizing Integration:

trade_engine.py уменьшает размер позиции пропорционально risk_factor

Telegram-уведомления при входе с пониженным риском (ниже 0.9x)

Все риски теперь рассчитываются от скорректированного размера

🔁 Adaptive Filter Logic:

passes_filters_optimized() теперь использует atr_threshold и rel_volume_threshold из runtime_config.json

Автоадаптация фильтров при низкой рыночной волатильности

Настройка adaptive_filters_enabled: true и rel_volume_threshold: 0.5 активирует гибкость

📡 Continuous Symbol Rotation:

continuous_scanner.py запускается каждые 15 минут

Пополняет inactive_candidates.json для ротации

Emergency fallback при малом числе активных пар включает BTC/ETH и другие надёжные символы

Telegram уведомление: "⚠️ Added essential fallback pairs..."

🧪 Risk Health Monitoring:

check_block_health() проверяет долю символов с risk_factor < 0.25

Ускоренный decay вызывается при превышении 30%

Telegram-оповещения при критической массе риска

Планировщик APScheduler вызывает проверку каждые 30 минут

📲 Telegram Integration Improvements:

Все команды используют централизованный telegram_handler

Устранены дубликаты сообщений (/status, /failstats, /summary и др.)

MarkdownV2 форматирование и безопасная обработка ошибок

📉 Обновление балансовой логики (150 → 300 USDC):

Везде заменён порог small account с 150 на 300 USDC

Это влияет на лимиты позиций, приоритет пар, расчёт риска

Поддержка приоритетных пар для баланса < 300

Риск-система и ротация адаптированы под скальпинг с небольшим депозитом

🟩 Проверка кода и совместимости:

🧹 Удаление legacy:

block_symbol() и blocked_symbols больше не используются

is_symbol_blocked() оставлен как stub для совместимости (всегда False)

✅ Проверка consistency:

Порог 300 USDC используется во всех модулях (strategy, pair_selector, position_manager)

Остался 1 случай 150 в risk_utils.py — рекомендуется обновить до 300

Документация обновлена: нет больше описания блокировок на 2h/4h/12h — заменено на decay

## Recent Enhancements

🔁 Recent Enhancements in v1.6.3
🔢 Updated Account Tiering System
The bot now uses a three-tier structure for account classification:

Small: balance < 120 USDC

Medium: 120–299 USDC

Standard: ≥ 300 USDC

This model replaces the previous binary (150-based) logic and provides finer control across:

Score thresholds and entry filters

TP/SL adaptation

Risk and leverage scaling

Telegram logging (e.g. /status, /risk, /scorelog)

Modules updated: entry_logger, score_logger, score_evaluator, config_loader, position_manager, strategy

🔄 Position Limit Unification
The logic for max concurrent positions has been fully unified:

position_manager.can_open_new_position() now calls get_max_positions() from config_loader.py

This ensures consistent enforcement of position limits based on balance across all modules

No more mismatch between hardcoded vs. adaptive logic

New scale:

<60 → 3 positions

<120 → 5

<300 → 7

<500 → 10

<1000 → 12

≥1000 → 15

🔥 Dynamic Aggressiveness & Score-Driven Risk
Aggressiveness and risk percent now adapt more precisely:

aggressiveness_controller.py uses account size and TP2 ratio to smooth aggressiveness updates

score_evaluator.py incorporates:

Signal score tiering

Win streak bonus

Priority pair boost (for small/medium balances)

Maximum risk caps:

<100 → 1.5%

<300 → 2.5%

≥300 → 5.0%

📊 Entry Quality Safeguards (Reversal Filter)
candle_analyzer.py blocks Doji / Engulfing patterns

strategy.py enforces entry quality score ≥ 0.4 for balances < 300

Helps avoid poor setups on small accounts and improve overall precision

✅ All of the above changes are now part of BinanceBot v1.6.3. They ensure:

Better protection for smaller accounts

Consistent behavior across strategy modules

Smarter trade filtering based on volatility, score, and balance

Unified risk logic across the board
