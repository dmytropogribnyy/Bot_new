Вот упорядоченный список файлов проекта BinanceBot, которые нужно проверить и рефакторить по новому плану — от ядра до вспомогательных компонентов:

✅ 1. Ядро стратегии и сигналов
core/strategy.py
🔧 Что сделать: удалить score, HTF, адаптивную логику, внедрить get_signal_breakdown() и passes_1plus1()

🔗 Зависимости: fetch_ohlcv, tp_utils, trade_engine, risk_utils, entry_logger, component_tracker

core/score_evaluator.py
🗑 Удалить полностью — логика score не используется

core/signal_feedback_loop.py
🗑 Если не участвует в новой логике TP/SL или фильтров — удалить

✅ 2. Вход в сделку и исполнение
core/trade_engine.py
🔧 Что сделать: убрать все проверки на score, risk_factor, HTF; сделать enter_trade() простым — принимает direction, price, qty, tp/sl

🔗 Вызывает: order_utils, tp_utils, entry_logger, notifier

core/tp_utils.py
🔧 Проверить расчёт TP1/TP2, trailing и break-even — оставить только фиксированную логику

❗ Убедиться, что не зависит от winrate или режима aggressiveness

core/risk_utils.py
🔧 Упростить до get_adaptive_risk_percent(balance), убрать aggressiveness

✅ 3. Логирование и анализ
core/entry_logger.py
🔧 Проверить: логирует ли entry_price, qty, breakdown, tp/sl, is_successful

🔗 Используется в trade_engine, strategy

core/component_tracker.py
🔧 Проверить: логирует ли breakdown по компонентам (EMA, RSI и т.д.), без score

❗ Логика is_successful → нужна для анализа winrate сигналов

core/missed_signal_logger.py
🔧 Убедиться, что фиксирует причины отказов (non_optimal_hours, low_balance, filtered, missing_1plus1)

🔗 Вызывается из strategy.py

✅ 4. Селектор и фильтры
pair_selector.py
🔧 Оставить отбор по ATR % и Volume, убрать зависимости от score, relax_factor, HTF_CONFIDENCE

❗ Проверить fallback-логику: при отсутствии пар использовать USDC_SYMBOLS

core/filter_adaptation.py, filter_optimizer.py
🔧 Упростить или удалить, если логика фильтров фиксированная (atr_threshold_percent, volume_threshold_usdc)

✅ 5. Telegram-интерфейс
telegram/telegram_commands.py
🔧 Удалить/обновить команды: /scoreboard, /signalstats, /heatmap

🔧 Обновить: /summary, /rejections, /failstats — показывают breakdown и TP

✅ Привести к @register_command, как в Refactor Plan

telegram/telegram_utils.py
🔧 Удалить дубли, упростить MarkdownV2, fallback

✅ 6. Утилиты и конфиг
utils_core.py
🔧 Удалить: адаптивные утилиты (get_adaptive_min_score, relax logic и др.)

🔧 Оставить: normalize_symbol, fetch_data_multiframe, get_cached_balance, is_optimal_trading_hour

common/config_loader.py
🔧 Удалить: USE_SCORE_LOGIC, HTF_CONFIDENCE, adaptive_filters_enabled

✅ Оставить: TRADING_HOURS_FILTER, SL_PERCENT, RISK_PERCENT, volume_threshold_usdc, atr_threshold_percent

✅ 7. Отладка и тесты
debug_tools.py, test_api.py, missed_tracker.py
🔧 Проверить, используют ли score — если да, переделать под breakdown или удалить

score_heatmap.py
🗑 Удалить — построен на score

✅ 8. Документация и инфраструктура
README.md, UltraClaude_Updated.md, Refactor_plan.md
✅ Уточнить, что теперь логика «1+1 сигнала»

✅ Удалить упоминания score, HTF, adaptive

## To mention

ChatGPT said:
✅ Да, мы полностью уходим от score и любых связанных с ним адаптивных механизмов — это основа всего текущего рефакторинга. Ни score, ни HTF_CONFIDENCE, ни get_adaptive_min_score больше не используются. Их место занимает простая бинарная логика: “1 основной + 1 дополнительный сигнал”.

❓ Что делать с filter_adaptation.py?
📌 Цель этого модуля:
Он динамически ослаблял фильтры (например, rsi_threshold, rel_volume_threshold) в “тихие” периоды рынка — через relax_factor.

✅ Лучшее решение: Удалить filter_adaptation.py полностью, если:
Ты перешёл на статичные фильтры, как в get_runtime_config():

json
Copy
Edit
{
"rsi_threshold": 50,
"rel_volume_threshold": 0.5,
"atr_threshold_percent": 0.005
}
Весь код теперь проверяет напрямую эти значения, без relax_boost или adapt_threshold(...)

В strategy.py нет вызовов get_relax_boost(...) или get_filter_adaptation(...)

✅ Тогда filter_adaptation.py — больше не нужен.

🟡 Альтернатива: оставить, но в замороженном виде
Если ты хочешь оставить структуру на будущее, то:

Убери всё, что меняет пороги динамически

Сделай заглушку:

python
Copy
Edit
def get_relax_boost(symbol: str) -> float:
return 1.0
🟢 Резюме:
Сценарий Рекомендация
Используешь только статичные пороги ❌ Удалить модуль
Хочешь оставить fallback на будущее 🟡 Заглушка: return 1.0
Всё ещё есть вызовы relax-функций ⚠️ Удалить их или заменить

🔚 Итог: да, мы официально и последовательно отказались от score, и всё, что с ним связано — либо уже удалено, либо в процессе. filter_adaptation.py входит в это число.
