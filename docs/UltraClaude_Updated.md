# UltraClaude Updated — Оптимизированный план развития BinanceBot

## Введение

Этот документ является полной заменой прежнего `ultra_claude.md`. Он разработан на основе объединённого анализа от GPT-4 и Claude Sonnet, содержит чёткую стратегию и архитектуру, направленную на решение главных проблем проекта BinanceBot: "торгового болота", перегрузки индикаторами и нестабильных сигналов.

## Структура проекта

BINANCEBOT/
├── .env, .env.example # Переменные окружения
├── .gitignore, README.md # Git и инструкции запуска
├── pyproject.toml, requirements.txt # Pip-зависимости
├── main.py # Точка входа
├── config.py # Глобальные параметры
├── start_bot.bat, push_to_github.bat, update_from_github.bat
├── restore_backup.py # Восстановление состояния
├── clean_cache.py, safe_compile.py # Очистка и сборка
├── score_heatmap.py # Визуализация score
├── stats.py # Расчёт и сбор статистики (TP/Winrate)
├── refactor_imports.py # Импорт-проверка

├── core/ # Основная торговая логика
│ ├── aggressiveness_controller.py # Адаптация риска на основе TP winrate
│ ├── balance_watcher.py # Мониторинг баланса и PnL
│ ├── binance_api.py # Обёртка над Binance API
│ ├── candle_analyzer.py # Анализ свечей по таймфреймам
│ ├── dynamic_filters.py # ATR / объём / relax адаптация
│ ├── engine_controller.py # Smart Switching и soft exit
│ ├── entry_logger.py # CSV-логирование всех попыток входа
│ ├── exchange_init.py # Инициализация API и сессии
│ ├── fail_stats_tracker.py # Decay + прогрессивная блокировка
│ ├── failure_logger.py # Логирование ошибок символов
│ ├── filter_adaptation.py # Управление порогами фильтров
│ ├── notifier.py # Telegram-уведомления
│ ├── order_utils.py # Построение ордеров (post_only и пр.)
│ ├── position_manager.py # Учёт и контроль открытых позиций
│ ├── risk_utils.py # Drawdown, notional check, capital control
│ ├── score_evaluator.py # Расчёт и нормализация итогового score
│ ├── score_logger.py # Логирование компонентов score
│ ├── signal_feedback_loop.py # Runtime адаптация параметров стратегии
│ ├── status_logger.py # Статус в консоль и Telegram
│ ├── strategy.py # Логика сигналов (RSI, EMA, MACD, ATR, VWAP)
│ ├── symbol_priority_manager.py # Управление приоритетами символов
│ ├── symbol_processor.py # Обработка одного символа
│ ├── tp_utils.py # Поддержка TP1/TP2 логики
│ ├── trade_engine.py # Входы/выходы, TP/SL/auto-profit/flat exit
│ └── volatility_controller.py # Волатильность и фильтрация по объёму

├── common/
│ └── config_loader.py # Загрузка переменных окружения и runtime_config

--tools
-- continuous_scanner.py # Мониторинг неактивных символов

├── telegram/
│ ├── telegram_utils.py # Telegram API + MarkdownV2
│ ├── telegram_handler.py # Обработка всех команд
│ ├── telegram_commands.py # /start, /stop, /summary и др.
│ └── telegram_ip_commands.py # /ipstatus, /router_reboot и т.д.

data/
├── bot_state.json # Состояние сессии бота (включен, остановлен, shutdown и т.д.)
├── dry_entries.csv # Попытки входов в DRY_RUN режиме
├── dynamic_symbols.json # Список выбранных активных символов на текущую сессию
├── entry_log.csv # Лог всех реальных входов в сделки
├── failure_stats.json # Счётчики ошибок по символам и причинам
├── failure_decay_timestamps.json # Метки последнего уменьшения счетчиков ошибок
├── filter_adaptation.json # Параметры динамических фильтров ATR/volume и пр.
├── initial_balance.json # Исходный баланс при запуске сессии
├── initial_balance_timestamps.json # Временные метки инициализации баланса
├── last_ip.txt # Последний обнаруженный внешний IP
├── last_update.txt # Время последнего успешного обновления данных
├── missed_opportunities.json # Упущенные сделки (high потенциал, не открыта)
├── pair_performance.json # Производительность по парам (winrate, профит, count)
├── parameter_history.json # История адаптированных параметров (TP, score, risk и пр.)
├── runtime_config.json # Активная конфигурация стратегии в реальном времени
├── score_history.csv # История score значений по символам
├── signal_failures.json # История неудачных попыток сигналов (причины отказа)
├── symbol_signal_activity.json # Активность сигналов по символам за последние часы
├── tp_performance.csv # История TP1/TP2/SL по сделкам (для оптимизации)
└── trade_statistics.json # Сводная торговая статистика (PnL, winrate, risk и др.)

├── docs/ # Документация проекта
│ ├── UltraClaude_Updated.md # Финальная стратегия и архитектура
│ ├── Master_Plan.md # Roadmap и статус задач
│ ├── File_Guide.md # Структура проекта
│ ├── Syntax_and_Markdown_Guide.md
│ ├── PracticalGuideStrategyAndCode.md
│ ├── Mini_Hints.md, project_cheatsheet.txt
│ ├── router_reboot_dry_run.md
│ ├── router_reboot_real_run.md
│ └── Archive/ # Старые версии

├── logs/
│ └── main.log

├── tp_logger.py # Логирование TP/SL и причин выхода
├── tp_optimizer.py # Базовая TP-оптимизация
├── tp_optimizer_ml.py # ML-подход к TP адаптации
├── htf_optimizer.py # Адаптация фильтра HTF
├── missed_tracker.py # Учёт упущенных возможностей
├── ip_monitor.py # Отслеживание смены IP-адреса
├── symbol_activity_tracker.py # Учёт активности символов
├── utils_core.py # Вспомогательные функции и кэш
└── utils_logging.py # Форматирование логов и уровни

## ✅ Overall Assessment

BinanceBot — надёжный, адаптивный и безопасный бот, оптимизированный под фьючерсную торговлю с малыми депозитами. Архитектура модульная, гибкая, готова к масштабированию.

🧩 Implementation Quality
Модульная архитектура, изоляция DRY_RUN

Централизованный конфиг, runtime_config

Безопасная остановка и восстановление

Telegram-интерфейс с расширенными командами

Runtime адаптация параметров на основе TP/HTF/Score/Volatility

Thread-safe логика, защита от ошибок и флагов

💡 Key Strengths
✅ Small Deposit Optimization
Tier-based адаптация депозита (0–119, 120–249, 250–499…)

Dynamic risk/score thresholds

Smart Switching и микропрофит

Автоматический выбор активных пар

Поддержка повторного входа и soft exit

✅ Advanced Risk Management
Агрессивность на основе TP winrate

Drawdown защита

Переменный риск по TP2 winrate

Smart scaling и notional-проверка

✅ Market Adaptability
HTF фильтр и его Confidence

Автоадаптация wick / volatility / relax

Momentum, MACD, RSI, Bollinger

Open Interest как триггер усиления сигнала

Волатильностные фильтры и ротация пар

✅ Effective Integration
Полный Telegram-бот: команды, отчёты, логи

Auto-ротация пар, логика активности

Daily/Weekly/Monthly/Yearly отчёты

Полная логика missed opportunities и Smart Reentry

Heatmap по score и runtime config адаптация

✅ Current Status Summary
Текущая версия: v1.6.5-opt-stable
Режим: REAL_RUN
Ошибки: отсутствуют
Стабильность: подтверждена
Адаптация: активна и проверена

## Цели и приоритеты

### Главные задачи:

-   Устранить "болото" и заблокированные пары
-   Обеспечить 7–10 активных, торгуемых пар в любой момент
-   Выдавать только качественные, подтверждённые сигналы
-   Минимизировать избыточные индикаторы
-   Оптимизировать под краткосрочную скальпинг-торговлю USDC Futures (EU compliant)

## Обзор решений

### 🔁 Dynamic Symbol Priority

-   Символы не блокируются навсегда — у них просто падает приоритет
-   Внедряется `SymbolPriorityManager` (оценка событий за последний час)
-   Приоритет обновляется на основе успешности / неудач
-   Прогрессивная блокировка: 2ч → 4ч → до 12ч
-   Отпадание блокировок — автоматически по decay (раз в 3 часа)
-   Используется скользящее окно, а не накопительные счётчики

### ♻️ Постоянная ротация и пополнение пар

-   Внедряется ContinuousScanner: сканирует все неактивные пары на предмет всплесков
-   Emergency-режим добавляет пары с мягкими фильтрами при нехватке активных
-   Ротация происходит каждые 60 сек, всегда поддерживается минимум 5–6 пар, приоритет — 7–10
-   Все пары с приоритетом ≥ 0.3 попадают в кандидатский список

### 📊 Оптимизация индикаторов

-   Используются только RSI(9), EMA(9/21), MACD, ATR, объём
-   Исключены ADX, BB, сложные паттерны
-   Все сигналы стандартизированы через `calculate_score`
-   Вход возможен только при достаточном совокупном score (0–5 шкала)
-   Адаптивный `min_score`: зависит от баланса, волатильности, сессии

### 🧠 Multi-Timeframe & Scalping Support

-   Основной анализ: 3m, 5m (вход); 15m, 1h (контекст)
-   Внедрён MultiTimeframeAnalyzer (1m, 3m, 5m, 15m)
-   Поддержка «раннего сигнала» при расхождении таймфреймов (арбитраж во времени)

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

## 🧹 Что можно удалить (опционально)

-   `fetch_data()` — если больше не используется вообще
-   `passes_filters()` — если все сделки уже используют `passes_filters_optimized()`
-   Старые переменные в config: `USE_HTF_CONFIRMATION`, `BB_BAND_WIDTH_THRESHOLD`, `ADX_THRESHOLD`

---

## 📌 Текущая версия: `v1.6.2-final`

✅ Стабильная, адаптивная, Telegram-интеграция, полная поддержка flat/soft exit, runtime feedback, унифицированный pipeline.

📎 _Развёрнутые реализации и примеры кода перенесены в `UltraClaude_Expanded.md` (архив в /docs/Archive/)_

fetch_data() и passes_filters() можно удалить, если fallback не используется в режиме STANDARD. В текущей версии стратегия полностью перешла на fetch_data_optimized() и passes_filters_optimized().

check_auto_profit() теперь стабильно активен для сделок с удержанием менее 60 минут и PnL ≥ 2.2%, при этом TP1 не должен быть достигнут — позволяет зафиксировать быстрый профит в условиях высокой волатильности.

📌 Эти уточнения завершают реализацию фазы 2.5 и подтверждают завершённость версии v1.6.2-final.
