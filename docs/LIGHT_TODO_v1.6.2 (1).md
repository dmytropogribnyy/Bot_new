# BinanceBot — LIGHT TODO v1.6.3-next [Priority 0: Устойчивость и стабильность]

Это обновлённый список задач для фазы Priority 0, направленной на повышение надежности бота перед расширением функциональности.

---

## Priority 0 — Устойчивость и стабильность (Стабилизирующий блок) ✅

### 1. Внедрить safe_call_retry

- **Цель:** Увеличить устойчивость вызовов Binance API к временным сбоям.
- **Статус:** ✅ Функция реализована в `utils_core.py` и интегрирована в:
  - `trade_engine.py` (fetch_ticker, create_limit_order, create_order, fetch_ohlcv)
  - `strategy.py` (fetch_data)
  - `pair_selector.py` (load_markets, fetch_ohlcv)
  - `binance_api.py` (fetch_balance, fetch_ticker и т.д.)

### 2. Централизация last_trade_info через TradeInfoManager

- **Цель:** Исключить race conditions при доступе к информации о сделках.
- **Статус:** ✅ Создан класс TradeInfoManager в `trade_engine.py` с методами `add_trade`, `get_trade`, `update_trade` и `remove_trade`. Все обращения к last_trade_info заменены на вызовы через trade_manager.

### 3. Адаптация интервалов polling (DRY_RUN vs REAL_RUN)

- **Цель:** Снизить нагрузку и шум в логах при тестировании.
- **Статус:**
  - `telegram_handler.py`: задержка опроса изменена на `time.sleep(60 if DRY_RUN else 3)`.
  - `ip_monitor.py`: интервал проверки IP выставлен на `check_interval = 120 if DRY_RUN else 30 * 60`.
- Дополнительно: В engine_controller.py добавлены временные фильтры для логов «Checking {symbol}» и «Balance for cycle» (не чаще 5 минут).

---

## Следующие шаги

### Priority 1 — Расширение логики входа и сопровождения

- **♻️ Smart Re-entry Logic:** Внедрение повторного входа по той же паре при повторном сильном сигнале (с использованием cooldown и score).
- **🔄 Soft Exit / Partial TP Optimization:** Идея адаптивного выхода, если TP1 почти достигнут.
- **📊 Auto TP/SL based on market regime:** Автоматическая настройка TP/SL в зависимости от рыночного режима (flat vs trending).

### Priority 2 — Улучшения стратегического ядра

- Передача relax_factor в score_evaluator.py, улучшение calculate_score() и анализ отказов сделок.

### Priority 3 — UI, отладка и безопасность

- Введение команды `/errors`, расширение `/summary`, вывод текущей агрессивности и прочее.

### Maintenance / Housekeeping

- Удаление устаревшего LIGHT_TODO_v1.6.2.md и обновление README/SUMMARY.md.

---

**Итог:** Priority 0 полностью завершена. Все изменения для повышения стабильности и устойчивости (safe_call_retry, TradeInfoManager, адаптированные интервалы polling, оптимизация логирования) внедрены и протестированы.

---

Что дальше?
Предлагаю перейти к Priority 1: внедрение Smart Re-entry Logic. Для этого нам потребуется обновить логику входа в сделку (в strategy.py) и, возможно, управление сделками (в trade_engine.py).

Если все устраивает, можем отметить Priority 0 как завершенное, и я готов продемонстрировать или обсудить план для Priority 1.
