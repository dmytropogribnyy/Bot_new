✅ Финальные выводы

1. TP/SL не выставляются при малом объеме
   Причина: safe_round_and_validate(...) возвращает None для долей qty < min_step_size → tp_total_qty = 0 → TP не ставится вообще.

Факт: trades SUI и ENA вошли без TP, SL появился позже.

Решение: fallback должен всегда ставить хотя бы один TP1, даже при qty < 0.002.

2. Зависшие позиции (WIF, XRP) мешают входам
   pending_exit = True остаётся в trade_manager, блокируя новые сделки.

Метод count_active_positions() считает такие позиции как активные.

Решение: после 5 неудачных попыток закрытия — сбрасывать позицию, убирать из учёта.

3. Ошибки слежения за состоянием позиций
   open_positions_count не уменьшается после fallback-закрытия.

trade_manager хранит записи с pending_exit, даже если фактически позиции нет.

Решение: при любом исходе close_real_trade — корректно обновлять счётчики и очищать pending.

4. Несогласованность конфигураций
   config_loader.py содержит TP1_PERCENT = 0.007, TP2_PERCENT = 0.014

А в runtime_config.json: "step_tp_levels": [0.0025, 0.004, 0.006]

Решение: убрать дублирующие значения из config_loader, брать всё из runtime_config.

🛠️ Чек-лист приоритетных фиксов (P1 – P3)
🔺 P1. TP/SL: исправить критические ошибки на малых qty
В place_take_profit_and_stop_loss_orders(...):

При qty < threshold — устанавливать только TP1 + SL

Защита: если tp_total_qty = 0, SL всё равно должен ставиться (FORCE_SL_ALWAYS = True)

Telegram log: "⚠️ Only SL set for {symbol}, TP too small"

python
Copy
Edit
if tp_total_qty == 0.0:
if runtime_config.get("FORCE_SL_ALWAYS", True): # Ставим хотя бы SL, даже если нет TP
sl_order = place_stop_loss_order(...)
if sl_order:
trade["sl_order_id"] = sl_order["id"]
trade["tp_sl_success"] = False
else: # критичный fail — log
🔺 P2. Close logic: устранить зависшие pending_exit позиции
В close_real_trade(...):

Если позиция не закрылась за 5 попыток:

Удалять её из trade_manager

Логировать exit_fail_reason

В конце: remove_trade(symbol) даже при pending_exit

python
Copy
Edit
if close_failed:
trade["pending_exit"] = True
trade["exit_fail_reason"] = reason
trade_manager.remove_trade(symbol)
🔺 P3. Синхронизация config_loader и runtime_config
В calculate_tp_levels(...):

Заменить:

python
Copy
Edit
from config_loader import TP1_PERCENT, TP2_PERCENT
на:

python
Copy
Edit
cfg = get_runtime_config()
tp_levels = cfg.get("step_tp_levels", [0.007, 0.014])
tp_shares = cfg.get("step_tp_sizes", [0.8, 0.2])
Убедиться, что все TP/SL уровни в расчётах берутся из runtime_config.

📦 Дополнительно (P4 – P6)
⚠️ P4. count_active_positions() игнорирует pending_exit
python
Copy
Edit
def count_active_positions():
return sum(1 for t in active_trades.values() if not t.get("pending_exit"))
⚠️ P5. Telegram уведомления о TP/SL fallback
Добавить логи типа:

python
Copy
Edit
send_telegram_message(f"⚠️ TP not placed for {symbol} – SL only fallback")
⚠️ P6. Улучшить record_trade_result(...):
Всегда логировать tp_fallback_used, tp_total_qty, tp_sl_success даже при 0.0

✅ Вывод: Финальный план фиксов
Приоритет Блок Действие
P1 TP/SL fallback Исправить safe_round, fallback на TP1-only + SL даже при qty < 0.002
P2 Close + state tracking Удалять зависшие pending_exit, пересчитывать open_positions
P3 TP-level config sync Убрать TP1_PERCENT из config_loader, использовать runtime_config
P4 Trade count logic count_active_positions → игнорировать pending_exit
P5 Telegram TP fallback Логировать случаи отсутствия TP
P6 TP log enhancement Всегда логировать tp_fallback_used, даже при убытке
