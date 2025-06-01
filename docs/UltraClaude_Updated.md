# UltraClaude Updated — Оптимизированный план развития BinanceBot

## Введение

Этот документ является полной заменой прежнего `ultra_claude.md`. Он разработан на основе объединённого анализа от GPT-4 и Claude Sonnet, содержит чёткую стратегию и архитектуру, направленную на решение главных проблем проекта BinanceBot: "торгового болота", перегрузки индикаторами и нестабильных сигналов.

📁 Обновлённая структура проекта (v1.6.6-refactored)
Проект полностью модульный и разделён по назначению. Ниже — актуальное описание всех директорий и ключевых файлов:

📂 Корень BINANCEBOT/
Файл Назначение
.env, .env.example Переменные окружения (API, режимы и параметры)
main.py Главная точка входа для запуска бота
config.py, constants.py Дефолтные значения и пути
clean_cache.py, safe_compile.py, restore_backup.py Утилиты очистки и восстановления
refactor_imports.py Структуризация импортов
pyproject.toml, requirements.txt Зависимости проекта
README.md Инструкция
start_bot.bat, push_to_github.bat, update_from_github.bat Windows-скрипты

📂 core/ — Логика стратегии и торговли
Файл Назначение
strategy.py Главная логика сигналов (should_enter_trade, unified check)
trade_engine.py Цикл входа, сопровождения и выхода из сделки
entry_logger.py, failure_logger.py Логирование входов и причин отказа
binance_api.py, exchange_init.py Доступ к Binance Futures
order_utils.py, tp_utils.py Построение TP/SL, trailing, break-even
risk_utils.py, balance_watcher.py Объём позиций, защита депозита
component_tracker.py Учёт сигналов EMA/RSI/MACD и их успешности
volatility_controller.py Глобальная рыночная волатильность
filter_adaptation.py, filter_optimizer.py Управление ATR/Volume фильтрами
priority_evaluator.py, symbol_priority_manager.py Приоритеты символов
engine_controller.py Управление торговыми потоками и soft exit
symbol_processor.py Сопровождение 1 символа в 1 потоке
score_evaluator.py, score_logger.py ❗️Устаревшие — удаляются при рефакторинге
signal_feedback_loop.py, aggressiveness_controller.py, candle_analyzer.py ❗️Кандидаты на удаление — используются в старом score-based подходе

📂 tools/ — Анализ и диагностика
Файл Назначение
continuous_scanner.py Периодический обход всех пар — формирует debug-сводки
debug_tools.py, missed_tracker.py Инструменты для ручной отладки
test_api.py, final_continuous_scan.py Проверка доступности API и символов
score_heatmap.py Построение теплокарты по компонентам (устарело)

📂 telegram/ — Telegram-интерфейс
Файл Назначение
telegram_commands.py Основные команды: /summary, /status, /signalstats, /rejections
telegram_utils.py Отправка сообщений, Markdown экранирование
telegram_handler.py Обработка входящих событий
telegram_ip_commands.py IP/роутер команды типа /ipstatus, /router_reboot
registry.py Регистр команд с категориями и описаниями

📂 data/ — Runtime и аналитика
Файл Назначение
entry_log.csv, tp_performance.csv Сделки, TP/SL результаты
component_tracker_log.json Статистика по успешности сигналов по компонентам
debug_monitoring_summary.json Обзор сигналов и отфильтрованных пар
runtime_config.json Основные параметры работы (ATR, объём и пр.)
missed_signals.json, signal_failures.json, failure_stats.json Причины отказов
parameter_history.json История изменения конфигураций
valid_usdc_symbols.json, dynamic_symbols.json Список доступных и активных пар
initial_balance.json, trade_statistics.json Баланс, доходность, winrate
priority_pairs.json, filter_adaptation.json Приоритеты и гибкие фильтры

📂 docs/ — Документация и планы
Файл Назначение
UltraClaude_Updated.md 📌 Основной стратегический файл проекта
todo_updated.md, Master_Plan.md Актуальные TODO и планы
Refactor_plan.md, checklist_for_run.md Чеклисты для рефакторинга
File_Guide.md, Mini_Hints.md Быстрые подсказки
Syntax_and_Markdown_Guide.md Форматирование сообщений Telegram

📂 logs/
Файл Назначение
main.log Полный лог операций и запусков бота

## ✅ Overall Assessment — v1.6.5-opt-stable

BinanceBot — устойчивый, самонастраивающийся фьючерсный торговый бот, оптимизированный под малые депозиты и короткие сделки. Архитектура модульная, масштабируемая, с адаптивной фильтрацией сигналов и динамической ротацией символов.

---

### ✅ Реализовано (по состоянию на v1.6.5-opt-stable):

🔹 **Symbol Selection & Monitoring**

-   Фильтрация только по ATR и объёму (без удаления `score=0`).
-   Использование `FILTER_TIERS` (0.006, 0.005 и т.д.) как доля цены.
-   Fallback: если нет отобранных пар → `filtered_data` → `USDC_SYMBOLS`.
-   Автоослабление фильтров при "тихом рынке" через `get_btc_volatility()`.
-   Telegram-уведомление, если ни одна пара не прошла фильтры.
-   Ротация пар через APScheduler (`rotate_symbols()` каждые 30 мин).
-   ContinuousScanner обновляет неактивные пары каждые 15 мин.
-   Автоинициализация `missed_opportunities.json` и `tp_performance.csv` в `main.py`.

🔹 **Signal Logic**

-   Стратегия основана на `fetch_data_multiframe()` с RSI, EMA, MACD, ATR, Volume.
-   Score рассчитывается по весам и проверяется через unified signal check ("1+1").
-   Реализована адаптация минимального score в зависимости от баланса, волатильности и времени.
-   Логика отказов (`missed_signal_logger.py`) и компонентов (`component_tracker.py`).

🔹 **Risk Management**

-   Graduated Risk вместо блокировок: `risk_factor ∈ [0.1–1.0]`.
-   Decay: автоматическое восстановление репутации символа.
-   Drawdown protection, Notional Check, TP2 winrate-адаптация.

🔹 **Telegram & DRY_RUN**

-   Команды: `/start`, `/stop`, `/summary`, `/failstats`, `/signalconfig`, `/missedlog`, `/hot`, `/scorelog`, и др.
-   Полное экранирование MarkdownV2.
-   DRY_RUN = без логов и CSV-файлов — только консоль.

---

### 🟡 Переносится в Phase 2.8 (не реализовано полностью):

| Задача                                        | Статус      | Комментарий                                                    |
| --------------------------------------------- | ----------- | -------------------------------------------------------------- |
| 🔄 Re-entry логика                            | 🔸 Частично | Повторные сигналы логгируются, но повторный вход не реализован |
| 📈 WebSocket сигналы                          | ⛔ Нет      | Используется polling — WebSocket ещё не подключён              |
| 📊 Графики PnL / winrate в Telegram           | ⛔ Нет      | Только текстовые отчёты, визуализация не реализована           |
| 🧠 Signal Intelligence                        | 🔸 Частично | Есть логгеры, но нет автоисключения слабых сигналов            |
| 📉 Smart fallback через continuous_candidates | ⛔ Нет      | Работает только absolute fallback, recovery не расширен        |
| 🔧 Объединение в symbol_controller            | ⛔ Нет      | selector, optimizer, scanner работают раздельно                |
| 📉 Автоадаптация min_dynamic_pairs            | ⛔ Нет      | Пока задаются вручную через config                             |

---

### 🔜 Следующий этап — Phase 2.8

-   Подключение WebSocket и переход от polling к push-сигналам
-   Визуализация через Telegram-графики (PNL, winrate, activity)
-   Реализация Re-entry логики и повторных входов
-   Введение полноценного Signal Intelligence с рейтингами, исключением
-   Расширенный smart fallback через continuous_candidates
-   Символ-контроллер: объединение фильтрации, сканирования и оптимизации
-   Автоадаптация min/max_dynamic_pairs по волатильности и балансу

---

BinanceBot v1.6.5-opt-stable — надёжная, автономная и гибкая система скальпинга с прозрачной логикой и мощной архитектурой. Готов к выходу на следующий уровень адаптации, визуализации и WebSocket-интеграции (Phase 2.8).

## 🔄 Стратегический переход: внедрение упрощённой логики сигналов (июнь 2025)

🎯 Причина перехода:
Аудит и диагностика сигналов показали, что:

использование комплексного score с динамическими порогами и весами привело к непрозрачности,

сложные компоненты типа HTF_CONFIDENCE, aggressiveness, volatility_controller и candle_analyzer дублируют фильтры и мешают отладке,

Telegram-команды и monitoring-система завязаны на устаревшую метрику score.

✅ Что будет внедряться:
Согласно новому плану (см. Аудит и Оптимизация Логики BinanceBot, май 2025):

Удаляется: расчёт score, адаптивные пороги, HTF-модификаторы.

Внедряется: логика 1 основной + 1 дополнительный сигнал (EMA + RSI, RSI + Volume и пр.).

Обновляется: should_enter_trade() — возвращает сигнал на основе breakdown без score.

Упрощается: entry_log.csv, debug_monitoring_summary.json, telegram_commands.py — работают на базе компонентного анализа.

Очищается: runtime_config — остаются только фиксированные фильтры ATR, Volume и min_pairs.

Упраздняются: компоненты score_evaluator.py, candle_analyzer.py, aggressiveness_controller.py, если они не участвуют в TP/SL.

📦 Схематически включает:
strategy.py — чистая логика сигналов

signal_utils.py — расчёт breakdown и unified check

entry_logger.py и missed_signal_logger.py — лог отказов по причинам

component_tracker.py — статистика по индикаторам

telegram_commands.py — команды /signalstats, /rejections, /summary обновлены под breakdown

📌 Этот переход подготовлен и согласован в рамках v1.6.5-opt-final → v1.7-beta.
📁 Детальный план с кодом и файлами: docs/refactoring_entry_logic.md.
