# BinanceBot: Архитектурное описание

## 🏦 Общее

BinanceBot — автономный трейд-бот для спот/фьючерс Binance (USDC/USDT), построенный на CCXT.

🌐 Язык: Python 3.11+
🔌 API: Binance Futures USDC / USDT
🔒 Telegram integration: уведомления, команды, /goal, /summary, /stop

---

## 📊 Основные фичи

-   Адаптивное управление risk % / qty / SL
-   Многоуровневый фильтр (RSI, MACD, EMA, volume, ATR)
-   TP1/TP2 + fallback + trailing + soft-exit + auto-profit
-   Строгий control capital utilization
-   Постпоновляемая ротация пар со скорингом
-   Отчёты: daily/weekly/monthly, /summary, /goal
-   Telegram: все события, auto-notify

---

## 📂 Структура проекта

```
.
├── main.py                # Точка входа, запуск всего бота
├── core/                  # Ядро: торговля, сигналы, логика стратегии
│   ├── trade_engine.py         # enter_trade, monitor, record_trade_result, auto-profit
│   ├── strategy.py             # should_enter_trade, fetch_data_multiframe
│   ├── signal_utils.py         # get_signal_breakdown, passes_1plus1
│   ├── tp_utils.py             # TP/SL уровни, min_profit
│   ├── runtime_state.py        # streaks, pause_symbol, global_pause
│   ├── runtime_stats.py        # hourly trade limiter
│   ├── position_manager.py     # лимиты по позициям, capital utilization
│   ├── exchange_init.py        # инициализация API CCXT Binance
│   ├── binance_api.py          # fetch_ohlcv, create_order, validation
│   ├── entry_logger.py         # CSV лог входов
│   ├── component_tracker.py    # статистика по компонентам сигналов
│   ├── notifier.py             # Telegram: DRY_RUN, milestone, ошибки
│   ├── engine_controller.py    # run_trading_cycle: основная логика входов
│   ├── fail_stats_tracker.py   # риск-фактор по частоте отказов
│   ├── failure_logger.py        # log отказов по причинам
├── common/               # Конфигурации и Telegram
│   ├── config_loader.py        # config, .env, pairs, thresholds
│   ├── leverage_config.py      # карта плечей по символам
├── telegram/             # Обработчики Telegram
├── utils_core.py           # Кэш баланса, runtime_config, safe_call
├── utils_logging.py        # log(), log_to_file, log_to_telegram
├── pair_selector.py        # Выбор активных символов, фильтры, корреляции
├── continuous_scanner.py   # Поиск неиспользуемых но волатильных пар
├── tp_logger.py            # log_trade_result + CSV лог с Net PnL
├── tp_optimizer.py         # evaluate_best_config → TP адаптация
├── stats.py                # Отчёты, PnL-графики, /goal
├── order_utils.py          # calculate_order_quantity, limit reduceOnly
├── balance_watcher.py      # Обнаружение депозитов, алерты
├── priority_evaluator.py   # Система приоритетных пар
```

---

## ⚖️ Режимы торговли

-   `REAL_RUN` — полноценная торговля
-   `DRY_RUN=True` — симуляция входов, позиции не открываются
-   `SHORT_TERM_MODE=True` — ограничивает входы по часам UTC (2–8 skip слабые)

---

## 🚀 Запуск и масштабирование

-   Все агенты могут работать как:

    -   `main.py` (основной)
    -   `tp_sniper.py`, `hft_worker.py`, `adaptive_optimizer.py`

-   Запускаются параллельно через `tmux`, `pm2`, `supervisor`
-   Используют разные `runtime_config_X.json`, `chat_id`, `bot_name`

---

## 📊 Примеры логов и Telegram

-   Вход в позицию:

    ```
    🚀 ENTER WIFUSDC BUY qty=13.54 @ 0.1523
    ```

-   Закрытие:

    ```
    🌟 Step TP +4% → WIFUSDC partial close (4.00)
    🔵 Trade Closed [TP1 / TP1]
    ```

-   Статус:

    ```
    📊 *Goal Progress*
    Today's Trades: 7/9 (78%)
    Today's Profit: $3.42/$10.00
    ```

---

## 🔐 Защиты и fail-safe

-   SL-приоритет: SL исполняется до TP, если включено
-   3 SL подряд → auto pause symbol
-   Daily Net PnL < -\$5.0 → глобальная пауза
-   Drawdown > 15% → полная остановка
-   Стоп флаг через Telegram: /stop

---

## 🛠️ Модули будущих агентов (готова интеграция)

-   `tp_sniper.py` — снайпер входов рядом с TP
-   `hft_worker.py` — скальп на 15s–1m
-   `adaptive_optimizer.py` — автообновление TP / risk

---

## 📊 Состояние: Production-ready

-   Проверено >40 модулей
-   Полностью адаптированная архитектура под мульти-ботов
-   Telegram полностью интегрирован
-   Встроенные метрики, PnL, мониторинг

---
