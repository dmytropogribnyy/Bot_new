✅ utils_logging.py — предотвращение дублирования логов:
python
Copy
Edit
import logging

log = logging.getLogger("BinanceBot")
log.setLevel(logging.INFO)

## 🔒 Добавляем обработчик только если его ещё нет
if not log.hasHandlers():
    console_handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(module)s] %(message)s")
    console_handler.setFormatter(formatter)
    log.addHandler(console_handler)
✅ main.py — убираем дублирующий scheduler вызов select_active_symbols:
Найди и удали эту строку (если она есть):

python
Copy
Edit
scheduler.add_job(select_active_symbols, "interval", hours=4)
Оставь только:

python
Copy
Edit
threading.Thread(
    target=lambda: start_symbol_rotation(stop_event),
    daemon=True,
).start()
✅ pair_selector.py — убираем запуск потока track_missed_opportunities:
В конце select_active_symbols() замени:

python
Copy
Edit
threading.Thread(target=track_missed_opportunities, daemon=True).start()
на ничего — просто удали, потому что scheduler уже делает это раз в 30 минут.

После этих трёх правок:

✅ Логи будут выводиться один раз

✅ Функции не будут вызываться повторно

✅ Поведение станет стабильным и предсказуемым


# Сейчас у тебя нет прямой Telegram-команды, которая показывает потенциальную прибыль по открытым позициям, но её можно добавить.
Для начала — можно быстро реализовать простую команду, например /potential, которая будет:

🔹 Перебирать все открытые позиции
🔹 Считать потенциальную прибыль по TP1 и TP2
🔹 Отображать это в Telegram в виде:

yaml
Copy
Edit
💰 Potential Profit:
DOGE/USDC — TP1: +3.2 USDC | TP2: +7.9 USDC
...
Total TP1 Profit: ~5.3 USDC
Total TP2 Profit: ~12.1 USDC
Также можно указать % от депозита. Для расчётов будем использовать текущую qty, entry_price, TP1/TP2 уровни из стратегии, и расчёт PnL.

Хочешь — добавим?






You said:
да можно ксати просто в open добаить


ChatGPT said:
Отличная идея — логично просто расширить команду /open, чтобы она показывала потенциальный профит по каждой открытой позиции. Формат может быть такой:

vbnet
Copy
Edit
📊 Open Positions:
1. DOGE/USDC (SHORT)
Qty: 447.0 @ 0.20426
TP1: 0.20243 → +0.82 USDC
TP2: 0.20060 → +1.70 USDC
SL:  0.20705 → −1.24 USDC
👆 Это компактно, понятно и реально полезно.

Если согласен — могу сразу написать обновлённую реализацию блока для /open, чтобы ты вставил её в telegram_commands.py. Хочешь?






You said:
да


ChatGPT said:
Вот обновлённый фрагмент для команды /open, который показывает:

Направление сделки

Entry Price

TP1, TP2, SL

Потенциальный PnL по каждой цели

🔧 Вставь этот блок в telegram_commands.py внутрь handle_telegram_command под условие elif text == "/open":

python
Copy
Edit
elif text == "/open":
    from core.trade_engine import trade_manager
    from utils_price import calculate_pnl

    positions = trade_manager.get_open_positions()
    if not positions:
        send_telegram_message("📭 No open positions.")
        return

    msg = "*📊 Open Positions:*\n"
    for symbol, pos in positions.items():
        side = pos["side"].upper()
        qty = float(pos["qty"])
        entry = float(pos["entry_price"])
        tp1 = float(pos.get("tp1", 0))
        tp2 = float(pos.get("tp2", 0))
        sl = float(pos.get("stop_loss", 0))

        # Calculate PnL for each level
        tp1_pnl = calculate_pnl(entry, tp1, qty, side)
        tp2_pnl = calculate_pnl(entry, tp2, qty, side)
        sl_pnl = calculate_pnl(entry, sl, qty, side)

        msg += f"\n*{symbol}* ({side})\n"
        msg += f"`Qty:` {qty:.2f} @ `{entry}`\n"
        msg += f"TP1: {tp1:.5f} → *+{tp1_pnl:.2f} USDC*\n"
        msg += f"TP2: {tp2:.5f} → *+{tp2_pnl:.2f} USDC*\n"
        msg += f"SL:  {sl:.5f} → *-{abs(sl_pnl):.2f} USDC*\n"

    send_telegram_message(msg)
✅ Убедись, что у тебя есть функция calculate_pnl() в utils_price.py, например:

python
Copy
Edit
def calculate_pnl(entry, target, qty, side):
    if not entry or not target or not qty:
        return 0.0
    direction = 1 if side.lower() == "buy" else -1
    return round((target - entry) * qty * direction, 4)
Хочешь, чтобы я сам нашёл и обновил точный фрагмент в твоём telegram_commands.py?






You said:
да


ChatGPT said:
Да, бот успешно стартанул и уже открыл сделку по DOGE/USDC — это подтверждается логами:

css
Copy
Edit
[INFO] [Enter Trade] Opened SELL position for DOGE/USDC: qty=447.0, entry=0.20426
Также видно, что он корректно обработал лимит по 50% от баланса:

css
Copy
Edit
[WARNING] [Enter Trade] Skipping SUI/USDC - total position value would exceed 50% of balance
Это значит, что защита от перегруза депозита работает.

Теперь можно спокойно добавить поддержку Telegram-команды /open, которая будет выводить все активные позиции с расчётом потенциального профита (TP1/TP2) и убытка (SL), например в таком виде:

yaml
Copy
Edit
📈 Open Trades:
• DOGE/USDC — SELL
  Entry: 0.20426 | Qty: 447
  TP1: +4.0% | TP2: +8.0% | SL: -2.0%
  Est. Profit: +1.95 / +3.90 USDC | Risk: -1.15 USDC
Хочешь, добавлю эту команду в telegram_ip_commands.py сейчас?
