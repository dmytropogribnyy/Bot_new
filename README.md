# BinanceBot (v1.7)

Торговый бот для Binance Futures USDC, ориентированный на:
✅ стабильность, ✅ адаптивность, ✅ минимизацию рисков, ✅ автономность.

---

## 📂 Структура проекта

BINANCEBOT/
├── core/
│ ├── aggressiveness_controller.py
│ ├── balance_watcher.py
│ ├── binance_api.py
│ ├── engine_controller.py
│ ├── entry_logger.py
│ ├── exchange_init.py
│ ├── risk_utils.py
│ ├── score_evaluator.py
│ ├── score_logger.py
│ ├── strategy.py
│ ├── symbol_processor.py
│ ├── tp_utils.py
│ ├── trade_engine.py
│ ├── volatility_controller.py
├── data/
│ ├── bot_state.json
│ ├── dry_entries.csv
│ ├── dynamic_symbols.json
│ ├── entry_log.csv
│ ├── last_ip.txt
│ ├── last_update.txt
│ ├── score_history.csv
│ ├── tp_performance.csv
├── docs/
│ ├── BinanceBot — Project Plan (v1.6.3, April 2025).md
│ ├── BinanceBot Developer Guide — v1.6.3.md
│ ├── BinanceBot TODO — v1.6.3 Roadmap (April 2025).md
│ ├── plan_optimization_updated.md
│ ├── PracticalGuideStrategyAndCode.md
│ ├── router_reboot_dry_run.md
│ ├── router_reboot_real_run.md
│ ├── Syntax & Markdown Guide.md
│ ├── to_fix_real_run_updated.md
├── telegram/
│ ├── telegram_commands.py
│ ├── telegram_handler.py
│ ├── telegram_ip_commands.py
│ ├── telegram_utils.py
├── .env
├── .env.example
├── config.py
├── debug_log.txt
├── htf_optimizer.py
├── ip_monitor.py
├── main.py
├── pair_selector.py
├── push_log.txt
├── push_to_github.bat
├── pyproject.toml
├── README.md
├── requirements.txt
├── score_heatmap.py
├── start_bot.bat
├── stats.py
├── telegram_log.txt
├── test_api.py
├── tp_logger.py
├── tp_optimizer.py
├── tp_optimizer_ml.py
├── update_from_github.bat
├── utils_core.py
├── utils_logging.py

---

## ⚙️ Ключевые возможности

- **Testnet/Real переключение:** безопасная торговля в тестовой среде.
- **Адаптивный Risk-менеджмент:** процент риска на сделку зависит от баланса.
- **Динамический расчет TP/SL:** основан на ATR текущего символа.
- **Smart Entry / Smart Exit:** двухуровневый выход TP1/TP2 + break-even + trailing stop.
- **Поддержка нескольких пар:** ротация активных пар каждые 60 минут.
- **Telegram-интеграция:** команды управления ботом через `/status`, `/stop`, `/panic`, `/summary`, `/ipstatus` и др.
- **Защита депозита:** автоматическое отключение торговли при аномальной просадке.
- **Безопасная остановка:** бот корректно дожидается закрытия всех позиций.
- **Расширенные логи:** сделок, ошибок, IP изменений, системы ротации пар.
- **DRY_RUN режим:** режим симуляции для тестирования новых настроек без реальной торговли.

---

## 📈 Используемые индикаторы

- **MACD** — подтверждение тренда.
- **EMA** — трендовая фильтрация.
- **ATR** — расчет волатильности для динамических TP/SL.
- **ADX** — фильтрация слабых трендов.
- **Bollinger Bands Width** — фильтрация флэта.
- **(Дополнительно) RSI, Stochastic — в разработке.**

---

## 🛡 Безопасность и контроль

- Полный контроль ключей через `.env`.
- Переключение между Testnet/Real через `USE_TESTNET` в `config.py`.
- Автоматическая обработка ошибок Binance API и safe retries.
- Проверка состояния интернет-соединения и смены внешнего IP.
- Автоматическая приостановка торговли при критических ошибках.

---

## 🚀 Быстрый старт

1. Установить зависимости:
   ```bash
   pip install -r requirements.txt
   ```

````

2. Настроить файл `.env`:
   ```env
   API_KEY=your_key
   API_SECRET=your_secret
   ```
3. Проверить флаг тестового режима:
   ```python
   USE_TESTNET = True  # Для тестирования
   ```
4. Запустить бота:
   ```bash
   python main.py
   ```

---

## 📚 Документация проекта

- `docs/Master_Plan.md` — Полный стратегический план развития проекта.
- `docs/Master_Plan_implement_checklist.md` — Чек-лист внедрения на 14 дней.
- `docs/Mini_Hints.md` — Шпаргалка ежедневных проверок.
- `docs/plan_optimization_updated.md` — Архив рекомендаций.
- `docs/PracticalGuideStrategyAndCode.md` — Практическое руководство по стратегиям.

---

## 🛠 В разработке

- Расширение поддержки индикаторов (RSI, Stochastic).
- Автоматизация оптимизации TP/SL на основе Machine Learning.
- Поддержка мультибирж (Bybit, OKX).
- Расширенная аналитика: slippage, hold-time, PnL-графики.

---

# 🔥 BinanceBot v1.7 — Ваш надёжный помощник в мире фьючерсной торговли.
````
