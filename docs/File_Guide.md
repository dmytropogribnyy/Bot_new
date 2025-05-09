📂 BinanceBot — File Guide (май 2025)
Актуальное описание структуры проекта и назначения всех ключевых файлов и модулей.

📦 Папки и модули
Папка / Файл Назначение
common/ Централизованная конфигурация (config_loader.py)
core/ Основная логика: стратегия, риск, сигналы, адаптация
telegram/ Telegram-команды, IP-защита, интерфейс
data/ Состояние бота, сделки, статистика, активности
docs/ Документация по проекту
logs/ Логи (main.log)
venv/ Виртуальное окружение (локальное)

🛠 Основные файлы и модули
Файл Описание
main.py Главный файл запуска, старт всех потоков и задач
config_loader.py Загрузка переменных окружения, DRY_RUN, ключи
trade_engine.py Вход и сопровождение сделок (TP/SL/BreakEven)
strategy.py Генерация сигналов, score, тренды, фильтры
pair_selector.py Ротация активных символов и выбор пар
risk_utils.py Расчёт риска, drawdown, адаптация ставок
tp_utils.py TP/SL логика, расчёт уровней, Soft Exit
tp_logger.py Логирование результата сделок
tp_optimizer.py TP/SL оптимизация по истории
tp_optimizer_ml.py ML-модель оптимизации TP1/TP2
htf_optimizer.py Анализ старшего таймфрейма
aggressiveness_controller.py Адаптация агрессивности по статистике
score_evaluator.py Расчёт итогового score по компонентам
entry_logger.py Лог попыток входа
order_utils.py Размер позиции, min_notional
engine_controller.py Smart Switching между сделками
notifier.py Telegram-уведомления о сигналах
ip_monitor.py Проверка смены IP и защита
utils_core.py Кэш баланса, данных и runtime конфиг
utils_logging.py Расширенное логирование, форматирование
score_logger.py Лог истории оценок score
score_heatmap.py Генерация теплокарты сигналов
volatility_controller.py Расчёт и адаптация волатильности
signal_feedback_loop.py Адаптация стратегии на основе TP/SL и missed
missed_tracker.py Трекинг упущенных сигналов
symbol_activity_tracker.py Учёт активности символов (под ротацию)
open_interest_tracker.py Усиление сигналов на основе Open Interest

📊 Важные файлы данных (/data/)
Файл Назначение
bot_state.json Текущий статус бота, флаги остановки
dynamic_symbols.json Текущие активные пары для торговли
entry_log.csv Все попытки входа, с оценками
tp_performance.csv История TP1/TP2/SL по сделкам
score_history.csv История и структура оценки сигналов
filter_adaptation.json История фильтров ATR/ADX/BB
missed_opportunities.json Пропущенные сигналы по символам
symbol_signal_activity.json Частота сигналов по каждому символу
trade_statistics.json Winrate, PnL, TP2%, успешность
last_ip.txt Последний IP-адрес
last_update.txt Метка последнего анализа и обновления

📊 Data файлы
Файл Назначение
bot_state.json Состояние бота (флаги stop/shutdown, сессия, разрешённые пользователи)
dry_entries.csv Лог попыток входа в сделку в режиме DRY_RUN (не участвуют в статистике)
dynamic_symbols.json Актуальный список активных пар на текущую сессию
entry_log.csv История входов по сигналам, включая причину и статус
filter_adaptation.json История и параметры адаптации фильтров ATR/ADX/BB
initial_balance.json Изначальный баланс для отслеживания роста депозита
last_ip.txt Последний известный внешний IP-адрес
last_update.txt Время последнего обновления параметров или конфигурации
missed_opportunities.json Пропущенные сигналы и потенциальные сделки
parameter_history.json История всех изменений параметров runtime_config
score_history.csv Хронология значений score по каждой попытке входа
symbol_signal_activity.json Частота сигналов по символам за последние сутки/час
tp_performance.csv Результаты сделок по TP1/TP2/SL для анализа стратегии
trade_statistics.json Сводная статистика по прибыли, winrate, сериям и пр.
