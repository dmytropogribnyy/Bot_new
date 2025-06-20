# 📘 OptiFlow Core v3.3 – Финальный Fix Audit + Архитектура + Стратегия

Финальный документ объединяет всё: цели, структуру, реализацию, фиксы, стратегию и подтверждённый статус всех компонентов **OptiFlow Core** (v3.3, Июнь 2025).

---

## 🚀 Общая стратегия и цели

### 📈 Цель стратегии:

Создать стабильный и масштабируемый бот, который при депозите $225–250 даёт $3–5/час прибыли, с возможностью масштабирования через параллельные runtime-конфиги.

### 🔧 Основные фичи:

-   Stepwise TP1/TP2/TP3 (адаптивные уровни, runtime-driven)
-   SL на основе ATR + trailing + break-even
-   Сильные сигналы через MACD/EMA/RSI/volume фильтры
-   Signal Score логика с логированием, анализом и Telegram уведомлениями
-   Автооптимизация TP уровней через TP-хиты
-   Telegram-интерфейс: команды, логи, уведомления TP/SL
-   ENV-архитектура с запуском нескольких ботов
-   Система защит: anti-reentry, SL-streak pause, capital utilization limit, timeout exit

---

## 🧠 Архитектура и ключевые модули

| Модуль                         | Назначение                                                                   |
| ------------------------------ | ---------------------------------------------------------------------------- |
| `main.py`                      | Запуск, restore, Telegram init, runtime-config, логика init                  |
| `should_enter_trade(...)`      | Генерация сигнала, фильтры MACD/RSI/HTF, signal_score, min_profit            |
| `enter_trade(...)`             | Вход в сделку, risk/qty расчёт, проверка лимитов, Telegram логика            |
| `monitor_active_position(...)` | TP-touch мониторинг, fallback, break-even SL, soft_exit, trailing_tp         |
| `record_trade_result(...)`     | Финальный лог, PnL, SL, trailing, Telegram отчёт, update TP logic            |
| `log_trade_result(...)`        | CSV лог с 19 полями, TP1/2 hits, result, net/abs profit, signal_score        |
| `entry_logger.py`              | Запись попыток входа с expected_profit, commission, TP-ценами, score         |
| `tp_logger.py`                 | CSV логика, today PnL, get_trade_stats(), signal_score                       |
| `tp_optimizer.py`              | Автоанализ TP1/TP2 хитов, изменение TP уровней в runtime_config.json         |
| `telegram_commands.py`         | Команды управления и статистики: /summary, /goal, /pnl_today, /runtime и др. |

---

## ✅ Подтверждённая реализация всех блоков

### 🔹 Блок 1: Сигналы и входы

-   `signal_score` на основе весов MACD/RSI/EMA
-   `passes_1plus1(...)` — strict режим, min_primary = 2, min_secondary = 1
-   Фильтры: `min_macd_strength = 0.002`, `min_rsi_strength = 12.0`
-   Проверка HTF: не шортим против тренда (HTF < 1)
-   `min_profit_threshold` и expected_profit фильтр
-   Anti-reentry, cooldown, SL streak auto-pause

### 🔹 Блок 2: TP/SL и логика выхода

-   Step TP: `[0.02, 0.04, 0.06]` + `[0.5, 0.3, 0.2]`
-   TP-touch мониторинг, fallback через 5 сек
-   Break-even SL при +1.0% или TP1-hit
-   Soft-exit через 10 мин, если прибыль ≥ $0.10 (или ≥ 0 при allow_at_zero)
-   Timeout по `max_hold_minutes` = 45

### 🔹 Блок 3: Риск и ограничения

-   calculate_position_size(...):

    -   учитывает SL, leverage, margin, capital utilization
    -   авто-редукция (`auto_reduce_entry_if_risk_exceeds = true`)
    -   `min_trade_qty`, `MIN_NOTIONAL_OPEN` учтены

-   check_entry_allowed(...): max_concurrent_positions, capital used

-   runtime_config: поддерживает все параметры в коде, включая step_tp, capital_pct, base_risk_pct

### 🔹 Блок 4: Telegram и команды

-   Полный UI: /summary, /pnl_today, /goal, /runtime, /riskstatus, /debugpanel и др.
-   Telegram-уведомления:
    -   TP1/TP2-hit, fallback, soft_exit, stop, invalid qty, missed signals with score > 0.85

### 🔹 Блок 5: TP-оптимизация и адаптация

-   evaluate_best_config(...) → подсчёт TP1/2/SL hits, auto-update config
-   Telegram отчёт по TP-оптимизации: старая/новая конфигурация
-   tp_logger → 19 полей, включая signal_score, TP1/2/SL, result, PnL, ATR

---

## 🔧 Последние фиксы OptiFlow v3.3

-   Qty rounding через step_size, min_trade_qty защита
-   Авто-редукция позиции при превышении капитала
-   Полное покрытие логами: log_entry, record_trade_result, log_missed_signal
-   `signal_score` логируется везде, включая Telegram
-   Исключены ошибки filled_qty=0, TP не ставится, SL пропускается
-   Улучшена фильтрация сигналов, qty_blocked и low_volume обрабатываются прозрачно

---

## 🔚 Текущий статус: OptiFlow Core v3.3 ✅

Бот **полностью стабилен**, оптимизирован и завершён:

-   Все сделки проходят полный сигнал → вход → TP/SL → лог цепочку
-   Защиты работают: min_qty, capital limit, fallback, TP-touch, SL streak pause
-   Telegram покрывает все стадии: сигнал, вход, выход, missed, мониторинг
-   TP-оптимизация, мониторинг и логика PnL работают
-   Архитектура готова для масштабирования (мультиботы, TradingView, funding rate и т.д.)
