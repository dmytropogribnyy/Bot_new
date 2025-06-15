## ✅ Финальный TODO по текущему 1+1 боту (OptiFlow v2.9 + проблемы последнего запуска)

# ✅ Final TODO Summary — OptiFlow Core v2.9 (UltraClaude Final)

## 🔁 Ядро торговли

| Задача                                | Статус | Комментарий                                                             |
| ------------------------------------- | ------ | ----------------------------------------------------------------------- |
| `run_trading_cycle()` после закрытия  | ✅     | Вызывается после `safe_close_trade()` и timeout логики                  |
| Умный timeout > 1% PnL = не закрываем | ✅     | `monitor_active_position()` учитывает profit при тайм-ауте              |
| Реактивный re-entry                   | ✅     | `run_trading_cycle()` вызывается после закрытия позиции, если есть слот |
| Лимит входов в час                    | ✅     | `is_hourly_limit_reached()` (runtime_stats), лимит 6                    |

---

## ⚙️ Защитные механизмы

| Задача                     | Статус | Комментарий                                                   |
| -------------------------- | ------ | ------------------------------------------------------------- |
| Anti-reentry (5 мин)       | ✅     | Через `last_trade_times`, configurable в runtime_config       |
| Auto-pause при 3 SL подряд | ✅     | `pause_symbol(...)` + streak логика в `record_trade_result()` |
| Daily PnL stop (-5 USDC)   | ✅     | `get_today_pnl_from_csv()` + `pause_all_trading()` на 1 ч     |
| Drawdown-проверка          | ✅     | `check_drawdown_protection()` снижает риск или ставит паузу   |
| Capital Utilization        | ✅     | Лимит 80% через `check_capital_utilization(...)`              |
| Max Trades per Hour        | ✅     | Логика в `runtime_stats`, `update_trade_count()` + лимит      |

---

## 📊 TP/SL и логика выхода

| Задача                       | Статус | Комментарий                                                                      |
| ---------------------------- | ------ | -------------------------------------------------------------------------------- |
| TP1/TP2/SL по ATR            | ✅     | `calculate_tp_levels(...)`, учитывает `regime`, NaN-защиту                       |
| Stepwise TP (+0.10 → +0.40)  | ✅     | `step_profit_levels`, Telegram уведомления, `step_hits[]`                        |
| AutoProfit > 2.5% без TP     | ✅     | Закрытие при сильной прибыли без TP1, работает через `monitor_active_position()` |
| Timeout exit (если PnL < 1%) | ✅     | По истечении `max_hold_minutes` закрывает только если прибыль < 1%               |
| Extended TP                  | ✅     | TP переносится выше при сильном росте                                            |
| Partial Exit (40%)           | ✅     | Если рост остановился — скидывает часть позиции                                  |

---

## 🧠 Вход и стратегия

| Компонент                  | Статус | Комментарий                                                                       |
| -------------------------- | ------ | --------------------------------------------------------------------------------- |
| `should_enter_trade()`     | ✅     | Полная логика с `passes_1plus1`, фильтрами, TP/SL, cooldown, missed_signal логами |
| `process_symbol(...)`      | ✅     | Проверка notional, qty, margin, min_profit, pause check                           |
| `enter_trade(...)`         | ✅     | Лимиты, риск, qty, DRY_RUN, TP/SL-постановка, Telegram, логирование               |
| Anti-spread и min_notional | ✅     | Встроены в `process_symbol()` и risk_utils                                        |
| Priority-логика            | ✅     | `priority_pairs.json`, `priority_evaluator.py` актуальны                          |

---

## 💬 Telegram-интерфейс

| Команда                         | Статус | Комментарий                                       |
| ------------------------------- | ------ | ------------------------------------------------- |
| `/summary`                      | ✅     | Статистика по балансу, позициям, pnl              |
| `/runtime`                      | ✅     | Вывод текущего runtime_config.json                |
| `/logtail`                      | ✅     | Последние строки main.log                         |
| `/pnl_today`, `/pnl_week`       | ✅     | PnL отчёты из tp_performance.csv                  |
| `/riskstatus`                   | ✅     | Показывает paused symbols, streaks                |
| `/shutdown`, `/panic`           | ✅     | Управление состоянием бота                        |
| `/help`, `/backups`, `/restore` | ✅     | Все команды централизованы через COMMAND_REGISTRY |

---

## 🛠 Dev / Debug / Logs

| Компонент                                     | Статус | Комментарий                                         |
| --------------------------------------------- | ------ | --------------------------------------------------- |
| `ip_monitor.py`                               | ✅     | Telegram-уведомление при смене IP                   |
| `debug_monitoring_summary.json`               | ✅     | Поддерживается в debug_tools.py                     |
| `entry_logger.py`                             | ✅     | Логирует входы, min_profit, commission, exit_reason |
| `missed_signal_logger.py`                     | ✅     | Все отказы сохраняются с breakdown + reason         |
| `parameter_history.json`                      | ✅     | runtime_config обновления логируются                |
| `fetch_debug.json`, `valid_usdc_symbols.json` | ✅     | Обновляются в рамках fetch_data_multiframe, scanner |

---

## 🧹 Refactor & Очистка

| Блок                                                 | Статус | Комментарий                                              |
| ---------------------------------------------------- | ------ | -------------------------------------------------------- |
| Удаление score, HTF, aggressiveness, symbol_activity | ✅     | Удалены из стратегии и фильтров                          |
| Удаление ip_commands.py                              | ✅     | Telegram-команды централизованы в `telegram_commands.py` |
| Telegram fallback                                    | ✅     | Все send_telegram_message(...) защищены от крашей        |
| Очистка main.py                                      | ✅     | Импорты, fallback, init, сигналы — компактно и стабильно |

---

## ✅ Статус: Core Bot завершён

-   Все основные слои реализованы
-   Логика устойчива, Telegram-интерфейс стабильный
-   Risk/TP/SL слои прозрачны и согласованы
-   Готов к продакшену и масштабированию

Следующие шаги: запуск OptiScalp A/B, масштабирование на 3–9 ботов, WebSocket или grid/funding стратегии.

📌 Документ отражает итоговую реализацию OptiFlow Core v2.9 Final (UltraClaude).
Готов к запуску 24/7 в режиме real.

## Potential for future scalping bots to consider as an option

Да, помню. Мы ранее косвенно обсуждали WebSocket, когда затрагивали:

🔄 Задержки при получении fetch_ohlcv() через REST;

💬 Идею использовать WebSocket для онлайн-мониторинга или быстрой реакции на цену;

🧪 Но тогда решили отложить, потому что:

REST-подход был стабильным;

ты фокусировался на стратегии, TP, Telegram и защите;

WebSocket требовал дополнительной архитектуры (события, буферы, авто-реконнект).

🧠 Что бы WebSocket дал сейчас?
Возможность Нужно ли тебе? Комментарий
📈 Онлайн-триггер TP1/SL 🟡 Необязательно Сейчас TP-монитор работает с REST-интервалом (polling); WebSocket мог бы ускорить
⚡ Быстрый вход на пробой 🟢 Если пойдёшь в OptiScalp B/C Тогда WebSocket может дать преимущество
📊 Live-данные в Dashboard или UI ❌ Пока не требуется Telegram полностью покрывает текущее управление
🧯 Обновление позиции в реальном времени 🟡 Не приоритет Пока хватает логики мониторинга и safe_close_trade() по REST

🔍 Поддержка в Binance
Binance поддерживает WebSocket через:

wss://fstream.binance.com/ws — подписка на:

aggTrade (агрегированные сделки)

kline_1m, kline_5m (свечи)

markPriceUpdate, bookTicker, depth

📦 Можно использовать через websockets, aiohttp или ccxt.pro

🔧 Хочешь — можно внедрить:
websocket_monitor.py для TP/SL по markPriceUpdate;

или ws_price_listener.py для scalping trigger'ов.

✅ Резюме:
Ты не упустил ничего критически важного, WebSocket пока не нужен для текущей архитектуры.
Но если ты:

🟢 начнёшь скальпинг-ботов с интервалом 5–15 сек

🔁 хочешь реагировать не с интервалом 10 сек, а по tick'у
→ WebSocket становится осмысленным улучшением.

---
