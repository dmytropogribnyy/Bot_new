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

## ✅ Реализовано (по состоянию на v1.7-final)

🔹 Symbol Selection & Monitoring

Фильтрация только по ATR и объёму (atr_threshold_percent, volume_threshold_usdc), без score.

Многоуровневая фильтрация через FILTER_TIERS, fallback на USDC_SYMBOLS при пустом результате.

Поддержка type=fixed/dynamic для каждой пары.

Ротация символов через rotate_symbols() каждые 30 минут.

continuous_scan() — каждые 15 минут логирует inactive пары.

Telegram-уведомление при отсутствии подходящих символов.

Инициализация missed_opportunities.json, tp_performance.csv, dynamic_symbols.json в main.py.

🔹 Signal Logic

Принцип 1+1 сигнал: стратегия основана на breakdown по EMA, RSI, Volume (через passes_1plus1()).

fetch_data_multiframe() объединяет 3m, 5m, 15m данные + индикаторы.

should_enter_trade() логирует причины отказа (filter_fail, missing_1plus1, cooldown, low_pnl, и др.)

component_tracker.py ведёт статистику успехов сигналов.

🔹 TP / SL / Exit Management

TP1, SL рассчитываются через calculate_tp_levels(), SL — по ATR.

TP2 заменён на трейлинг (run_adaptive_trailing_stop()).

soft_exit и auto_profit_exit реализованы.

Telegram-уведомления при TP1, SL, soft exit (в monitor_active_position()).

tp_performance.csv содержит: ATR, Type, Commission, Net PnL, Exit Reason.

🔹 Risk Management

Используется risk_factor для dynamic selection и qty расчёта.

Защита от избыточного размера (Notional Check, Margin Buffer).

Gradual Risk Recovery через decay.

Статистика win/loss/streak в config_loader.py готова под auto-risk.

🔹 Telegram & Monitoring

Полностью декораторная структура (@register_command) и категоризация.

Поддерживаются: /summary, /status, /runtime, /signalstats, /rejections, /log, /pairstoday, и др.

DRY_RUN работает на всех уровнях: сигналы, позиции, Telegram, CSV.

send_daily_summary() логирует сделки дня.

MarkdownV2 экранирование, fallback на plain text.

🟡 Переносится в Phase 2.8 (опционально/в работе)
Задача Статус Комментарий
🔄 Re-entry логика ✅ Частично Поддержка через повторные сигналы и tp1_sniper.py
📈 WebSocket сигналы ⛔ Нет Используется polling
📊 Графики PnL / winrate в Telegram 🕐 В планах CSV уже логирует, готово к визуализации
🧠 Signal Intelligence ✅ Базовая Через component_tracker, но без автоисключения
📉 Smart fallback через continuous_candidates ⛔ Нет Пока используется basic fallback при пустых парах
🔧 Symbol controller 🕐 Нет selector, rotation, optimizer — всё ещё отдельно
📉 Автоадаптация min_dynamic_pairs 🕐 Нет Пока задаётся вручную, filter_adaptation.py готов

🔜 Следующий этап — Phase 2.8
Подключение WebSocket и переход от polling к push-сигналам

/pnl_today, /dailycsv и Telegram-графики доходности

Расширение Re-entry логики + sniper повторных входов

Signal Intelligence: автоисключение слабых компонентов

Smart fallback (continuous_candidates, recovery блок)

Символ-контроллер: объединение логики фильтрации, подбора и анализа

Auto-risk на основе winrate и equity (модуль risk_adjuster.py)

Адаптация min/max_dynamic_pairs от баланса и волатильности

✅ Стратегический переход (v1.6.5 → v1.7)
Удалены: score, HTF_CONFIDENCE, adaptive thresholds

Введена логика: 1 основной + 1 дополнительный сигнал

Обновлены: should_enter_trade(), entry_log.csv, telegram_commands.py

Очищен: runtime_config.json

Обновлены: все Telegram-команды, monitoring, breakdown

Поддержка fixed/dynamic через JSON и runtime-поля

---

## 🔐 Финальная проверка:

Компонент Статус Комментарий
TP/SL, trailing, soft_exit ✅ Готово Все методы отлажены и логируются
Логика 1+1 сигналов ✅ Реализована Через passes_1plus1 и breakdown
risk_adjuster.py (auto-risk) ✅ Активен Запускается по scheduler каждый час
Telegram команды ✅ Работают /open, /status, /summary, /pairstoday и т.д.
DRY_RUN → REAL_RUN ✅ Проверено DRY отключён, Telegram работает, API ключи готовы
Логирование в CSV ✅ Завершено tp_performance.csv содержит ATR, Type, Exit Reason, Commission, Net PnL
Monitoring и decay ✅ Работает schedule_failure_decay, track_missed_opportunities, фильтры ослабляются
main.py финализирован ✅ Все потоки, scheduler, cron-задачи подключены
Риск-защита / ограничение Notional ✅ Проверяется при входе

🟢 Что ты имеешь:
Полностью адаптивный, безопасный и прозрачный скальпер

Telegram-интерфейс с расширенными командами

Runtime-адаптация риска на базе winrate и streak

Готовность к визуализации, WebSocket, и Phase 2.8

📌 Можешь запускать main.py с настоящими API-ключами и наблюдать:

Telegram-уведомления по сделкам

tp_performance.csv обновляется

/summary, /runtime, /log дают актуальные данные
