### 🔹 Обновлённый аудит BinanceBot (v1.6.1-dev) — апрель 2025

---

## 1. Общий обзор

### 1.1 Структура проекта

**Core:**

- main.py — точка входа, запуск потоков
- config.py — конфигурация
- strategy.py — логика сигналов
- trade_engine.py — вход/TP/SL/trailing/break-even
- engine_controller.py — цикл с Smart Switching
- score_evaluator.py — оценка score (adaptive, weighted)
- aggressiveness_controller.py — динамика aggressive уровня
- pair_selector.py, symbol_processor.py, binance_api.py, balance_watcher.py
- entry_logger.py, tp_logger.py, stats.py, score_heatmap.py
- tp_optimizer.py, tp_optimizer_ml.py, htf_optimizer.py

**Telegram:** telegram_commands.py, telegram_utils.py, telegram_ip_commands.py, telegram_handler.py

**Утилиты:** utils_core.py, utils_logging.py

---

### 1.2 Соответствие TODO.md (v1.5/v1.6)

#### ✅ Completed:

- Modular architecture
- DRY_RUN / REAL_RUN разделение: исключена запись в CSV/JSON
- Smart Switching
- Adaptive Score + threshold tuning (score_evaluator.py + strategy.py)
- Aggressiveness System (aggressiveness_controller.py + EMA smoothing)
- Telegram команды: /score_debug, /aggressive_status
- TP1/TP2/SL/trailing/break-even (+ auto-extension logic)
- Reports: daily, weekly, monthly, YTD
- HTF filter + ML optimization (htf_optimizer.py)
- TP ML loop (без feedback)
- Auto resume / config backup

#### ⏳ In Progress:

- 📊 **PnL Graphs**: stats.py — нет generate_pnl_graph(), matplotlib-графиков
- 🌡️ **Signal Heatmap**: есть score_history.csv, нет визуализации/Telegram
- ↻ **Config cleanup (volatility filters)**: фильтры ATR/ADX/BB размазаны в strategy.py
- 🧠 **ML Feedback Loop**: tp_optimizer_ml.py — нет обратной связи с tp_logger.py

#### ❌ Not Started (Planned):

- ⚡ WebSocket feed (websocket_manager.py)
- ⛏ Open Interest (oi_tracker.py)
- 🔒 Soft Exit logic
- ↗ Auto-scaling position size
- ⟳ Re-entry logic
- 🌐 REST API (rest_monitor.py / api_server.py)

---

### 1.3 Критические требования

**DRY_RUN исключён:** CSV/JSON записи работают только в REAL_RUN (score_history, entry_log, tp_performance, dynamic_symbols).

**Fallback API:**

- Все обращения через safe_call()
- ⚠ trade_engine.py пока содержит raw вызовы exchange._ (fetch_ticker, create_order) — нужно заменить на api._

**Score & Aggressive:**

- score = normalized weighted system + adaptive threshold
- get_aggressiveness_score() вместо is_aggressive (EMA 1d)

**Telegram:**

- MarkdownV2 экранирование исправлено
- Все ключевые команды работают корректно

---

### 1.4 📃 Конкретные файлы в работе

| Файл                   | Статус         | Действие                                     |
| ---------------------- | -------------- | -------------------------------------------- |
| **trade_engine.py**    | 🟠 In progress | safe_call(exchange.\*) вместо raw вызовов    |
| **stats.py**           | ❌ Not started | График PnL (generate_pnl_graph), Telegram    |
| **score_heatmap.py**   | 🟡 Partial     | Telegram-отчёт, фильтры по score/time        |
| **tp_optimizer_ml.py** | 🟡 Partial     | Feedback loop с tp_logger + threshold update |
| **rest_monitor.py**    | ❌ Missing     | REST API через Flask/FastAPI                 |

---

## 2. Вывод

- ✅ **v1.5** TODO — полностью выполнено
- ✅ Часть v1.6 — выполнена и протестирована
- ⚠ Остающее требует дописи модулей или визуализации

---

## 3. Следующие шаги

- 📅 Протестировать REAL_RUN с полным логированием
- 📊 Добавить matplotlib-график в stats.py
- 🛠️ Завершить WebSocket: websocket_manager.py
- 🔎 Реализовать oi_tracker.py + Soft Exit (trade_engine)
- 🔢 Завершить API fallback в trade_engine.py
- 🌿 (опц.) динамическая адаптация весов score

---

⚖️ Статус: **актуален на апрель 2025**
