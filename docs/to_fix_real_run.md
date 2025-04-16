проанализировал все проблемы, которые возникли во время реального запуска (real run) твоего бота, и составлю чёткое и структурированное summary. Проблемы будут перечислены по порядку их обнаружения, с описанием причин и способов их решения. Это поможет тебе иметь полную картину и последовательно устранить все недочёты.

Summary: Проблемы при real run и способы их решения

1. Ошибка [SmartSwitch] Failed to calculate winrate: 'ResultType'
   Описание:

В логе появилась ошибка:
text

Copy
[2025-04-16 11:48:48] [WARNING] [SmartSwitch] Failed to calculate winrate: 'ResultType'
Бот пытался найти столбец ResultType в tp_performance.csv, но в файле используется столбец Result.
Причина:

В engine_controller.py в функции get_smart_switch_stats код ссылается на неправильное имя столбца (ResultType вместо Result).
Решение:

Измени строку в engine_controller.py:
python

Copy
recent = df[df["ResultType"] == "smart_switch"].tail(10)
на:
python

Copy
recent = df[df["Result"] == "smart_switch"].tail(10)
Перезапусти бота и проверь, исчезла ли ошибка. 2. Ошибка [ERROR] Trailing init fallback: index 14 is out of bounds for axis 0 with size 2
Описание:

При попытке рассчитать ATR для TIA/USDC возникла ошибка:
text

Copy
[2025-04-16 11:48:34] [INFO] [ERROR] Trailing init fallback: index 14 is out of bounds for axis 0 with size 2
Биржа вернула только 2 свечи вместо ожидаемых 15, что привело к сбою в расчёте ATR.
Причина:

В trade_engine.py в функции run_adaptive_trailing_stop не было проверки на достаточное количество свечей перед расчётом ATR:
python

Copy
ohlcv = safe_call_retry(exchange.fetch_ohlcv, symbol, timeframe="15m", limit=15, label=f"fetch_ohlcv {symbol}")
highs = [c[2] for c in ohlcv]
lows = [c[3] for c in ohlcv]
closes = [c[4] for c in ohlcv]
atr = max([h - low for h, low in zip(highs, lows)])
Решение:

Добавь проверку на количество свечей в trade_engine.py:
python

Copy
ohlcv = safe_call_retry(exchange.fetch_ohlcv, symbol, timeframe="15m", limit=15, label=f"fetch_ohlcv {symbol}")
if not ohlcv or len(ohlcv) < 14:
log(f"[ERROR] Insufficient data for trailing stop for {symbol}: {len(ohlcv)} candles", level="ERROR")
trailing_distance = entry_price \* 0.02 # Fallback
else:
highs = [c[2] for c in ohlcv]
lows = [c[3] for c in ohlcv]
closes = [c[4] for c in ohlcv]
atr = max([h - low for h, low in zip(highs, lows)])
Перезапусти бота и проверь, исчезла ли ошибка при расчёте ATR. 3. Ошибка [ERROR] create_break_even TIA/USDC failed: [<class 'decimal.ConversionSyntax'>]
Описание:

При попытке установить break-even ордер для TIA/USDC (и позже для TRUMP/USDC) возникала ошибка:
text

Copy
[2025-04-16 11:49:32] [ERROR] create_break_even TIA/USDC failed (attempt 1/3): [<class 'decimal.ConversionSyntax'>]
[2025-04-16 11:49:34] [ERROR] create_break_even TIA/USDC exhausted retries
Причина:

В trade_engine.py в функции run_break_even параметр stop_price передаётся в API Binance в некорректном формате (например, как numpy.float64 или Decimal), что вызывает ошибку decimal.ConversionSyntax.
Решение:

Измени run_break_even в trade_engine.py, чтобы stop_price явно приводился к float:
python

Copy
stop_price = float(round(entry_price, 4))
log(f"[DEBUG] Creating break-even for {symbol} with stop_price: {stop_price}", level="DEBUG")
safe_call_retry(
exchange.create_order,
symbol,
"STOP_MARKET",
"sell" if side == "buy" else "buy",
None,
params={"stopPrice": stop_price, "reduceOnly": True},
label=f"create_break_even {symbol}",
)
Перезапусти бота и проверь, исчезла ли ошибка при установке break-even ордеров. 4. Ошибка [ERROR] create_limit_order TP1 HBAR/USDC failed: binance {"code":-2019,"msg":"Margin is insufficient."}
Описание:

При попытке установить TP1 ордер для HBAR/USDC и KAITO/USDC возникла ошибка:
text

Copy
[2025-04-16 11:49:48] [ERROR] create_limit_order TP1 HBAR/USDC failed (attempt 1/3): binance {"code":-2019,"msg":"Margin is insufficient."}
[2025-04-16 11:50:09] [ERROR] create_limit_order TP1 KAITO/USDC exhausted retries
Причина:

На счёте недостаточно свободной маржи для размещения TP-ордеров:
Баланс: 120.07 USDC.
Открытые позиции: 1000BONK/USDC (notional ≈ 62.62 USDC) и TIA/USDC (notional ≈ 343.20 USDC).
Суммарный notional: 405.82 USDC, что превышает баланс, а маржинальная торговля требует дополнительной свободной маржи для ордеров.
Решение:

Проверь доступную маржу:
Используй команду /balance или API Binance, чтобы узнать свободную маржу.
Уменьши количество позиций:
Добавь проверку текущих позиций перед входом в новую сделку в symbol_processor.py:
python

Copy
positions = exchange.fetch_positions()
active_positions = sum(1 for pos in positions if float(pos.get("contracts", 0)) != 0)
if active_positions >= MAX_POSITIONS:
log(f"⏩ Skipping {symbol} — max open positions ({MAX_POSITIONS}) reached (current: {active_positions})", level="DEBUG")
return None
Закрой лишние позиции вручную:
Используй /panic YES для закрытия всех позиций, если маржа исчерпана.
Увеличь MAX_POSITIONS (опционально):
Если ты хочешь больше позиций, увеличь MAX_POSITIONS в config.py, но будь осторожен с маржой:
python

Copy
MAX_POSITIONS = 2 5. Проблема: /stop и /panic YES не закрывали позиции автоматически
Описание:

После команды /stop и /panic YES позиции (например, 1000BONK/USDC) не закрывались, и тебе пришлось закрывать их вручную через Binance:
text

Copy
[2025-04-16 11:50:39] [DEBUG] [telegram_utils] Message sent successfully: 🛑\ Stop\ command\ received\.
No\ open\ trades\.\ Bot\ will\ ...
Хотя позиция 1000BONK/USDC оставалась открытой.
Причина:

Функции handle_stop и handle_panic в telegram_commands.py некорректно определяли открытые позиции, используя устаревший кэш вместо актуальных данных с биржи.
Решение:

Обнови handle_stop и handle_panic в telegram_commands.py, чтобы они запрашивали позиции напрямую с биржи:
python

Copy
def handle_stop():
log("[Stop] Received stop command", level="INFO")
state = load_state()
state["stopping"] = True
save_state(state)
send_telegram_message("🛑 Stop command received.\nClosing all trades...", force=True)

    try:
        positions = exchange.fetch_positions()
        open_trades = [p for p in positions if float(p.get("contracts", 0)) != 0]
        if not open_trades:
            send_telegram_message("No open trades. Bot will stop shortly.", force=True)
        else:
            for trade in open_trades:
                symbol = trade["symbol"]
                log(f"[Stop] Closing position for {symbol}", level="INFO")
                close_real_trade(symbol)
                open_orders = exchange.fetch_open_orders(symbol)
                for order in open_orders:
                    exchange.cancel_order(order['id'], symbol)
                    log(f"[Stop] Cancelled order {order['id']} for {symbol}", level="INFO")
            send_telegram_message("✅ All trades closed. Bot will stop shortly.", force=True)
    except Exception as e:
        log(f"[Stop] Failed to close trades: {e}", level="ERROR")
        send_telegram_message(f"❌ Failed to close trades: {e}", force=True)

def handle_panic():
log("[Panic] Received panic command", level="INFO")
send_telegram_message("🚨 Panic command received.\nClosing all trades immediately...", force=True)

    try:
        positions = exchange.fetch_positions()
        open_trades = [p for p in positions if float(p.get("contracts", 0)) != 0]
        if not open_trades:
            send_telegram_message("No open trades to close.", force=True)
        else:
            for trade in open_trades:
                symbol = trade["symbol"]
                log(f"[Panic] Closing position for {symbol}", level="INFO")
                close_real_trade(symbol)
                open_orders = exchange.fetch_open_orders(symbol)
                for order in open_orders:
                    exchange.cancel_order(order['id'], symbol)
                    log(f"[Panic] Cancelled order {order['id']} for {symbol}", level="INFO")
            send_telegram_message("✅ All trades closed via panic.", force=True)
    except Exception as e:
        log(f"[Panic] Failed to close trades: {e}", level="ERROR")
        send_telegram_message(f"❌ Failed to close trades: {e}", force=True)

Перезапусти бота и протестируй команды /stop и /panic YES. 6. Проблема: Открылось больше 10 сделок, несмотря на ограничение MAX_POSITIONS
Описание:

В реальном запуске открылось больше 10 сделок, хотя в config.py было установлено ограничение MAX_POSITIONS = 10 (или 1).
Причина:

Ограничение MAX_POSITIONS применялось только к новым позициям, но не учитывало уже открытые позиции.
Открытые ордера (TP/SL) не учитывались в MAX_POSITIONS, что создавало путаницу.
Решение:

Исправь проверку в symbol_processor.py:
python

Copy
def should_enter_trade(symbol, exchange):
with open_positions_lock:
positions = exchange.fetch_positions()
active_positions = sum(1 for pos in positions if float(pos.get("contracts", 0)) != 0)
if active_positions >= MAX_POSITIONS:
log(f"⏩ Skipping {symbol} — max open positions ({MAX_POSITIONS}) reached (current: {active_positions})", level="DEBUG")
return None # Логика входа в сделку...
Добавь закрытие лишних позиций при запуске в main.py:
python

Copy
def main():
exchange = ccxt.binance({
"apiKey": API_KEY,
"secret": API_SECRET,
"enableRateLimit": True,
})
positions = exchange.fetch_positions()
active_positions = sum(1 for pos in positions if float(pos.get("contracts", 0)) != 0)
if active_positions > MAX_POSITIONS:
log(f"[Startup] Found {active_positions} positions, but MAX_POSITIONS is {MAX_POSITIONS}. Closing excess positions...", level="INFO")
for pos in positions:
if float(pos.get("contracts", 0)) != 0:
symbol = pos["symbol"]
close_real_trade(symbol)
active_positions -= 1
if active_positions <= MAX_POSITIONS:
break # Остальной код main()...
Ограничивай открытые ордера: В config.py добавь:
python

Copy
MAX_OPEN_ORDERS = 10
В trade_engine.py добавь проверку:
python

Copy
def place_tp_sl_orders(symbol, side, qty, entry_price):
open_orders = exchange.fetch_open_orders(symbol)
if len(open_orders) >= MAX_OPEN_ORDERS:
log(f"[TP/SL] Skipping TP/SL for {symbol} — max open orders ({MAX_OPEN_ORDERS}) reached", level="DEBUG")
return # Логика размещения TP/SL ордеров... 7. Проблема: tp_performance.csv не обновлялся
Описание:

Сделки (TIA/USDC, KAITO/USDC, HBAR/USDC) не записывались в tp_performance.csv, хотя файл содержал тестовую запись.
Причина:

Сделки закрывались вручную через Binance, и бот не фиксировал их закрытие.
Функция close_real_trade не вызывала log_trade_result для записи сделок.
Ошибка с путём (tp.performance.csv вместо tp_performance.csv) в EXPORT_PATH.
Решение:

Исправь путь в config.py:
python

Copy
from pathlib import Path

TIMEZONE = pytz.timezone("Europe/Bratislava")
LOG_FILE_PATH = str(Path("bots", "BinanceBot", "telegram_log.txt"))
EXPORT_PATH = str(Path("c:/Bots/BinanceBot/data/tp_performance.csv"))
TP_LOG_FILE = str(Path("c:/Bots/BinanceBot/data/tp_performance.csv"))

if not Path(TP_LOG_FILE).exists():
raise FileNotFoundError(f"TP_LOG_FILE not found at: {TP_LOG_FILE}")
else:
print(f"TP_LOG_FILE found at: {TP_LOG_FILE}")
Добавь вызов log_trade_result в close_real_trade: В trade_engine.py:
python

Copy
def close_real_trade(symbol):
try:
positions = exchange.fetch_positions()
position = [p for p in positions if p['symbol'] == symbol and float(p.get("contracts", 0)) != 0]
if position:
qty = abs(float(position[0]['contracts']))
side = "sell" if position[0]['side'] == "long" else "buy"
entry_price = float(position[0]['entryPrice'])
order = exchange.create_market_order(symbol, side, qty, params={"reduceOnly": True})
log(f"[Close Trade] Closed position for {symbol}: {side} {qty}", level="INFO")
exit_price = float(order['price']) if order['price'] else float(exchange.fetch_ticker(symbol)['last'])
pnl_percent = ((exit_price - entry_price) / entry_price _ 100) if side == "sell" else ((entry_price - exit_price) / entry_price _ 100)
duration = (datetime.utcnow() - datetime.utcfromtimestamp(position[0]['timestamp'] / 1000)).total_seconds() // 60
log_trade_result(
symbol=symbol,
direction=position[0]['side'].upper(),
entry_price=entry_price,
exit_price=exit_price,
qty=qty,
tp1_hit=False,
tp2_hit=False,
sl_hit=False,
pnl_percent=pnl_percent,
duration=duration,
htf_confirmed=False,
atr=0.0, adx=0.0, bb_width=0.0
)
open_orders = exchange.fetch_open_orders(symbol)
for order in open_orders:
exchange.cancel_order(order['id'], symbol)
log(f"[Close Trade] Cancelled order {order['id']} for {symbol}", level="INFO")
except Exception as e:
log(f"[Close Trade] Failed for {symbol}: {e}", level="ERROR")
raise 8. Следующие шаги
Применить все исправления:
Исправь ошибки в engine_controller.py, trade_engine.py, symbol_processor.py, main.py, telegram_commands.py и config.py, как указано выше.
Перезапусти бота:
Запусти бота:
text

Copy
cd c:\Bots\BinanceBot
python main.py
Протестировать:
Открой тестовую позицию и закрой её через /stop или /panic YES.
Убедись, что:
Ошибки исчезли.
Позиции закрываются автоматически.
Не открывается больше позиций, чем указано в MAX_POSITIONS.
Сделки записываются в tp_performance.csv.
Итог: Все проблемы при real run были связаны с некорректной логикой обработки позиций, ордеров, путей и записи сделок. Исправления выше должны устранить их. Примени всё и напиши, как всё прошло! 😊
