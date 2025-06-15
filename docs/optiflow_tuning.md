## 🤖 OptiFlow System — Финальный Детальный План (v2.9+)

Это главный документ по запуску, улучшению и масштабированию OptiFlow Bot System. Основан на твоей стабильной логике 1+1, покрывает всё: от фильтров и TP-логики до автозащиты, Telegram, рекавери, рестарта и масштабирования на 9+ ботов.

---

## 🧱 Этап 0 — OptiScalp A (бот 1.1 → v2.9 Final)

**Статус:** готов на 90%, требует внедрения последних улучшений и проверки логов

### Что доработать:

-   [x] Полнейшее логирование фильтрации и сигналов
-   [x] Проверка passes_1plus1, добавить DEBUG-логи
-   [x] Telegram: вход, TP1, TP2, SL, AutoProfit, Timeout, Shutdown
-   [x] Spread + Notional фильтры (0.4% / \$50)
-   [x] AutoProfit при +3%, Stepwise TP, MaxHold
-   [x] Blacklist: 3 SL → 120 мин пауза
-   [x] Reactive вход сразу после выхода

📈 Цель: стабильный бот с \$15–25/день при \$300–500 депозите

---

## 🪜 Этап 1 — Запуск OptiScalp A / B / C

### ✅ OptiScalp_A (умеренный)

-   Пары: BTC, ETH, ADA
-   TP1: 0.003, SL: 0.006, timeout = 60 мин
-   Макс 2 позиции, интервал: 20 сек
-   Stepwise TP: +\$0.10, +\$0.20, +\$0.30, +\$0.40 (20/20/30/30%)

### ⏩ OptiScalp_B (через 2–3 дня)

-   Пары: SOL, DOGE, LTC
-   TP1: 0.0025, SL: 0.005, интервал: 15 сек
-   Цель: \$20–30/день

### 🔥 OptiScalp_C (через 3–5 дней)

-   Пары: XRP, AVAX, MATIC
-   TP1: 0.002, SL: 0.004, интервал: 10 сек
-   До 3 одновременных сделок, высокая частота
-   Цель: \$30–40/день

📌 Все трое = ядро HFT-сегмента

---

## 🧩 Этап 2 — Масштабирование до 6–9 ботов

-   OptiScalp A/B/C (3)
-   Ещё 2–3 скальп-бота (свои пары)
-   2–3 микросвинг-бота (TP2-only, hold_time до 4ч)

📊 Цель: \$90–150+ в день при депозите \$600–700 на каждого

---

## 🎯 Внедрённые тюнинги и логика выхода

### ✅ Stepwise TP

```python
step_profit_levels = [0.10, 0.20, 0.30, 0.40]
step_profit_shares = [0.2, 0.2, 0.3, 0.3]
```

→ Частичное закрытие при достижении уровня прибыли

### ✅ AutoProfit fallback

```python
if not tp1_hit and pnl >= 3.0:
    safe_close_trade(..., reason="auto_profit")
```

→ Закрытие при сильном росте без TP1

### ✅ Timeout exit logic

```python
if held_minutes >= 60 and pnl < 1.0:
    safe_close_trade(..., reason="timeout")
```

→ Не срезает рост, но завершает болото

### ✅ Reactive вход

```python
if get_open_positions_count() < max:
    run_trading_cycle()
```

→ Новая сделка после завершения предыдущей

### ✅ Spread/Notional защита

```python
spread_threshold_percent = 0.4
min_trade_notional = 50
```

### ✅ Blacklist

```python
if SL_count ≥ 3 → pause symbol 120 мин
```

---

## 🛡 Safety Layer для всех ботов

```python
volume_filter = median_volume * 1.2
atr_filter = median_atr * 0.9
min_pause_between_trades = 300
max_trades_per_hour = 6
```

→ Не допускает флуда, защищает депозит, пропускает только нормальные сигналы

---

## 🧠 Runtime-защита и устойчивость

### ✅ Обработка падений

```python
try:
    run_runtime_loop()
except Exception as e:
    log(...); send_telegram_message(...); raise
```

### ✅ Telegram fallback

-   Отправка ошибок и shutdown-сообщений
-   `🛑 Bot shutting down...` даже при Ctrl+C

### ✅ Хранение состояния

-   active_trades.json
-   tp_performance.csv
-   debug_monitoring_summary.json

### ✅ Автозапуск через:

-   `pm2`, `supervisor`, `systemd`, `screen + restart.sh`

---

## 🗂 Telegram-интерфейс (финальный)

-   `/open` — позиции с расчётом TP1/TP2
-   `/summary` — баланс, риск, открытые позиции
-   `/failstats`, `/blockers`, `/runtime`, `/filters`
-   `/log`, `/dailycsv`, `/signalstats`, `/near`, `/topmissed`
-   `/shutdown` — завершение с логом
-   Все команды через `@register_command`, категории в `/help`

---

## ✅ Статус проекта

| Компонент              | Статус |
| ---------------------- | ------ |
| Core логика входов     | ✅     |
| TP1 / TP2 / SL         | ✅     |
| Telegram логика        | ✅     |
| Stepwise + AutoProfit  | ✅     |
| Timeout и Hold         | ✅     |
| Blacklist, Notional    | ✅     |
| Reactive вход          | ✅     |
| Signal filters (1+1)   | ✅     |
| Debug logs по символам | ✅     |
| Crash-recovery         | ✅     |

---

📌 Этот документ объединяет всё, что мы внедрили и планируем использовать как основу мультибот-системы.

Хочешь — подготовлю `runtime_config_optiscalpA.json` и `bot_launcher.sh` под 3–9 параллельных ботов.
