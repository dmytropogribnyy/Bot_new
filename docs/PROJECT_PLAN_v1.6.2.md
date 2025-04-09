🧠 BinanceBot — MASTER PLAN v1.6.2-dev (Апрель 2025)
📌 Статус проекта
✅ Актуальная версия: v1.6.2-dev

📂 Архитектура: модульная, покрытие DRY_RUN/REAL_RUN, Telegram, ML, HTF

🧭 Цель текущей итерации: чистка стратегии, адаптивность, надёжность

🔄 Объединены: ANALYSIS_v1.6.1.md + TODO_dev.md + предложения из чата

✅ Завершено
TP/SL, TP1/TP2, trailing stop, break-even

✅ Adaptive Score Threshold (баланс, winrate, частота сделок)

✅ Dynamic Volatility Filters (ATR/ADX/BB через relax_factor)

Smart Switching (лимит, winrate)

Aggressiveness System (EMA-сглаживание)

DRY_RUN защита: логика и файлы

Telegram команды, MarkdownV2 стандартизация

TP Logger: ATR/ADX/BB/HTF

HTF-автоанализ и автопереключение

ML TP Optimizer: анализ TP1/TP2, status.json

Auto config backup / Auto resume

Централизованное экранирование Telegram

Проверка entry_logger.py, tp_logger.py на DRY_RUN

MarkdownV2 → только в summary / reports

Score Heatmap отправляется раз в неделю

⏳ В процессе

1. 🔁 TP1/TP2 per symbol (TP_THRESHOLDS)
   Добавить блок TP_THRESHOLDS = {symbol: {tp1, tp2}} в config.py

Обновить trade_engine.py для подстановки этих значений

В tp_optimizer_ml.py заменить формат записи

Добавить Telegram лог при кастомных TP

2. 📉 PnL график
   Реализовать generate_pnl_graph() в stats.py

Построить matplotlib график по tp_performance.csv

Отправлять в Telegram (по пятницам или команде)

❌ Пока не начинали
❌ WebSocket feed

❌ Open Interest

❌ Soft Exit logic

❌ Auto-scaling позиции

❌ Re-entry logic

❌ REST API

🧠 Score System: статус
✅ Весовая модель + explain_score

✅ get_adaptive_min_score: аргументы trade_count, winrate активны

✅ DRY_RUN лог score и порога

✅ HTF Confirmed логируется и анализируется

🔐 DRY_RUN защита: подтверждено
entry_logger.py — ✅

tp_logger.py — ✅

score_evaluator.py — ✅

score_history.csv, tp_performance.csv — только в REAL_RUN

🗂️ Schedule (по времени)
⏰ Daily Report: 21:00

📈 Weekly Report: Воскресенье

📊 Monthly / Quarterly / YTD: по календарю

🤖 ML TP Optimizer: каждые 2 дня в 21:30

🧠 HTF Optimizer: воскресенье

🔥 Score Heatmap: пятница

🧪 Relax Factor Log: ежедневно (в отчёте)

✅ Чеклист задач
Adaptive Score Threshold активен

Фильтры вынесены в passes_filters и адаптируются

TP_THRESHOLDS реализован и используется

PnL график отправляется

trade*engine: все create*\* через safe_call

Проверка FULL REAL_RUN с логами пройдена
