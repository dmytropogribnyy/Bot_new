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
----- priority_evaluator.py # Оценка приоритета символов
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

Удалённые/устаревшие методы
fetch_data() и fetch_data_optimized(): полностью исключены (заменены на fetch_data_multiframe()).

passes_filters_optimized(), determine_strategy_mode(), scalping_mode, а также уникальные индикаторы типа MACD_RSI, MACD_EMA — убраны.

Логика now целиком строится на: calculate_score() + passes_unified_signal_check() + risk_factor.

Новая логика сигналов и score

1. fetch_data_multiframe() как основной источник
   Вместо нескольких отдельных функций, бот загружает свечи 3m, 5m, 15m в один DataFrame, считает rsi_5m, ema_3m, macd_5m и т.д. Все расчёты (Volume Spike, PriceAction, HTF-тренд) проводятся внутри этого единого метода.

2. Расчёт score + breakdown
   В файле score_evaluator.py функция calculate_score(df) суммирует веса:

RSI (примерно +1.0)

MACD (примерно +1.2)

EMA_CROSS (примерно +1.2)

Volume (примерно +0.5, если объём выше 1.5× средней)

HTF (+0.5, если старший TF подтверждает вход)

PriceAction (+0.5, если аномально большая свеча)

Веса (SCORE_WEIGHTS) по умолчанию заданы либо внутри score_evaluator.py, либо в config_loader.py. Также вы можете хранить их в runtime_config.json и подгружать на лету. Для продвинутой адаптации веса можно корректировать по мере набора статистики.

Возврат: (score, breakdown)
где score — число (обычно до 3–4), а breakdown — словарь { "MACD":1.2, "Volume":0.5, ... } с вкладом каждого индикатора.

3. Unified signal check («1+1»)
   После расчёта score следует проверка passes_unified_signal_check(score, breakdown). Логика:

Должен быть минимум 1 основной сигнал (MACD, EMA_CROSS, RSI)

И минимум 1 дополнительный (Volume, HTF, PriceAction)

Если score < 2.5, обязательна поддержка EMA (или комбинации MACD+EMA).

Это гарантирует, что бот не откроет сделку на одной «сильной» метрике без подтверждения другим видом индикатора.

4. Порог входа (min_required) и адаптивность
   get_adaptive_min_score(...) может повысить/понизить необходимый score в зависимости от:

Баланс <300 USDC → снижаем порог

Время суток (ночные часы — повышаем порог)

Volatility (flat / breakout)
Если score не дотягивает — сделка отклоняется с причиной "insufficient_score".

Но при условии, что если score чуть-чуть ниже порога, и всё же выполнено «1+1» + тренд/EMA, — можно разрешить вход (зависит от вашей внутренней настройки, это описано в strategy.py).

Graduated Risk & Decay
Отказ от binary blocking
Ранее символы могли полностью block_until (2h/4h/12h). Теперь:

fail_stats_tracker.py ведёт счёт неудач по symbol.

get_symbol_risk_factor(symbol) возвращает фактор (0.1–1.0) — снижается при больших провалах, восстанавливается apply_failure_decay().

При входе риск/объём позиции просто уменьшается (напр. risk_factor=0.5 → половинная позиция).
Никакой жёсткой блокировки: символ можно торговать, но с пониженным риском.

risk_utils
Адаптивные функции вроде get_adaptive_risk_percent(balance, atr_percent, ...) учитывают win_streak, volumе, score → итоговый risk%

Drawdown protect: при падении баланса >15% бот может паузиться автоматически (настраивается).

Логирование сигналов и отказов

1. missed_signal_logger.py
   Записывает в data/missed_signals.json все отказы, их причины (cooldown_active, insufficient_score, signal_combo_fail, candle_pattern и т.п.).
   Команда /missedlog читает и показывает последние N пропущенных сигналов.

2. component_tracker.py
   После открытия сделки вызывается log_component_data(symbol, breakdown, is_successful=True), где фиксируется, какие индикаторы участвовали.
   Команда /signalstats:

Выводит, сколько раз (и с какой успешностью) участвовали RSI, MACD, HTF и т.д.

Также может показать, сколько candlestick_rejections сработало (если используете паттерны свече́й).

Новые команды Telegram
/lastscore <symbol>
Выводит последний рассчитанный score и breakdown для заданного символа, указывает причину (если была).
Пример:

yaml
Copy
BTC/USDC (score=2.2) breakdown: MACD=1.2, RSI=1.0 → Rejected: no secondary
/missedlog
Показывает до 10 последних пропущенных сигналов, указывая score, активные индикаторы и причину отказа.

/signalstats
Сводка об участии компонентов (MACD, RSI, Volume…) и их результатах.

makefile
Copy
MACD: count=40 (win=25, last_used=2025-05-10)
RSI: count=35 (win=22) ...
/signalconfig (опционально)
Кратко выводит текущие веса индикаторов (SCORE_WEIGHTS), минимальный порог, relax_boost и т.д., если нужно.

DRY_RUN: полностью чистая симуляция
При DRY_RUN бот не пишет никаких данных в tp_performance.csv, entry_log.csv, trade_statistics.json и т.д.

Логи сделок/пропущенных сигналов отображаются только в консоли для отладки. Это предотвращает «засорение» статистики тестовыми входами.

При возвращении бота в LIVE-режим (DRY_RUN=false) всё полноценно ведётся, включая запись результатов и риск-статистики.

Итог: v1.6.2-Final
fetch_data_multiframe() — единый универсальный источник OHLCV и расчётов RSI, EMA, MACD и пр.

Score + breakdown → unified signal check («1+1»)

Graduated Risk вместо блокировки

Adaptивные пороги и runtime_config

Полное логирование пропусков (missed_signal_logger) и вкладов (component_tracker)

Новые Telegram-команды для прозрачности

DRY_RUN без побочных эффектов

Очистка Legacy: passes_filters_optimized, determine_strategy_mode, fetch_data() удалены

Дальнейшие шаги (Phase 2.7+)
Возможна реализация score_heatmap.py (визуализация теплокарты), улучшенный ML-режим TP (tp_optimizer_ml.py), re-entry logic, auto-weights адаптация.

Все будущие обновления будут основываться на данной стабильной базе v1.6.2.

Важно:
Этот документ является основным описанием актуального состояния бота. Всё устаревшее (gpt_signals_approach.md, new_chat.md, и т.п.) следует перенести в архив.

Вывод
BinanceBot v1.6.2-final — стабильная, модульная и прозрачная система для фьючерс-торговли на USDC, которая:

Использует логику «1 основной + 1 дополнительный сигнал»,

Имеет гибкий, многокомпонентный score и адаптивные пороги,

Ведёт расширенное логирование входов/отказов,

Опирается на graduated risk вместо блокировки,

Предоставляет удобный Telegram-интерфейс для мониторинга и настройки.

Это даёт высокую надёжность и гибкость при торговле с малыми и средними балансами, а также облегчает анализ и отладку благодаря подробным логам и прозрачным командам.

---

## Current update

# UltraClaude Updated — Оптимизированный план развития BinanceBot

## Обновление: Шаги 2+ (Май 2025)

После успешной нормализации формата символов (Шаг 1), бот переходит к следующему этапу оптимизации архитектуры работы с парами и сигналами:

### 🔧 Шаг 2. Фильтрация только по ATR и объёму

-   Удалена любая фильтрация по score.
-   В `pair_selector.py` фильтры используют только:
    ```python
    atr_percent = atr / price
    volume_usdc = df["volume"].mean() * price
    ```
-   `atr_percent` сравнивается с FILTER_TIERS, заданными в runtime_config.json в долях (0.006 = 0.6%).

### 🔧 Шаг 3. FILTER_TIERS и согласованная шкала ATR

-   Все значения `atr` в FILTER_TIERS интерпретируются как доля цены.
-   Пример:

```json
"FILTER_TIERS": [
  {"atr": 0.006, "volume": 600},
  {"atr": 0.005, "volume": 500}
]
```

### 🔧 Шаг 4. Пары с `score = 0` не исключаются

-   Пара остаётся в `filtered_data`, даже если её `performance_score = 0`
-   Сортировка происходит по `performance_score`, но не влияет на включение в `filtered_data`

### 🔧 Шаг 5. Fallback при пустом отборе

```python
if not selected_dyn and filtered_data:
    selected_dyn = list(filtered_data.keys())[:min_dyn]
if not selected_dyn and not filtered_data:
    selected_dyn = USDC_SYMBOLS[:min_dyn]
```

-   Бот всегда продолжает работу, даже если рынок «тихий»

### 🔁 Шаг 6. Непрерывная ротация и Live-мониторинг

-   В `main_loop_runner.py` запущены два потока:
    1. Ротация пар (`select_active_symbols()`) каждые 15 мин
    2. Проверка сигналов (`should_enter_trade()`) каждые 30 сек
-   `main.py` не завершает работу при `not symbols`, а ждёт и повторяет

### 🧠 Шаг 7. Актуализация `debug_tools.py` и `filter_optimizer.py`

-   Все symbol → `normalize_symbol(symbol)`
-   `atr_percent` логируется в процентах (×100), но сравнивается как доля
-   filter_optimizer адаптирует `FILTER_TIERS` по итогам `debug_monitoring_summary.json`

---

## 🔁 Вставка в Финальный План (Phase 2.6+)

Добавить в раздел `Phase 2.6 — Visualization & Analytics`:

### ✅ Phase 2.6A — Continuous Symbol Monitoring

-   Введена модульная структура live-мониторинга через `main_loop_runner.py`
-   Восстановлена логика fallback, исключающая остановку при `0 active symbols`
-   Обеспечена ротация пар и постоянная проверка входов без выхода из цикла

---

## ✅ Итог:

BinanceBot теперь устойчив даже при отсутствии сигналов, не завершает работу при пустом списке, и автоматически адаптирует фильтры и активные пары. Все компоненты синхронизированы по формату symbol и шкале фильтрации ATR.
