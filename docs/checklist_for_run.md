✅ Чеклист после каждого нового запуска бота:
📂 1. main.log — основной журнал
Проверяй:

Был ли прогон: NEW BOT RUN - ...

Сколько пар отобрано: Selected N active symbols: [...]

Есть ли сообщения score=<...> и Re-entry triggered или ✅ BUY/SELL

Ищешь:

хоть одно сообщение о входе

либо причину: no 1+1 signals, score too low, cooldown

📄 2. entry_log.csv — отказы по входу
Файл создаётся автоматически, если ты уже добавил log_rejected_entry(...).

Проверяй:

Появился ли файл data/entry_log.csv

Есть ли строки вида:

css
Copy
Edit
timestamp,symbol,score,reasons,components
2025-05-29T19:43:17,BTC/USDC:USDC,1.7,insufficient_profit,MACD:1.2;PriceAction:0.5
📌 Если файл пуст или не создаётся — значит входы даже не доходят до расчёта.

📄 3. debug_monitoring_summary.json — диагностика отбора
Проверяй:

"passed": ... — сколько пар прошло

"filtered": ... — сколько отфильтровано

"near_signals": [...] — если есть пары с хорошим score, но отказ по другим причинам

"missed_analysis.top_reasons" — что чаще всего мешает (например, low_volatility, low_volume)

📄 4. component_tracker_log.json — что давали компоненты
Проверяй:

Есть ли новые пары с successful=False

Если score > 0, а компонент успешный, но вход не происходит → смотри entry_log.csv почему

📄 5. data/tp_performance.csv — реальные сделки
Если будет хоть 1 вход, здесь появится строка с результатом.

💾 Структура твоей папки data/ выглядит ОК:
Категория Файлы Чекать после запуска?
⚙️ Runtime & config runtime_config.json, filter_adaptation.json Нет, только если ты менял настройки
📈 Score & signal logs component_tracker_log.json, debug_monitoring_summary.json, missed_opportunities.json ✅ Да
📉 TP анализ tp_performance.csv, missed_signals.json ✅ Да (если сделки были)
📊 Лог отказов entry_log.csv ✅ ОБЯЗАТЕЛЬНО
📦 Символы dynamic_symbols.json, valid_usdc_symbols.json ✅ При отборе
🧠 Приоритеты priority_pairs.json Можно, если надо

🟢 Резюме: После каждого рана открывай 3 файла:
main.log

entry_log.csv

debug_monitoring_summary.json

🟨 И по ситуации — component_tracker_log.json или tp_performance.csv.

Хочешь — скину этот чеклист в текстовый .md файл, чтобы был под рукой.

## Checks from o1 pro:

Ниже короткие и конкретные выводы и шаги, чтобы бот наконец начал открывать сделки:

1. Проверить, что entry_log.csv реально создаётся и наполняется
   Убедиться, что в файле should_enter_trade(...) есть импорт:

python
Copy
from utils_core import log_rejected_entry
Убедиться, что в каждом месте return None, failure_reasons вызывается:

python
Copy
log_rejected_entry(symbol, score_or_0, failure_reasons, breakdown_or_empty_dict)
Запустить бота заново и проверить в папке data/, появился ли файл entry_log.csv.

Если файла нет — значит либо импорт не сработал, либо в коде нет вызова.

Если файл пустой или не наполняется — тоже признак, что что-то не вызывается.

Без лога отказов трудно понять, на каком шаге сделка отваливается.

2. Временно отключить жёсткие проверки, чтобы протестировать вход
   В runtime_config.json поставить:

json
Copy
"USE_MULTITF_LOGIC": false
Так фильтрация станет менее строгой (проверяется только rsi_15m, atr_15m).

По желанию, снять требования в passes_unified_signal_check() — например, комментировать проверку if score < 2.5 and breakdown.get("EMA_CROSS", 0) <= 0: return False, чтобы смягчить порог.

Снизить rsi_threshold ещё сильнее (например, 25) и уменьшить rel_volume_threshold (например, 0.2).

Запустить бот. Если после этого появятся хотя бы несколько сделок (или хотя бы записи «insufficient_profit»/«signal_combo_fail» в entry_log.csv), значит дело было в слишком жёстких фильтрах.

3. Добавить Telegram-команду /rejections (рекомендация)
   Чтобы быстро увидеть причины отказа, не глядя в файл entry_log.csv. В telegram_commands.py:

python
Copy
@register_command("/rejections")
@handle_errors
def cmd_rejections(message, state=None, stop_event=None):
import csv
import os

    path = "data/entry_log.csv"
    if not os.path.exists(path):
        send_telegram_message("No entry_log.csv found. No rejections logged yet.")
        return

    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    if not rows:
        send_telegram_message("No rejections found.")
        return

    # последние 10 (сортировка по timestamp)
    rows = sorted(rows, key=lambda x: x["timestamp"], reverse=True)[:10]
    msg = "⚠️ *Recent Rejections*\n\n"
    for r in rows:
        msg += (
            f"{r['timestamp'][:19]} | {r['symbol']} | score={r['score']}\n"
            f"reasons: {r['reasons']}\n\n"
        )
    send_telegram_message(msg, parse_mode="MarkdownV2", force=True)

Потом в Телеграм: /rejections → сразу видим последние отклонения, например:

makefile
Copy
2025-05-29T19:46:03 | SUI/USDC:USDC | score=1.30
reasons: insufficient_profit
Это моментально покажет, какая именно причина (RR слишком низкий, min_profit не пройден, etc.).

4. Уменьшить min_net_profit и ослабить фильтры
   В utils_core.py (или где у вас get_min_net_profit) вернуть более маленькое значение. Например:

python
Copy
def get_min_net_profit(balance): # временно
return 0.0
Или хотя бы 0.1 USDC, чтобы сделки не отклонялись по причине “insufficient_profit”.

5. Проверить, какая действительно получается score и min_required
   В should_enter_trade(...) уже есть лог:

python
Copy
log(f"{symbol} ⚙️ HTF confidence: {htf_conf:.2f} → score: {raw_score:.2f} → {score:.2f}", level="DEBUG")
log(f"{symbol} DRY_RUN final Score={score:.2f}, threshold={min_required:.2f}")
Убедитесь, что в логе видно оба числа: score и min_required.
Если score=1.2, а min_required=2.0, сделки не откроются никогда.
Тогда:

Понизить get_adaptive_min_score(...), либо

Boost для score (т.е. "HTF_CONFIDENCE": 1.0 вместо 0.5).

6. Запустить бота и посмотреть результат
   Если появятся записи в entry_log.csv с причинами отказа — отлично, вы увидите конкретные блокеры.

Если пойдут реальные сделки (BUY/SELL в main.log) — значит всё сработало.

Итог:

Проверьте, что log_rejected_entry(...) реально вызывается.

Временно отключите сложные фильтры и проверки, чтобы протестировать вход.

Следите за entry_log.csv (или /rejections) и за сообщениями в main.log.

Таким образом, вы найдёте точную причину, почему сделки не открывались, и сможете отладить систему до рабочего состояния.

## ✅ Обновлённая подсказка (итоговая)

📋 Что сейчас временно включено (для диагностики):
Параметр / функция Временное значение Было до изменений
get_min_net_profit(balance) return 0.0 0.2 / 0.3 / 0.5 по балансу
base_threshold в get_adaptive_min_score(...) 1.6 / 2.0 / 2.3 2.3 / 2.8 / 3.3
return max(..., threshold) max(1.0, threshold) max(1.8, threshold)
"HTF_CONFIDENCE" 1.0 0.5
"score_relax_boost" 1.2 1.5
"USE_MULTITF_LOGIC" false true

🛠 Что потом вернуть обратно:
json
Copy
Edit
"HTF_CONFIDENCE": 0.5,
"score_relax_boost": 1.5,
"USE_MULTITF_LOGIC": true
А в коде:

вернуть base_threshold = 2.3 / 2.8 / 3.3

вернуть return max(1.8, threshold)

вернуть min_net_profit по балансу: 0.2 / 0.3 / 0.5

def get_min_net_profit(balance):
"""
Returns minimum acceptable profit for a trade based on account size.

    Args:
        balance: Account balance in USDC

    Returns:
        Minimum profit in USDC
    """
    if balance < 120:
        return 0.2  # $0.2 for micro accounts (0-119 USDC)
    elif balance < 300:
        return 0.3  # $0.3 for small accounts (120-299 USDC)
    else:
        return 0.5  # $0.5 for standard accounts (300+ USDC)

временно:
def get_min_net_profit(balance):
return 0.0
