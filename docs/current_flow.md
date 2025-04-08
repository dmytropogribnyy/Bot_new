Обновлённый аудит BinanceBot (v1.6.1-final) — апрель 2025

1. Общий обзор

1.1 Структура проекта

Core:

main.py — точка входа, запуск потоков

config.py — конфигурация

strategy.py — логика сигналов

trade_engine.py — вход/TP/SL/trailing/break-even

engine_controller.py — цикл с Smart Switching

score_evaluator.py — оценка score (adaptive, weighted)

aggressiveness_controller.py — динамика aggressive уровня

pair_selector.py, symbol_processor.py, binance_api.py, balance_watcher.py

entry_logger.py, tp_logger.py, stats.py, score_heatmap.py

tp_optimizer.py, tp_optimizer_ml.py, htf_optimizer.py

Telegram: telegram_commands.py, telegram_utils.py, telegram_ip_commands.py, telegram_handler.py

Утилиты: utils_core.py, utils_logging.py

1.2 Соответствие TODO.md (v1.5/v1.6)

✅ Completed:

Modular architecture

DRY_RUN / REAL_RUN разделение: исключена запись в CSV/JSON

Smart Switching

Adaptive Score + threshold tuning (score_evaluator.py + strategy.py)

Aggressiveness System (aggressiveness_controller.py + EMA smoothing)

Telegram команды: /score_debug, /aggressive_status

TP1/TP2/SL/trailing/break-even (+ auto-extension logic)

Reports: daily, weekly, monthly, YTD

HTF filter + ML optimization (htf_optimizer.py)

TP ML loop (tp_optimizer_ml.py + feedback + threshold update)

Auto resume / config backup

Telegram MarkdownV2 fully supported

✅ entry_logger.py защищён от DRY_RUN — лог только в консоль через log_dry_entry

✅ trade_engine.py полностью переведён на safe_call() с fallback и метками

⏳ In Progress:

📊 PnL Graphs: stats.py — нет generate_pnl_graph(), matplotlib-графиков

🌡️ Signal Heatmap: есть score_history.csv, нет визуализации/Telegram

↻ Config cleanup (volatility filters): фильтры ATR/ADX/BB размазаны в strategy.py

❌ Not Started (Planned):

⚡ WebSocket feed (websocket_manager.py)

⛏ Open Interest (oi_tracker.py)

🔒 Soft Exit logic

↗ Auto-scaling position size

⟳ Re-entry logic

🌐 REST API (rest_monitor.py / api_server.py)

1.3 Критические требования

DRY_RUN исключён: CSV/JSON записи работают только в REAL_RUN (score_history, entry_log, tp_performance, dynamic_symbols).

Fallback API:

Все обращения через safe_call()

✅ Все raw вызовы в trade_engine.py заменены на safe_call с проверками и fallback

Score & Aggressive:

score = normalized weighted system + adaptive threshold

get_aggressiveness_score() вместо is_aggressive (EMA 1d)

Telegram:

MarkdownV2 экранирование исправлено

Все ключевые команды работают корректно

1.4 📃 Конкретные файлы в работе

Файл

Статус

Действие

trade_engine.py

✅ Done

Все вызовы exchange.\* заменены на safe_call()

stats.py

❌ Not started

График PnL (generate_pnl_graph), Telegram

score_heatmap.py

🟡 Partial

Telegram-отчёт, фильтры по score/time

rest_monitor.py

❌ Missing

REST API через Flask/FastAPI

websocket_manager.py

❌ Missing

Подключение WebSocket и async feed

2. Вывод

✅ v1.5 TODO — полностью выполнено

✅ Основные задачи v1.6 выполнены и протестированы

⚠ Остались визуализация и WebSocket-этапы

3. Следующие шаги

🗓 Протестировать REAL_RUN с полным логированием

📊 Добавить matplotlib-график в stats.py

🛠️ Завершить WebSocket: websocket_manager.py

🔎 Реализовать oi_tracker.py + Soft Exit (trade_engine)

🔢 Завершить API fallback в trade_engine.py ✅ (готово)

🌿 (опц.) динамическая адаптация весов score

⚖️ Статус: v1.6.1-final, актуален на апрель 2025
