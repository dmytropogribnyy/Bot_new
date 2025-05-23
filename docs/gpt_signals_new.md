GPT Signals — New (v1.6.2 Alignment)

1. Введение и цель
   В данном документе кратко описан новый подход к формированию сигналов в BinanceBot, основанный на:

Многокомпонентной системе score с весами

Правиле «1 основной + 1 подтверждающий» (unified check)

Адаптивных порогах входа и отказе от бинарной блокировки символов

Все детальные пояснения (файловая структура, risk-фактор, Telegram-команды, DRY_RUN) см. в UltraClaude_Updated.md, где описана финальная архитектура проекта (v1.6.2-final).

2. Основные новшества
   2.1. Суммарный score и breakdown
   Каждому индикатору (RSI, MACD, EMA_CROSS, Volume, HTF, PriceAction) присваивается вес.

При входном анализе DataFrame (через fetch_data_multiframe) мы сложим весовые баллы в calculate_score(), возвращая (score, breakdown).

Рекомендуемые веса (пример):

ini
Copy
RSI = +1.0
MACD = +1.2
EMA_CROSS = +1.2
Volume = +0.5
HTF = +0.5
PriceAction = +0.5
Итоговый score в диапазоне ~0..4.0.

breakdown — словарь вида: {"MACD":1.2, "Volume":0.5, ...}.

2.2. Unified signal check («1 основной + 1 подтверждающий»)
После расчёта score выполняется passes_unified_signal_check(score, breakdown).

Основные сигналы: ["MACD", "EMA_CROSS", "RSI"].

Подтверждающие: ["Volume", "HTF", "PriceAction"].

Сделка возможна только при наличии хотя бы 1 из первой группы и 1 из второй.

Если score < 2.5, то требуется дополнительное условие, например, EMA-кросс или MACD-EMA совместный сигнал.

2.3. Adaptive threshold и risk factor
get_adaptive_min_score() поднимает/опускает требуемый порог в зависимости от баланса (<300 USDC?), времени суток, волатильности.

Если score не достигает порога → отказ (причина "insufficient_score").

Graduated Risk: при накоплении ошибок по символу уменьшается только объём позиции (через risk_factor) — символ не блокируется целиком.

3. Ключевые модули и вызовы
   fetch_data_multiframe(symbol)

Единый способ загрузить 3m/5m/15m.

Считает rsi_5m, macd_5m, ema_3m, rel_volume_15m, price_action и т.д.

calculate_score(df) -> (score, breakdown) (в score_evaluator.py)

Суммирует веса: RSI, MACD, EMA_CROSS, Volume, HTF, PriceAction.

passes_unified_signal_check(score, breakdown)

Проверяет, есть ли основной + дополнительный индикаторы, а также EMA-поддержка при низком score.

get_adaptive_min_score(balance, ...)

Возвращает динамический порог входа.

should_enter_trade(symbol, df, ...) (в strategy.py)

Вызывает calculate_score(), сравнивает с min_required, затем passes_unified_signal_check().

В случае отказа — вызывает log_missed_signal(...).

4. Логирование и Telegram
   Missed signals: missed_signal_logger.py → пишет в data/missed_signals.json.

/missedlog выводит последние N записей (score, причина).

Компоненты: component_tracker.py → успешные входы учитывают, какие индикаторы дали вклад.

/signalstats обобщает статистику участия сигналов.

/lastscore <symbol> выводит недавний breakdown для символа (принят или отклонён).

Весы: при желании можно показать через /signalconfig (если реализован).

5. Подробные пояснения
   Все дополнительные детали по:

Graduated Risk: decay и fail_stats

HTF (подтверждение старшего ТФ)

DRY_RUN (логи только в консоль)

Ротация символов (continuous_scanner, priority_pairs)

описаны в UltraClaude_Updated.md.

Там же есть описание команд, legacy-модулей, cleanup и пр.

6. Заключение
   Таким образом, gpt_signals_new фиксирует основную идею новой системы сигналов:

Единый score из нескольких индикаторов.

Правило «1+1»: минимум один «Primary» + один «Secondary».

Dynamic threshold и небольшой «платёжеспособный» вход при низком risk_factor, вместо блокировки.

Поддержка логирования и Telegram-команд для прозрачности.

Это даёт более гибкую и надёжную стратегию, улучшает анализ, уменьшает фолс-позитивы и поддерживает стабильный скальпинг на USDC.

Смотрите UltraClaude_Updated.md для итоговой структуры v1.6.2-final.
