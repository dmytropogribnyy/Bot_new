Объединенный документ: Binance USDC Futures Smart Bot v1.6.2 - Полный план с кодом и разделами
Введение
Этот объединенный план описывает создание торгового бота для скальпинга на Binance USDC Futures, с целью достижения прибыли 50 USD в день при масштабировании капитала с начальных 44 USD до 600–1500 USD. План включает многофреймовую стратегию (1 час для тренда, 15 минут для сигналов, 5 минут для входа), реализацию с примерами кода и дополнительные разделы для бэктестинга, обработки ошибок, оптимизации производительности и безопасности. Документ объединяет детальные шаги из gpt_steps.md и расширенные функции из grok.md, обеспечивая исчерпывающее руководство для разработчиков и пользователей.

Цель стратегии
Торговать USDC futures на Binance с использованием трех таймфреймов:
1 час для определения глобального тренда.
15 минут для генерации основных сигналов.
5 минут для точного подтверждения входа.
Управлять рисками с установкой риска 5% от депозита на начальном этапе, обеспечивая минимум 10 сделок в день.
Последовательно масштабировать капитал после успешного тестирования в течение 1-2 недель.
Основные разделы
Введение: Обзор цели и стратегии.
Архитектура системы: Описание модульной структуры и ключевых файлов.
Торговая стратегия: Подробности о таймфреймах и индикаторах.
Шаги реализации: Пошаговое руководство с кодом для каждого этапа.
Бэктестинг стратегии: Проверка на исторических данных.
Обработка ошибок: Управление сбоями API и сети.
Оптимизация производительности: Ускорение работы бота.
Безопасность: Защита API-ключей и данных.
Мониторинг и отчеты: Отслеживание результатов и логирование.
Масштабирование и улучшения: Планы на будущее с увеличением капитала.

1. Введение
   Описание: Бот предназначен для автоматизированной торговли на USDC futures с акцентом на скальпинг, с целью достичь 50 USD прибыли в день при масштабировании капитала с 44 USD.
   Детали: Стратегия использует многофреймовый анализ с индикаторами EMA, MACD, RSI и Stochastic RSI, начиная с тестового периода и увеличивая капитал после успешных результатов.
2. Архитектура системы
   Описание: Модульная структура включает:
   main.py: Основной цикл, перебирающий пары и запускающий торговую логику.
   strategy.py: Логика расчета индикаторов и генерации сигналов (1h/15m/5m).
   trade_engine.py: Расчет позиции, выставление ордеров, сопровождение сделки.
   config.py: Параметры стратегии, риска, API.
   entry_logger.py, tp_logger.py: Логирование сделок и TP/SL-результатов.
   telegram_handler.py: Уведомления и команды через Telegram.
   tp_optimizer.py, tp_optimizer_ml.py: Адаптация TP/SL на основе истории.
   pair_selector.py: Динамический выбор активных пар по объему и волатильности.
   Детали: Данные хранятся в state.json, trade_log.csv, tp_performance.csv для мониторинга и анализа.
3. Торговая стратегия
   Описание: Использует три таймфрейма:
   1 час: Определение тренда (EMA50 > EMA200 для бычьего, иначе медвежий).
   15 минут: Генерация сигналов (MACD, RSI, ATR).
   5 минут: Подтверждение входа (Stochastic RSI K < 20 для buy, > 80 для sell).
   Сигналы:
   Buy: MACD > MACD_signal и RSI < 50 в бычьем тренде, подтверждено на 5m.
   Sell: MACD < MACD_signal и RSI > 50 в медвежьем тренде, подтверждено на 5m.
   Пример кода (strategy.py):
   python

Collapse

Unwrap

Copy
def generate_signal(df_15m, trend, use_htf_confirmation=True):
if df_15m is None or df_15m.empty:
return None
if trend == 'bullish' and df_15m['MACD'].iloc[-1] > df_15m['MACD_signal'].iloc[-1] and df_15m['RSI'].iloc[-1] < 50:
direction = 'buy'
elif trend == 'bearish' and df_15m['MACD'].iloc[-1] < df_15m['MACD_signal'].iloc[-1] and df_15m['RSI'].iloc[-1] > 50:
direction = 'sell'
else:
return None
if use_htf_confirmation:
if direction == 'buy' and trend != 'bullish':
log("Buy сигнал отклонён: тренд не bullish", level='INFO')
return None
if direction == 'sell' and trend != 'bearish':
log("Sell сигнал отклонён: тренд не bearish", level='INFO')
return None
return direction 4. Шаги реализации
Шаг 1: Загрузка данных и фильтрация по ликвидности
Что делаем: Подключаемся к Binance через ccxt, загружаем OHLCV-данные для 1h, 15m, 5m, отсекаем пары с объемом < 10,000.
Почему: Избегаем низколиквидных пар с высоким риском проскальзывания.
Код (strategy.py):
python

Collapse

Unwrap

Copy
import ccxt
import pandas as pd
import ta
from utils_logging import log

exchange = ccxt.binance({
'apiKey': 'YOUR_API_KEY',
'secret': 'YOUR_SECRET',
'enableRateLimit': True,
})

def fetch_data(symbol, timeframe, limit=100):
try:
ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
avg_vol = df['volume'].mean()
min_vol_threshold = 10000
if avg_vol < min_vol_threshold:
log(f"{symbol} отклонён: низкая ликвидность (ср. объём {avg_vol:.2f})", level='INFO')
return None
return df
except Exception as e:
log(f"Ошибка загрузки данных для {symbol}: {e}", level='ERROR')
return None
Краткое саммари: Функция загружает данные и отсекает пары с низким объемом, снижая риск проскальзывания.
Шаг 2: Расчет индикаторов
Что делаем: Рассчитываем EMA50/EMA200 (1h), MACD/RSI/ATR (15m), Stochastic RSI (5m).
Почему: Индикаторы обеспечивают анализ тренда, сигналов и точного входа.
Код (strategy.py):
python

Collapse

Unwrap

Copy
def calculate_indicators(df, timeframe):
if timeframe == '1h':
df['EMA50'] = ta.trend.EMAIndicator(df['close'], window=50).ema_indicator()
df['EMA200'] = ta.trend.EMAIndicator(df['close'], window=200).ema_indicator()
elif timeframe == '15m':
macd_obj = ta.trend.MACD(df['close'])
df['MACD'] = macd_obj.macd()
df['MACD_signal'] = macd_obj.macd_signal()
df['RSI'] = ta.momentum.RSIIndicator(df['close']).rsi()
df['ATR'] = ta.volatility.AverageTrueRange(df['high'], df['low'], df['close']).average_true_range()
elif timeframe == '5m':
df['Stoch_RSI_K'] = ta.momentum.StochRSIIndicator(df['close']).stochrsi_k() \* 100
return df
Краткое саммари: Вычисляем индикаторы для каждого таймфрейма, обеспечивая данные для анализа.
Шаг 3: Определение глобального тренда
Что делаем: Анализируем 1h по EMA50 и EMA200.
Почему: Фильтрует сигналы по основному направлению рынка.
Код (strategy.py):
python

Collapse

Unwrap

Copy
def get_trend(df_1h):
if df_1h is None or df_1h.empty:
return 'neutral'
return 'bullish' if df_1h['EMA50'].iloc[-1] > df_1h['EMA200'].iloc[-1] else 'bearish'
Краткое саммари: Определяет тренд для фильтрации сигналов.
Шаг 4: Генерация сигналов
Что делаем: Генерируем сигналы на 15m с учетом тренда (MACD, RSI).
Почему: Обеспечивает точные сигналы в направлении тренда.
Код: См. раздел "Торговая стратегия" выше.
Краткое саммари: Генерирует сигналы с фильтром тренда для точности.
Шаг 5: Подтверждение входа
Что делаем: Проверяем вход на 5m с Stochastic RSI (K < 20 для buy, > 80 для sell).
Почему: Уточняет момент входа, минимизируя ложные сигналы.
Код (strategy.py):
python

Collapse

Unwrap

Copy
def confirm_entry(df_5m, signal):
if df_5m is None or df_5m.empty:
return False
if signal == 'buy' and df_5m['Stoch_RSI_K'].iloc[-1] < 20:
return True
elif signal == 'sell' and df_5m['Stoch_RSI_K'].iloc[-1] > 80:
return True
return False
Краткое саммари: Подтверждает вход для точного тайминга.
Шаг 6: Расчет SL/TP и управление рисками
Что делаем: Устанавливаем SL/TP по ATR (SL = ATR _ 1.5, TP = ATR _ 2), риск 5%, размер позиции: qty = risk_amount / |entry_price - stop_price|.
Почему: Защищает капитал и адаптируется к волатильности.
Код (trade_engine.py):
python

Collapse

Unwrap

Copy
def calculate_risk_amount(balance, risk_percent=0.05):
return balance \* risk_percent

def calculate_position_size(entry_price, stop_price, risk_amount):
risk_per_unit = abs(entry_price - stop_price)
return round(risk_amount / risk_per_unit, 3) if risk_per_unit else 0

def calculate_sl_tp(df_15m, entry_price, direction):
atr = df_15m['ATR'].iloc[-1]
if direction == 'buy':
sl = entry_price - atr _ 1.5
tp = entry_price + atr _ 2
else:
sl = entry_price + atr _ 1.5
tp = entry_price - atr _ 2
return sl, tp
Краткое саммари: Рассчитывает SL/TP и размер позиции для защиты капитала.
Шаг 7: Выставление ордеров и сопровождение позиции
Что делаем: Выставляем TP1 (70%), TP2 (30%), SL как STOP_MARKET, запускаем Soft Exit, Break-Even, Trailing Stop в потоках.
Почему: Обеспечивает прибыль и защиту позиции с гибкостью выхода.
Код (trade_engine.py):
python

Collapse

Unwrap

Copy
import threading

def enter_trade(symbol, direction, qty, entry_price, score, is_reentry=False):
tp1_price = entry_price _ (1 + 0.007 if direction == "buy" else -0.007)
tp2_price = entry_price _ (1 + 0.013 if direction == "buy" else -0.013)
sl_price = entry_price _ (1 - 0.01 if direction == "buy" else 0.01)
if qty _ entry_price < 2:
log(f"{symbol} Notional too low", level='WARNING')
return
log(f"{symbol} OPEN {direction.upper()} @ {entry_price}", level='INFO')
if not DRY_RUN:
send_telegram_message(f"OPEN {direction.upper()} {symbol} @ {entry_price}")
safe_call_retry(exchange.create_limit_order, symbol, "sell" if direction == "buy" else "buy", qty _ 0.7, tp1_price)
safe_call_retry(exchange.create_limit_order, symbol, "sell" if direction == "buy" else "buy", qty _ 0.3, tp2_price)
safe_call_retry(exchange.create_order, symbol, "STOP_MARKET", "sell" if direction == "buy" else "buy", qty, params={"stopPrice": sl_price}) # Запуск механизмов сопровождения
threading.Thread(target=run_soft_exit, args=(symbol, direction, entry_price, tp1_price, qty)).start()
threading.Thread(target=run_break_even, args=(symbol, direction, entry_price, qty)).start()
threading.Thread(target=run_trailing_stop, args=(symbol, direction, entry_price, qty)).start()

def run_soft_exit(symbol, direction, entry_price, tp1_price, qty):
soft_exit_threshold = 0.9
soft_exit_price = entry_price + (tp1_price - entry_price) _ soft_exit_threshold if direction == 'buy' else entry_price - (entry_price - tp1_price) _ soft_exit_threshold
while True:
current_price = fetch_data(symbol, '1m')['close'].iloc[-1]
if (direction == 'buy' and current_price >= soft_exit_price) or (direction == 'sell' and current_price <= soft_exit_price):
log(f"Soft Exit triggered for {symbol} @ {current_price}", level='INFO')
if not DRY_RUN:
safe_call_retry(exchange.create_market_order, symbol, "sell" if direction == "buy" else "buy", qty \* 0.5)
break
time.sleep(5)

def run_break_even(symbol, direction, entry_price, qty):
trigger_price = entry_price \* (1 + 0.005 if direction == 'buy' else -0.005)
while True:
current_price = fetch_data(symbol, '1m')['close'].iloc[-1]
if (direction == 'buy' and current_price >= trigger_price) or (direction == 'sell' and current_price <= trigger_price):
log(f"Break-Even triggered for {symbol} @ {entry_price}", level='INFO')
if not DRY_RUN:
safe_call_retry(exchange.create_order, symbol, "STOP_MARKET", "sell" if direction == "buy" else "buy", qty, params={"stopPrice": entry_price})
break
time.sleep(5)

def run_trailing_stop(symbol, direction, entry_price, qty):
trailing_distance = entry_price \* 0.01 # 1% trailing
max_price = entry_price if direction == 'buy' else float('inf')
min_price = entry_price if direction == 'sell' else 0
while True:
current_price = fetch_data(symbol, '1m')['close'].iloc[-1]
if direction == 'buy':
max_price = max(max_price, current_price)
if current_price <= max_price - trailing_distance:
log(f"Trailing Stop triggered for {symbol} @ {current_price}", level='INFO')
if not DRY_RUN:
safe_call_retry(exchange.create_market_order, symbol, "sell", qty)
break
else:
min_price = min(min_price, current_price)
if current_price >= min_price + trailing_distance:
log(f"Trailing Stop triggered for {symbol} @ {current_price}", level='INFO')
if not DRY_RUN:
safe_call_retry(exchange.create_market_order, symbol, "buy", qty)
break
time.sleep(5)
Краткое саммари: Выставляет ордера и запускает механизмы сопровождения для гибкого управления позицией.
Шаг 8: Основной цикл и логирование
Что делаем: Перебираем пары каждую минуту, генерируем сигналы, логируем сделки в CSV и Telegram.
Почему: Обеспечивает непрерывную торговлю и мониторинг.
Код (main.py):
python

Collapse

Unwrap

Copy
SYMBOLS_ACTIVE = ['BTC/USDC', 'ETH/USDC']
while True:
balance = get_cached_balance()
for symbol in SYMBOLS_ACTIVE:
df_1h = fetch_data(symbol, '1h')
df_15m = fetch_data(symbol, '15m')
df_5m = fetch_data(symbol, '5m')
if not all([df_1h, df_15m, df_5m]):
continue
df_1h = calculate_indicators(df_1h, '1h')
df_15m = calculate_indicators(df_15m, '15m')
df_5m = calculate_indicators(df_5m, '5m')
trend = get_trend(df_1h)
signal = generate_signal(df_15m, trend)
if signal and confirm_entry(df_5m, signal):
entry_price = df_5m['close'].iloc[-1]
sl, tp = calculate_sl_tp(df_15m, entry_price, signal)
risk_amount = balance \* 0.05
qty = calculate_position_size(entry_price, sl, risk_amount)
enter_trade(symbol, signal, qty, entry_price, score=5)
time.sleep(60)
Краткое саммари: Перебирает пары, генерирует сигналы и логирует сделки. 5. Бэктестинг стратегии
Описание: Проверка стратегии на исторических данных с использованием backtrader.
Почему: Оценивает эффективность перед реальной торговлей.
Код:
python

Collapse

Unwrap

Copy
import backtrader as bt

class MultiTimeframeStrategy(bt.Strategy):
def **init**(self):
self.ema50_1h = bt.indicators.EMA(self.data1.close, period=50)
self.ema200_1h = bt.indicators.EMA(self.data1.close, period=200)

    def next(self):
        if self.ema50_1h > self.ema200_1h:
            self.buy()

cerebro = bt.Cerebro()
data = bt.feeds.PandasData(dataname=df_1h)
cerebro.adddata(data)
cerebro.addstrategy(MultiTimeframeStrategy)
cerebro.run() 6. Обработка ошибок
Описание: Обеспечение стабильности при сбоях API и сети.
Почему: Предотвращает остановку бота из-за временных проблем.
Код:
python

Collapse

Unwrap

Copy
from tenacity import retry, wait_exponential

@retry(wait=wait_exponential(multiplier=1, min=4, max=10))
def fetch_data_with_retry(symbol, timeframe):
try:
return exchange.fetch_ohlcv(symbol, timeframe)
except Exception as e:
log(f"Error fetching {symbol}: {e}", level='ERROR')
raise 7. Оптимизация производительности
Описание: Ускорение бота с помощью асинхронных вызовов и кэширования.
Почему: Критично для скальпинга, где важна скорость.
Код:
python

Collapse

Unwrap

Copy
import asyncio
import ccxt.async_support as ccxt

async def fetch_multiple_symbols(symbols):
exchange = ccxt.binance()
tasks = [exchange.fetch_ticker(symbol) for symbol in symbols]
return await asyncio.gather(\*tasks)

tickers = asyncio.run(fetch_multiple_symbols(SYMBOLS_ACTIVE)) 8. Безопасность
Описание: Защита API-ключей через переменные окружения.
Почему: Предотвращает утечки и несанкционированный доступ.
Код:
python

Collapse

Unwrap

Copy
import os

API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')
exchange = ccxt.binance({'apiKey': API_KEY, 'secret': API_SECRET}) 9. Мониторинг и отчеты
Описание: Логирование сделок в CSV и отправка отчетов через Telegram.
Почему: Позволяет отслеживать производительность в реальном времени.
Код:
python

Collapse

Unwrap

Copy
def send_daily_report(pnl, win_rate):
message = f"Daily Report: PnL {pnl}, Win Rate {win_rate}%"
send_telegram_message(message) 10. Масштабирование и улучшения
Описание: Увеличение капитала с 44 USD до 600–1500 USD, добавление ML-оптимизации TP/SL.
Почему: Достижение 50 USD в день требует большего капитала и адаптации.
Рекомендации: После теста увеличить до 500 USD, затем до 1000 USD, использовать tp_optimizer для анализа.
Код (config.py):
python

Collapse

Unwrap

Copy
RISK_PERCENT = 0.05
MAX_OPEN_POSITIONS = 3
MIN_NOTIONAL = 2
Таблица: Ключевые параметры
Параметр Значение Описание
BALANCE 44 USD Начальный депозит
RISK_PERCENT 0.05 5% риска на сделку
MIN_NOTIONAL 2 USD Минимальный нотинал
MAX_OPEN_POSITIONS 1 Максимум позиций на старте
TP1_PERCENT 0.007 Тейк-профит 1 (0.7%)
TP2_PERCENT 0.013 Тейк-профит 2 (1.3%)
SL_PERCENT 0.01 Стоп-лосс (1%)
Заключение
Этот объединенный план включает все шаги и код из gpt_steps.md, дополненные функциями из grok.md, такими как бэктестинг, обработка ошибок, оптимизация и безопасность. Добавлен код для Soft Exit, Break-Even и Trailing Stop, устраняющий единственное упущение из gpt_steps.md. Документ обеспечивает полное руководство для достижения цели 50 USD в день. Рекомендуется начать с теста на 44 USD, затем масштабировать капитал после успешных результатов.

Примечания
Код для Soft Exit, Break-Even и Trailing Stop добавлен в шаг 7 для полноты, основываясь на упоминании в gpt_steps.md.
Дублирующий контент удален, сохраняя уникальные детали из обоих документов.
Если нужны уточнения или дополнительные механизмы, дайте знать!
