✅ Что нужно сделать сейчас:
🔁 1. Объединяем все идеи, доработки и TODO в новый TODO-файл
Будет называться, например:
📄 LIGHT_TODO_v1.6.3-next.md

🔥 Объединённый TODO (v1.6.3-next)
🔝 Priority 0 — Устойчивость и стабильность (стабилизирующий блок)
🔁 Внедрить safe_call_retry(func, tries=3, delay=1) — для API Binance, особенно критичных вызовов (fetch_ticker, place_order).

🔒 Централизовать доступ к last_trade_info через менеджер/обёртку — защита от race condition (Smart Switch и трейлинг).

⏱ Адаптировать polling-интервалы IP и Telegram в DRY_RUN — увеличить до 60–120 секунд.

🔝 Priority 1 — Расширение логики входа и сопровождения
♻️ Smart Re-entry Logic — повторный вход по той же паре при повторном сильном сигнале (через cooldown и score).

🔄 Soft Exit / Partial TP Optimization — идея адаптивного выхода, если TP1 почти достигнут.

📊 Auto TP/SL based on market regime (flat/trending) — переключение TP/SL по ADX или range.

🔝 Priority 2 — Улучшения стратегического ядра
🧠 Передача relax_factor в score_evaluator.py — адаптация scoring logic в зависимости от условий рынка.

⚖️ Улучшить calculate_score() — добавить веса на основе winrate по индикаторам (RSI, MACD и т.п.).

🔍 Анализ причин отказа сделок (score vs filters) — логировать причину отказа (фильтр, min_score и т.д.).

🔝 Priority 3 — UI, отладка, безопасность
🧾 Команда /errors — показать последние ошибки Binance API или логов.

🖼 Расширение /summary — включить breakdown последнего score.

🧠 Добавить вывод текущей агрессивности в каждый отчёт (/summary, /daily и т.д.).

📦 Maintenance / Housekeeping
🧹 Удалить устаревший LIGHT_TODO_v1.6.2.md после миграции

🗃 Обновить README.md и SUMMARY.md с учётом версии v1.6.3-dev

📁 Проверка и очистка data/ от неиспользуемых JSON/CSV, если остались
