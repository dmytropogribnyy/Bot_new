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

BinanceBot — LIGHT TODO v1.6.3-next
Priority 0 — Устойчивость и стабильность (Стабилизирующий блок) ✅
Внедрить safe_call_retry

Цель: Увеличить устойчивость вызовов Binance API к временным сбоям.

Статус: ✅ Реализована в utils_core.py и интегрирована в:

trade_engine.py (fetch_ticker, create_limit_order, create_order, fetch_ohlcv)

strategy.py (fetch_data)

pair_selector.py (load_markets, fetch_ohlcv)

binance_api.py (fetch_balance, fetch_ticker и т.д.)

Централизация last_trade_info через TradeInfoManager

Цель: Исключить race conditions при доступе к информации о сделках.

Статус: ✅ Создан класс TradeInfoManager в trade_engine.py с методами add_trade, get_trade, update_trade и remove_trade. Все обращения к информации о сделках заменены вызовами через trade_manager.

Адаптация интервалов polling (DRY_RUN vs REAL_RUN)

Цель: Снизить нагрузку и шум в логах при тестировании.

Статус:

В telegram_handler.py: задержка опроса изменена на time.sleep(60 if DRY_RUN else 3).

В ip_monitor.py: интервал проверки IP выставлен на check_interval = 120 if DRY_RUN else 30 \* 60.

Дополнительно: В engine_controller.py добавлены временные фильтры для логов «Checking {symbol}» и «Balance for cycle» (не чаще 5 минут).

Priority 1 — Расширение логики входа и сопровождения ✅
♻️ Smart Re-entry Logic

Цель: Внедрение повторного входа по той же паре при получении повторного сильного сигнала (с использованием cooldown и score).

Статус: ✅ Реализовано в strategy.py (функция should_enter_trade) и интегрировано в trade_engine.py. Логика учитывает:

Вход по re-entry, если с момента последнего входа или закрытия прошло менее 30 минут и новый score превышает порог (score > 4 или улучшение на 1.5+ по сравнению с предыдущим входом).

Режим DRY_RUN корректно логирует re-entry, хотя в тестовом запуске их может не быть из-за отсутствия предыдущих ордеров.

🔄 Soft Exit / Partial TP Optimization

Цель: Реализовать адаптивный выход, когда TP1 почти достигнут, чтобы зафиксировать часть прибыли, закрывая часть позиции.

Статус: ✅ Реализовано. В trade_engine.py добавлена функция run_soft_exit, которая закрывает 50% позиции при достижении 90% от TP1 (настройки SOFT_EXIT_THRESHOLD и SOFT_EXIT_SHARE в config.py). В сделке имеется флаг soft_exit_hit для отслеживания.

📊 Auto TP/SL based on market regime

Цель: Автоматическая настройка TP1, TP2 и SL в зависимости от рыночного режима (flat vs trending).

Статус: ✅ Реализовано.

Добавлена функция get_market_regime в trade_engine.py, которая определяет режим (trend, flat или neutral) на основе ADX.

В функции enter_trade TP/SL корректируются:

В режиме "flat" (когда ADX < ADX_FLAT_THRESHOLD) применяется коэффициент FLAT_ADJUSTMENT (0.7).

В режиме "trend" (когда ADX > ADX_TREND_THRESHOLD) применяется коэффициент TREND_ADJUSTMENT (1.3).

Сообщения об адаптации TP/SL логируются (например, «Adjusted TP/SL for BTC/USDC: trend regime (x1.3 for TP2/SL)»).

В текущем config.py установлены следующие значения, которые обеспечивают работу функции:

python
Copy
AUTO_TP_SL_ENABLED = True
FLAT_ADJUSTMENT = 0.7
TREND_ADJUSTMENT = 1.3
ADX_TREND_THRESHOLD = 20
ADX_FLAT_THRESHOLD = 15
Если значения ADX для символов находятся в диапазоне 20–25, режим может определяться как "neutral" (без адаптации TP/SL). Обновлённые пороги (20/15) позволяют системе чаще применять адаптивное поведение.

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
