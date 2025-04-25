План оптимизации торгового бота на депозит 100–120 USDC (Обновленный)
Введение
Данный документ представляет собой обновленный план оптимизации торгового бота, рассчитанного на работу с депозитом 100–120 USDC с перспективой его увеличения. План основан на оригинальном документе, дополнен новыми рекомендациями, учитывающими текущие рыночные условия (25 апреля 2025 года), проблемы, выявленные в логах (telegram_log.txt), и необходимость перехода от тестового режима к реальной торговле.
Цель — устранить ошибки, повысить стабильность, прибыльность и адаптивность бота, сохранив все ключевые элементы оригинального плана, включая риск-менеджмент, выбор пар и обработку ошибок. План включает конкретные кодовые предложения для упрощения реализации.

Оглавление

Введение
Нужные файлы
Проблемы
Критические исправления
Риск-менеджмент
Оптимизация торговли
Выбор пар
Обработка ошибок
Долгосрочные улучшения
Тест-план
Заключение

Нужные файлы
Список файлов остается неизменным, но добавлены комментарии о необходимых доработках:

engine_controller.py — координация логики бота и ордеров. Добавить проверки на лимиты позиций.
volatility_controller.py — сканирование рынка и отбор пар. Интегрировать динамические фильтры на основе ATR.
stats.py — сбор и анализ статистики сделок. Добавить учет комиссий и метрики (винрейт, просадка).
utils_logging.py — настройка форматирования логов. Расширить логирование для сделок с ID и причинами закрытия.
trade_engine.py — обработка сигналов на вход/выход. Внедрить ATR для TP/SL.
tp_logger.py — запись результатов сделок (tp_performance.csv). Устранить дубли и добавить комиссии.
symbol_processor.py — обработка символов, расчет ордеров. Исправить ошибки маржи и проверки данных.
telegram_commands.py — команды управления ботом. Добавить мониторинг ошибок через оповещения.
config.py — параметры стратегии. Активировать адаптивные настройки риска и позиций.
main.py — точка входа, запуск основного цикла. Усилить обработку ошибок с try/except.

Проблемы
Оригинальные проблемы дополнены новыми, выявленными в логах:
Оригинальные проблемы:

Ошибки в логировании сделок (tp_performance.csv): дублирование записей.
Нарушение ограничений позиций (MAX_POSITIONS, MAX_OPEN_ORDERS).
Ошибки недостаточного обеспечения ордеров (MarginError).
Сбои break-even и SmartSwitch (ошибки конвертации Decimal/float).
Некорректная остановка через /stop и /panic.
Статический список пар без учета волатильности.
Ограниченный риск-менеджмент (фиксированная ставка).
Недостаточная аналитика результатов.
Отсутствие тест-плана.

Новые проблемы (из логов):

Ошибки обработки данных: "unsupported operand type(s) for \*=: 'float' and 'NoneType'" (например, для SOL/USDC).
Недостаточная маржа: "Margin is insufficient" (например, для SUI/USDC).
Превышение нотинала: "Notional exceeds max with leverage" (например, BTC/USDC).
Ошибки TP2 ордеров: "Order's notional must be no smaller than 5" (XRP/USDC).
Отсутствие учета комиссий в расчетах прибыли.

Критические исправления
В config.py

Адаптивный риск:
1% для баланса <100 USDC.
2% для 100–150 USDC.
3% для 150–300 USDC.
5% для >300 USDC.
Реализация: def get_adaptive_risk_percent(balance):
if balance < 100:
return 0.01 # 1%
elif balance < 150:
return 0.02 # 2%
elif balance < 300:
return 0.03 # 3%
else:
return 0.05 # 5%

def get_max_positions(balance):
if balance < 100:
return 1
elif balance < 150:
return 2
elif balance < 300:
return 3
else:
return 5

from utils_core import get_cached_balance
balance = get_cached_balance()
RISK_PERCENT = get_adaptive_risk_percent(balance)
MAX_POSITIONS = get_max_positions(balance)

MIN_NOTIONAL_OPEN и MIN_NOTIONAL_ORDER: Установить 20 USDC.
MAX_OPEN_ORDERS: Установить 3 на символ.
SYMBOLS_ACTIVE: Динамический отбор через pair_selector.py.
TP/SL параметры:
Восстановить: TP1_PERCENT = 0.007, TP2_PERCENT = 0.013, SL_PERCENT = 0.01.
Добавить ATR: SL = 1.5 _ ATR, TP1 = 1 _ ATR, TP2 = 2 \* ATR.
Реализация: MIN_NOTIONAL_OPEN = 20
MIN_NOTIONAL_ORDER = 20
TP1_PERCENT = 0.007
TP2_PERCENT = 0.013
SL_PERCENT = 0.01
TP1_SHARE = 0.7
TP2_SHARE = 0.3
MAX_OPEN_ORDERS = 3

В trade_engine.py

Проверка нотинала: Перед открытием позиции проверять MIN_NOTIONAL_OPEN.
Исправление Decimal/float: Привести все вычисления к float.
Split-profit: TP1_SHARE = 0.7, TP2_SHARE = 0.3.
Динамическая настройка TP/SL: Использовать ATR.
Реализация: from ta.volatility import AverageTrueRange
def calculate_tp_levels(entry_price: float, side: str, regime: str = None, score: float = 5, df=None):
atr = AverageTrueRange(df["high"], df["low"], df["close"], window=14).average_true_range().iloc[-1]
sl_pct = 1.5 _ atr / entry_price
tp1_pct = 1.0 _ atr / entry_price
tp2_pct = 2.0 _ atr / entry_price
if AUTO_TP_SL_ENABLED and regime:
if regime == "flat":
tp1_pct _= FLAT_ADJUSTMENT
tp2_pct _= FLAT_ADJUSTMENT
sl_pct _= FLAT_ADJUSTMENT
elif regime == "trend":
tp2_pct _= TREND_ADJUSTMENT
sl_pct _= TREND_ADJUSTMENT
if side.lower() == "buy":
tp1_price = entry_price _ (1 + tp1_pct)
tp2_price = entry_price _ (1 + tp2_pct) if tp2_pct else None
sl_price = entry_price _ (1 - sl_pct)
else:
tp1_price = entry_price _ (1 - tp1_pct)
tp2_price = entry_price _ (1 - tp2_pct) if tp2_pct else None
sl_price = entry_price _ (1 + sl_pct)
return (
round(tp1_price, 4), round(tp2_price, 4) if tp2_price else None,
round(sl_price, 4), TP1_SHARE, TP2_SHARE
)

SmartSwitch: Проверять состояние позиции через API перед закрытием.
safe_call_retry: Применять ко всем API-вызовам.

В tp_logger.py

Устранение дублей: Использовать уникальные ID сделок.
Комиссии: Добавить поле для комиссий (0.02% maker, 0.05% taker).
Реализация: def log*trade_result(symbol, direction, entry_price, exit_price, qty, tp1_hit, tp2_hit, sl_hit, pnl_percent, duration_minutes, htf_confirmed, atr, adx, bb_width, result_type="manual"):
commission = qty * entry_price * TAKER_FEE_RATE * 2 # Открытие и закрытие
net_pnl = ((exit_price - entry_price) / entry_price * 100) - (commission / (qty * entry_price) * 100)
if direction == "SELL":
net_pnl \*= -1
date_str = now_with_timezone().strftime("%Y-%m-%d %H:%M:%S")
trade_id = f"{symbol}*{date*str}*{result_type}" # Уникальный ID
if trade_id in logged_trades:
log(f"Skipping duplicate trade {trade_id}", level="DEBUG")
return
logged_trades.add(trade_id)
row = [
date_str, symbol, direction, round(entry_price, 6), round(exit_price, 6),
round(qty, 2), tp1_hit, tp2_hit, sl_hit, round(net_pnl, 2), result_type,
duration_minutes, htf_confirmed, round(atr, 6), round(adx, 6), round(bb_width, 6),
round(commission, 6)
]
with open(TP_LOG_FILE, mode="a", newline="") as file:
writer = csv.writer(file)
if not os.path.isfile(TP_LOG_FILE):
writer.writerow([
"Date", "Symbol", "Side", "Entry Price", "Exit Price", "Qty",
"TP1 Hit", "TP2 Hit", "SL Hit", "PnL (%)", "Result", "Held (min)",
"HTF Confirmed", "ATR", "ADX", "BB Width", "Commission"
])
writer.writerow(row)

Логирование событий: Корректно обрабатывать Soft Exit, Trailing Stop, TP1, TP2, SL.

В engine_controller.py

Graceful shutdown: Реализовать через обработку сигналов SIGINT, SIGTERM.
Проверка лимитов: Добавить валидацию MAX_POSITIONS и MAX_OPEN_ORDERS.
Реализация: def run_trading_cycle(symbols, stop_event):
positions = exchange.fetch_positions()
active_positions = sum(1 for pos in positions if float(pos.get("contracts", 0)) != 0)
if active_positions >= MAX_POSITIONS:
log(f"Max positions ({MAX_POSITIONS}) reached. Skipping cycle.", level="INFO")
return
for symbol in symbols:
if stop_event.is_set():
break
process_symbol(symbol, get_cached_balance(), last_trade_times, last_trade_times_lock)

В symbol_processor.py

Исправление маржи: Добавить буфер 90% для предотвращения ошибок.
Проверка данных: Исключить NoneType ошибки.
Реализация: def process_symbol(symbol, balance, last_trade_times, lock):
if any(v is None for v in [symbol, balance]):
log(f"Skipping {symbol} — invalid input data", level="ERROR")
return None
required_margin = qty _ entry / LEVERAGE_MAP.get(normalized_symbol, 5)
if required_margin > available_margin _ 0.9:
log(f"Skipping {symbol} — margin too high: required={required_margin:.2f}, available={available_margin:.2f}", level="WARNING")
return None
notional = qty \* entry
if notional < MIN_NOTIONAL_OPEN:
log(f"Skipping {symbol} — notional too low: {notional:.2f} < {MIN_NOTIONAL_OPEN}", level="WARNING")
return None

В telegram_commands.py

Команды /stop и /panic YES: Исправить для корректного закрытия позиций.
Оповещения: Добавить уведомления о сбоях.
Реализация: def handle_telegram_command(message, state):
if message["text"] == "/stop":
state["stopping"] = True
save_state(state)
positions = exchange.fetch_positions()
for pos in positions:
if float(pos.get("contracts", 0)) > 0:
close_real_trade(pos["symbol"])
send_telegram_message("Stop command received. Closing positions.", force=True)
elif message["text"] == "/panic YES":
handle_panic(stop_event)

В main.py

Глобальный try/except: Перехватывать все исключения.
Завершение: Использовать stop_event.
Реализация: def start_trading_loop():
try:
while RUNNING and not stop_event.is_set():
run_trading_cycle(symbols, stop_event)
time.sleep(10)
except Exception as e:
log(f"Main loop error: {e}", level="ERROR")
send_telegram_message(f"Critical error: {e}", force=True)
stop_event.set()

В utils_logging.py

Логирование: Добавить ID сделок и причины закрытия.
Реализация: def log(message: str, important=False, level="INFO", trade_id=None):
full_msg = f"[{timestamp}] [{level}]"
if trade_id:
full_msg += f" [TradeID: {trade_id}]"
full_msg += f" {message}"
with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
f.write(full_msg + "\n")

Новые дополнения

stats.py: Добавить метрики (винрейт, просадка).
Реализация: def analyze_backtest(df):
win_rate = len(df[df["PnL (%)"] > 0]) / len(df) \* 100
avg_profit = df["PnL (%)"].mean()
max_drawdown = (df["PnL (%)"].cumsum().cummax() - df["PnL (%)"].cumsum()).max()
return {"win_rate": win_rate, "avg_profit": avg_profit, "max_drawdown": max_drawdown}

volatility_controller.py: Динамические фильтры на основе ATR.
pair_selector.py: Исключение коррелированных пар (>0.8).

Риск-менеджмент

Адаптивный риск: 1% (<100 USDC), 2% (100–150 USDC), 3% (150–300 USDC), 5% (>300 USDC).
Размер позиции: (баланс _ RISK_PERCENT) / риск в долларах.
Стоп-лосс: 1% или 1.5 _ ATR.
Тейк-профиты: TP1 = 0.7% или 1 _ ATR, TP2 = 1.3% или 2 _ ATR.
Break-Even: Перенос SL после TP1.
Ограничение позиций: 1–3 в зависимости от баланса.
Минимальный профит: 0.5 USDC (с учетом комиссий).
Мониторинг: Аудит через stats.py, оповещения в Telegram.
Лимит убытков: Остановка при просадке 5%.

Оптимизация торговли

Split TP: 70% на TP1, 30% на TP2.
Trailing Stop: Включить с fallback на фиксированный SL.
Фильтрация прибыли: Пропускать сделки <0.5 USDC.
Проверка нотинала: Соответствие MIN_NOTIONAL_OPEN и MIN_NOTIONAL_ORDER.
Risk/Reward: Соотношение ≥1:1.5.

Выбор пар

Динамический отбор: Волатильность (ATR) и объем через pair_selector.py.
Обновление: Каждые 1–2 часа.
Ликвидность: Минимальный объем, узкие спреды.
Корреляция: Исключать пары с корреляцией >0.8.
Приоритет: XRP/USDC, DOGE/USDC для депозита <150 USDC.
ML: В перспективе кластеризация пар.

Обработка ошибок

safe_call_retry: 3 попытки, задержка 1 секунда.
Глобальный try/except: В main.py.
Graceful Shutdown: На SIGINT, SIGTERM, /stop, /panic YES.
Фоллбэки: Фиксированный SL при сбоях трейлинга.
Валидация данных: Проверки в symbol_processor.py и trade_engine.py.
Оповещения: Telegram-уведомления о сбоях.

Долгосрочные улучшения

Метрики: Комиссии, проскальзывание, время удержания в stats.py.
Анализ: Дневные/недельные отчеты через stats.py.
ML: Кластеризация пар, регрессия для TP/SL.
Мульти-биржи: Поддержка Bybit и других платформ.
Базы данных: Хранение сделок для анализа.
Авто-оптимизация: Динамическая настройка через ML.

Тест-план

Очистка логов: Удалить дубли в tp_performance.csv, проверить формат.
Тест лимитов: Запустить с MAX_POSITIONS=1, MIN_NOTIONAL_OPEN=20.
Тест команд: Проверить /stop, /panic YES, graceful shutdown (Ctrl+C).
Тест ошибок: Смоделировать MarginError, NoneType, проверить safe_call_retry.
Бэктестирование: Анализ данных за январь–март 2025 через stats.py. Цели: винрейт ≥60%, просадка ≤5%.
Комплексный REAL_RUN: 1-часовой тест в DRY_RUN, проверка позиций, TP/SL, логов.
Проверка логов: Сравнить tp_performance.csv с данными Binance, убедиться в отсутствии дублей.
Финальная стабилизация: Исправить все ошибки, выполнить чистый прогон.

Заключение
Обновленный план сохраняет все ключевые элементы оригинала, дополняя их новыми рекомендациями для устранения текущих проблем и подготовки к реальной торговле. Реализация высокоприоритетных задач обеспечит стабильность, прибыльность и масштабируемость бота, позволяя работать с увеличивающимся депозитом.
Рекомендации:

Фокусироваться на парах с низкой ценой (XRP/USDC, DOGE/USDC) для депозита 100–120 USDC.
Начать с риска 1%, увеличивая до 2–3% с ростом депозита.
Провести тестирование перед реальной торговлей для минимизации рисков.

Ключевые цитаты:

Binance Fees Breakdown: A Detailed Guide for 2025
Binance API Documentation for Futures

Высокоприоритетные задачи и имплементация

Исправление ошибок (NoneType, MarginError)Описание: Устранить ошибки "unsupported operand type(s) for \*=: 'float' and 'NoneType'" и "Margin is insufficient".Имплементация:

Файл: symbol_processor.py def process_symbol(symbol, balance, last_trade_times, lock):
if any(v is None for v in [symbol, balance, entry, stop]):
log(f"Skipping {symbol} — invalid input data", level="ERROR")
return None
required_margin = qty _ entry / LEVERAGE_MAP.get(normalized_symbol, 5)
if required_margin > available_margin _ 0.9:
log(f"Skipping {symbol} — margin too high: required={required_margin:.2f}, available={available_margin:.2f}", level="WARNING")
return None
notional = qty \* entry
if notional < MIN_NOTIONAL_OPEN:
log(f"Skipping {symbol} — notional too low: {notional:.2f} < {MIN_NOTIONAL_OPEN}", level="WARNING")
return None

Файл: trade_engine.py def enter_trade(symbol, side, qty, score=5, is_reentry=False):
if any(v is None for v in [entry_price, tp1_price, sl_price]):
log(f"Skipping TP/SL for {symbol} — invalid prices", level="ERROR")
return

Срок: 1–2 дня.

Обновление настроек в config.pyОписание: Активировать адаптивные параметры, установить MIN_NOTIONAL_OPEN = 20.Имплементация:

Файл: config.py def get_adaptive_risk_percent(balance):
if balance < 100:
return 0.01 # 1%
elif balance < 150:
return 0.02 # 2%
elif balance < 300:
return 0.03 # 3%
else:
return 0.05 # 5%

def get_max_positions(balance):
if balance < 100:
return 1
elif balance < 150:
return 2
elif balance < 300:
return 3
else:
return 5

from utils_core import get_cached_balance
balance = get_cached_balance()
RISK_PERCENT = get_adaptive_risk_percent(balance)
MAX_POSITIONS = get_max_positions(balance)
MIN_NOTIONAL_OPEN = 20
MIN_NOTIONAL_ORDER = 20
TP1_PERCENT = 0.007
TP2_PERCENT = 0.013
SL_PERCENT = 0.01
TP1_SHARE = 0.7
TP2_SHARE = 0.3
MAX_OPEN_ORDERS = 3

Срок: 1 день.

Расчет комиссийОписание: Добавить учет комиссий (0.02% maker, 0.05% taker) в tp_performance.csv.Имплементация:

Файл: tp*logger.py def log_trade_result(symbol, direction, entry_price, exit_price, qty, tp1_hit, tp2_hit, sl_hit, pnl_percent, duration_minutes, htf_confirmed, atr, adx, bb_width, result_type="manual"):
commission = qty * entry_price * TAKER_FEE_RATE * 2
net_pnl = ((exit_price - entry_price) / entry_price * 100) - (commission / (qty * entry_price) * 100)
if direction == "SELL":
net_pnl \*= -1
date_str = now_with_timezone().strftime("%Y-%m-%d %H:%M:%S")
trade_id = f"{symbol}*{date*str}*{result_type}"
if trade_id in logged_trades:
log(f"Skipping duplicate trade {trade_id}", level="DEBUG")
return
logged_trades.add(trade_id)
row = [
date_str, symbol, direction, round(entry_price, 6), round(exit_price, 6),
round(qty, 2), tp1_hit, tp2_hit, sl_hit, round(net_pnl, 2), result_type,
duration_minutes, htf_confirmed, round(atr, 6), round(adx, 6), round(bb_width, 6),
round(commission, 6)
]
with open(TP_LOG_FILE, mode="a", newline="") as file:
writer = csv.writer(file)
if not os.path.isfile(TP_LOG_FILE):
writer.writerow([
"Date", "Symbol", "Side", "Entry Price", "Exit Price", "Qty",
"TP1 Hit", "TP2 Hit", "SL Hit", "PnL (%)", "Result", "Held (min)",
"HTF Confirmed", "ATR", "ADX", "BB Width", "Commission"
])
writer.writerow(row)

Срок: 1–2 дня.

Динамическая настройка TP/SLОписание: Внедрить ATR для адаптации TP/SL.Имплементация:

Файл: trade_engine.py from ta.volatility import AverageTrueRange
def calculate_tp_levels(entry_price: float, side: str, regime: str = None, score: float = 5, df=None):
atr = AverageTrueRange(df["high"], df["low"], df["close"], window=14).average_true_range().iloc[-1]
sl_pct = 1.5 _ atr / entry_price
tp1_pct = 1.0 _ atr / entry_price
tp2_pct = 2.0 _ atr / entry_price
if AUTO_TP_SL_ENABLED and regime:
if regime == "flat":
tp1_pct _= FLAT_ADJUSTMENT
tp2_pct _= FLAT_ADJUSTMENT
sl_pct _= FLAT_ADJUSTMENT
elif regime == "trend":
tp2_pct _= TREND_ADJUSTMENT
sl_pct _= TREND_ADJUSTMENT
if side.lower() == "buy":
tp1_price = entry_price _ (1 + tp1_pct)
tp2_price = entry_price _ (1 + tp2_pct) if tp2_pct else None
sl_price = entry_price _ (1 - sl_pct)
else:
tp1_price = entry_price _ (1 - tp1_pct)
tp2_price = entry_price _ (1 - tp2_pct) if tp2_pct else None
sl_price = entry_price _ (1 + sl_pct)
return (
round(tp1_price, 4), round(tp2_price, 4) if tp2_price else None,
round(sl_price, 4), TP1_SHARE, TP2_SHARE
)

Файл: strategy.py def should_enter_trade(symbol, df, exchange, last_trade_times, last_trade_times_lock):
result = calculate_tp_levels(entry_price, direction, regime, score, df=df)

Срок: 2–3 дня.

Тестирование и стабилизацияОписание: Провести бэктестирование и реальные симуляции.Имплементация:

Бэктестирование:
Файл: stats.py def analyze_backtest(df):
win_rate = len(df[df["PnL (%)"] > 0]) / len(df) \* 100
avg_profit = df["PnL (%)"].mean()
max_drawdown = (df["PnL (%)"].cumsum().cummax() - df["PnL (%)"].cumsum()).max()
return {"win_rate": win_rate, "avg_profit": avg_profit, "max_drawdown": max_drawdown}

Анализировать данные за январь–март 2025, целевые метрики: винрейт ≥60%, просадка ≤5%.

Реальная симуляция:
Запустить DRY_RUN на 1 час, проверить позиции, TP/SL, логи.

Проверка логов:
Сравнить tp_performance.csv с историей Binance, убедиться в отсутствии дублей.Срок: 3–5 дней.
