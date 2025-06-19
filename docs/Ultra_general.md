# 📘 OptiFlow Core v3.1 – Финальный Fix Audit + Архитектура + Стратегия

Финальный документ объединяет всё: цели, структуру, реализацию, фиксы, стратегию и подтверждённый статус всех компонентов **OptiFlow Core** (v3.1, Июнь 2025).

---

## 🚀 Общая стратегия и цели

### 📈 Цель стратегии:

Создать стабильный и масштабируемый бот, который при депозите \$225–250 даёт \$3–5/час прибыли, с возможностью масштабирования через параллельные runtime-конфиги.

### 🔧 Основные фичи:

-   Stepwise TP1/TP2/TP3 (адаптивные уровни, runtime-driven)
-   SL на основе ATR + trailing + break-even
-   Сильные сигналы через MACD/EMA/RSI/volume фильтры
-   Автооптимизация TP уровней через TP-хиты
-   Telegram-интерфейс: команды, логи, уведомления TP/SL
-   ENV-архитектура с запуском нескольких ботов
-   Система защит: anti-reentry, SL-streak pause, capital utilization limit, timeout exit

---

## 🧠 Архитектура и ключевые модули

| Модуль                         | Назначение                                                                   |
| ------------------------------ | ---------------------------------------------------------------------------- |
| `main.py`                      | Запуск, restore, Telegram init, runtime-config, логика init                  |
| `should_enter_trade(...)`      | Генерация сигнала, фильтры MACD/RSI/HTF, passes_1plus1, min_profit           |
| `enter_trade(...)`             | Вход в сделку, risk/qty расчёт, проверка лимитов, Telegram логика            |
| `monitor_active_position(...)` | TP-touch мониторинг, fallback, break-even SL, soft_exit, trailing_tp         |
| `record_trade_result(...)`     | Финальный лог, PnL, SL, trailing, Telegram отчёт, update TP logic            |
| `log_trade_result(...)`        | CSV лог с 18 полями, TP1/2 hits, result, net/abs profit                      |
| `entry_logger.py`              | Запись попыток входа с expected_profit, commission, TP-ценами                |
| `tp_logger.py`                 | CSV логика, today PnL, get_trade_stats()                                     |
| `tp_optimizer.py`              | Автоанализ TP1/TP2 хитов, изменение TP уровней в runtime_config.json         |
| `telegram_commands.py`         | Команды управления и статистики: /summary, /goal, /pnl_today, /runtime и др. |

---

## ✅ Подтверждённая реализация всех блоков

### 🔹 Блок 1: Сигналы и входы

-   `passes_1plus1(...)` — strict режим, min_primary = 2, min_secondary = 1
-   `min_macd_strength = 0.002`, `min_rsi_strength = 12.0`
-   Проверка HTF: не шортим против тренда (HTF < 1)
-   Учитывается `expected_profit`, min_profit_threshold (например, \$0.06)
-   Anti-reentry через `last_trade_times`
-   Daily SL streak → auto-pause на 15 мин при 3 убытках

### 🔹 Блок 2: TP/SL и логика выхода

-   Step TP: `[0.02, 0.04, 0.06]` + `[0.5, 0.3, 0.2]`
-   TP-touch monitor (если TP не fill'd → fallback через 5 сек)
-   Break-even SL при +1.0% или TP1-hit
-   Soft-exit через 10 мин, если прибыль ≥ \$0.10 (или ≥ 0, если allow_at_zero)
-   Timeout по `max_hold_minutes` = 45
-   minimum_step_profit_hit_required = true

### 🔹 Блок 3: Риск и ограничения

-   calculate_position_size(...) учитывает:

    -   SL, leverage, margin, max_notional, min_qty

-   Capital utilization limit ≤ 80%
-   Проверка `check_entry_allowed(...)` на max concurrent positions и hourly limit
-   runtime_config поддерживает `risk_multiplier`, `base_risk_pct`, `min_trade_qty`

### 🔹 Блок 4: Telegram и команды

-   `/summary`, `/pnl_today`, `/growth`, `/goal`, `/debugpanel`, `/riskstatus`, `/runtime` и др.
-   Все команды обновлены: используют TP_LOG_FILE, правильные поля (`Date`, `TP1 Hit`, `SL Hit`)
-   Уведомления по TP1-hit, TP-touch, fallback, soft-exit
-   fallback Telegram при ошибках в командах

### 🔹 Блок 5: TP-оптимизация и адаптация

-   `evaluate_best_config(...)` считает TP1/2/SL hits, winrate
-   при необходимости вызывает `_update_config_tp(...)`
-   Telegram-отчёт показывает старые/новые TP уровни, winrate

---

## 🛠 Фиксы внедрены (не требуют перепроверки)

-   `main.py` → удалён ручной CSV header, используется `ensure_log_exists()` ✅
-   `record_trade_result(...)` → добавлены exit_reason, TP-хиты, Telegram ✅
-   `log_trade_result(...)` → исправлена NaN защита, нет дубликатов, TP1/TP2/SL/commission ✅
-   `tp_logger.py` → 18 полей, правильный порядок, today_pnl работает ✅
-   `tp_optimizer.py` → использует TP_LOG_FILE, считает TP/SL/Net PnL ✅
-   `stats.py` → корректно считает daily/weekly PnL, использует Date ✅
-   `telegram_commands.py` → `/summary`, `/pnl_today`, `/goal` обновлены: `.sum()` по bool, TP_LOG_FILE ✅
-   `entry_logger.py` → логирует TP1 price, TP1 share из config, commission, expected_profit ✅
-   `missed_tracker.py` → исправлен `.append` → `.append()` с проверкой типа ✅

---

## 🔄 ToDo и потенциал для расширения (опционально)

| Блок                                   | Возможное улучшение                                                |
| -------------------------------------- | ------------------------------------------------------------------ |
| ENV-масштабирование                    | Добавить `--config`, `--data-dir` в `main.py` через argparse       |
| WebSocket мониторинг                   | Отслеживать mark price для ultra-fast TP-touch detection           |
| Трейлинг TP расширить                  | Добавить постепенное поднятие TP2, TP3 при росте momentum          |
| Прогноз времени удержания              | Оценка "живучести" сигнала по истории (avg hold)                   |
| Интеграция funding rate                | Добавить long/short bias по funding rate или CVD (futures only)    |
| Автоматический TP fallback             | Если TP2 не исполнен через N минут, закрыть по рынку долю          |
| Дополнительные Telegram отчёты         | /risktrend, /exitstats, /entrybreakdown                            |
| Расширенный `record_trade_result(...)` | Логировать режим (trend/flat), HTF, результат трейлинга, тип входа |

---

## 🔚 Текущий статус

Бот **полностью стабилен**, оптимизирован и протестирован:

-   Торгует до 12 пар одновременно
-   Полный Telegram-UI и fallback логика
-   Входы фильтруются по силе сигнала и min_profit
-   Выходы адаптивны: step TP, soft-exit, trailing
-   TP-оптимизация работает, TP_LOG актуален
-   ENV конфигурация масштабируема под мультиботы

📌 Цель: **\$3–5/час при \$225**, далее — параллельные запуски HFT/Scalp/TP-Sniper ботов.
