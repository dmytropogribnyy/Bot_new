# UltraClaude Updated — Оптимизированный план развития BinanceBot

## Введение

Этот документ является полной заменой прежнего `ultra_claude.md`. Он разработан на основе объединённого анализа от GPT-4 и Claude Sonnet, содержит чёткую стратегию и архитектуру, направленную на решение главных проблем проекта BinanceBot: "торгового болота", перегрузки индикаторами и нестабильных сигналов.

## Структура проекта

✅ Актуальная структура проекта (v1.6.5-opt-stable)
📁 Корень проекта BINANCEBOT/
Файл Назначение
.env, .env.example Переменные окружения: ключи API, режимы (DRY_RUN), конфиги
.gitignore, README.md Git и инструкция по проекту
pyproject.toml, requirements.txt Зависимости проекта (Poetry/pip)
main.py Главная точка запуска торгового бота
config.py Статические дефолтные параметры
restore_backup.py Восстановление состояния бота после сбоя
clean_cache.py Очистка временных файлов, логов и кэша
safe_compile.py Безопасная пересборка модулей
refactor_imports.py Автоматическая структурировка импортов
score_heatmap.py Генерация визуальных теплокарт по компонентам score
stats.py Расчёт TP/SL/Winrate и статистика по сделкам
start_bot.bat, push_to_github.bat, update_from_github.bat Утилиты запуска и синхронизации под Windows

📁 core/ — ядро стратегии
Файл Назначение
aggressiveness_controller.py Определение уровня агрессивности (на основе TP2 winrate)
balance_watcher.py Отслеживание роста капитала и фиксация PnL
binance_api.py Обёртка над Binance USDC Futures API
candle_analyzer.py Анализ свечей (MTF: 3m, 5m, 15m)
component_tracker.py Логирование вклада каждого индикатора в score
dynamic_filters.py Адаптация фильтров ATR и объёма в реальном времени
engine_controller.py Управление входами, smart switching, soft exit
entry_logger.py Логирование всех входов (entry_log.csv)
exchange_init.py Подключение и проверка доступа к API Binance
fail_stats_tracker.py Система decay и расчёт risk_factor по ошибкам
failure_logger.py Лог отказов по причинам: low score, cooldown и др.
filter_adaptation.py Управление relax_factor по символам
filter_optimizer.py Автосмягчение FILTER_TIERS по статистике
notifier.py Обработка уведомлений (вызовы Telegram изнутри core)
order_utils.py Построение TP1/TP2/SL, post-only ордеров
position_manager.py Учёт лимитов, управление открытыми позициями
priority_evaluator.py Расчёт приоритета символов на основе TP-статистики
risk_utils.py Drawdown, расчёт объёма позиции, защита
score_evaluator.py Расчёт score и breakdown по индикаторам
score_logger.py Логирование значений score и breakdown
signal_feedback_loop.py Runtime адаптация score, momentum, risk, relax
status_logger.py Обновление Telegram-статуса: пары, риск, экспозиция
strategy.py Основная логика сигналов и условий входа
symbol_priority_manager.py Управление приоритетами для маленького баланса
symbol_processor.py Сопровождение одной пары (1 позиция = 1 поток)
tp_utils.py Поддержка TP1/TP2, trailing stop, break-even
trade_engine.py Цикл торговли: входы, сопровождение, выходы
volatility_controller.py Расчёт глобальной рыночной волатильности (BTC, etc.)

📁 tools/
Файл Назначение
continuous_scanner.py Циклический анализ неактивных символов (15 мин)

📁 telegram/
Файл Назначение
telegram_utils.py Отправка сообщений, MarkdownV2, fallback
telegram_handler.py Обработка всех Telegram-событий
telegram_commands.py Команды: /summary, /status, /hot, /failstats, /regenpriority и др.
telegram_ip_commands.py IP-специфичные команды: /ipstatus, /router_reboot, /cancel_stop

📁 data/
Файл Назначение
entry_log.csv Реальные входы в позиции
tp_performance.csv TP1/TP2/SL по каждой сделке
missed_opportunities.json Упущенные сделки, где был потенциал
missed_signals.json Причины отказа по сигналам
score_history.csv История score по всем символам
symbol_signal_activity.json Активность сигналов по времени
component_tracker_log.json Статистика по индикаторам (MACD, RSI, EMA…)
parameter_history.json История изменений в runtime_config
runtime_config.json Текущие параметры стратегии (ATR, relax, min_dyn…)
priority_pairs.json Приоритетные символы (динамически)
failure_stats.json Кол-во отказов и результат decay по символам
failure_decay_timestamps.json Метки времени для decay
filter_adaptation.json Relax factor по каждому символу
bot_state.json Состояние бота: остановлен, запущен и т.д.
trade_statistics.json Общая PnL, winrate, max drawdown
valid_usdc_symbols.json, valid_usdc_last_updated.txt Кэш доступных USDC-пар
initial_balance.json, initial_balance_timestamps.json Баланс при старте + метка времени
last_ip.txt, last_update.txt Служебные данные
debug_monitoring_summary.json Сводка отладки сигналов из debug_tools

📁 docs/
Файл Назначение
UltraClaude_Updated.md 📌 Основной файл стратегии, фаз, структуры
todo_updated.md Актуальный TODO-план
Master_Plan.md Roadmap с фокусом на будущие фазы
File_Guide.md Этот файл — описание структуры проекта
Mini_Hints.md, project_cheatsheet.txt Подсказки и краткие шпаргалки
router_reboot_dry_run.md Поведение при перезагрузке роутера в DRY_RUN
router_reboot_real_run.md Поведение при реальном запуске
Syntax_and_Markdown_Guide.md Правила Markdown и Telegram-сообщений
Archive/ Старые и устаревшие версии документации

📁 logs/
Файл Назначение
main.log Основной лог всех действий бота

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
