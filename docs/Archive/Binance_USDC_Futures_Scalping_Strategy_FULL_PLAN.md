Binance USDC Futures Smart Bot v1.6.2 - Полный план с кодом и разделами
Введение
Этот документ представляет детальный план разработки торгового бота Binance USDC Futures Smart Bot с использованием многофреймовой скальпинговой стратегии. Бот предназначен для автоматической торговли фьючерсами с начальным капиталом 44 USDC, планомерным масштабированием до 600–1500 USDC и целью достижения прибыли около 50 USD в день. План включает:

Описание архитектуры системы.
Используемые индикаторы и условия стратегии.
Шаги входа/выхода из сделок.
Управление рисками.
Основной цикл работы.
Масштабирование и уведомления в Telegram.
Дополнительные разделы: бэктестинг, обработка ошибок, оптимизация производительности и безопасность.
Документ структурирован по разделам и подкреплен примерами кода для иллюстрации ключевых идей.

Цель стратегии
Торговать USDC futures на Binance с использованием трех таймфреймов:
1 час: определение глобального тренда.
15 минут: генерация основных сигналов.
5 минут: точное подтверждение входа.
Управлять рисками с фиксированным риском 5% от депозита на начальном этапе, обеспечивая минимум 10 сделок в день.
Последовательно масштабировать капитал после успешного тестирования в течение 1-2 недель.
Архитектура
Архитектура бота построена модульно, обеспечивая гибкость и устойчивость системы. Основные компоненты:

Модули системы
Модуль получения данных (Data Fetcher):
Подключается к API Binance Futures, получает рыночные данные (OHLCV) для таймфреймов 1h, 15m, 5m. Поддерживает как периодические запросы, так и подписку через WebSocket.
Модуль стратегии (Strategy):
Рассчитывает индикаторы (EMA, MACD, RSI, Stochastic RSI, ATR) и генерирует торговые сигналы на основе многофреймового анализа.
Торговый движок (Trade Engine):
Исполняет сигналы, рассчитывает размеры позиций, выставляет ордера (рыночные/лимитные), управляет стоп-лоссом и тейк-профитом, включая трейлинг-стоп и безубыточность.
Логирование и аналитика:
Фиксирует сделки и события в логах (trade_log.csv), генерирует отчеты (ежедневные/еженедельные) для анализа эффективности.
Интеграция с Telegram:
Отправляет уведомления о сделках, ошибках и отчетах, поддерживает команды управления (/status, /pause, /shutdown).
Конфигурация и режимы работы:
Параметры (API-ключи, пары, риск) хранятся в config.py. Поддерживает режимы DRY_RUN (тестирование без ордеров) и REAL_RUN (реальная торговля).
Структура файлов
Файл Описание
main.py Основной цикл работы бота
strategy.py Логика индикаторов и сигналов
trade_engine.py Исполнение ордеров и сопровождение позиций
config.py Настройки бота
entry_logger.py Логирование входов в сделки
tp_logger.py Логирование TP/SL-результатов
telegram_handler.py Уведомления и команды через Telegram
pair_selector.py Выбор активных пар по объему/волатильности
Данные: Состояние хранится в state.json, логи — в trade_log.csv, статистика — в tp_performance.csv.

Торговая стратегия
Таймфреймы и индикаторы
1 час (1h):
EMA50/EMA200: Определение тренда (EMA50 > EMA200 — бычий, иначе медвежий).
15 минут (15m):
MACD: Генерация сигналов (пересечение линий).
RSI: Фильтр перекупленности/перепроданности (< 50 для buy, > 50 для sell).
ATR: Расчет SL/TP.
5 минут (5m):
Stochastic RSI: Подтверждение входа (K < 20 для buy, > 80 для sell).
Условия входа
Фильтр тренда (1h):
Лонг: EMA50 > EMA200.
Шорт: EMA50 < EMA200.
Сигнал (15m):
Лонг: MACD > MACD_signal и RSI < 50.
Шорт: MACD < MACD_signal и RSI > 50.
Подтверждение (5m):
Лонг: Stochastic RSI K < 20.
Шорт: Stochastic RSI K > 80.
Условия выхода
Стоп-лосс (SL): ATR _ 1.5 от цены входа.
Тейк-профит (TP): ATR _ 2 от цены входа.
Дополнительно: Soft Exit, Break-Even, Trailing Stop (описаны ниже).
Код (strategy.py):

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
return direction

def confirm_entry(df_5m, signal):
if df_5m is None or df_5m.empty:
return False
if signal == 'buy' and df_5m['Stoch_RSI_K'].iloc[-1] < 20:
return True
elif signal == 'sell' and df_5m['Stoch_RSI_K'].iloc[-1] > 80:
return True
return False
Шаги реализации
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
Шаг 2: Расчет индикаторов
Что делаем: Рассчитываем EMA50/EMA200 (1h), MACD/RSI/ATR (15m), Stochastic RSI (5m).
Почему: Обеспечиваем анализ тренда, сигналов и точного входа.
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
Шаг 3: Определение глобального тренда
Что делаем: Анализируем 1h по EMA50 и EMA200.
Почему: Фильтрует сигналы по тренду.
Код (strategy.py):
python

Collapse

Unwrap

Copy
def get_trend(df_1h):
if df_1h is None or df_1h.empty:
return 'neutral'
return 'bullish' if df_1h['EMA50'].iloc[-1] > df_1h['EMA200'].iloc[-1] else 'bearish'
Шаг 4: Генерация сигналов
Что делаем: Генерируем сигналы на 15m с учетом тренда (MACD, RSI).
Почему: Обеспечивает точные сигналы в направлении тренда.
Код: См. "Торговая стратегия" выше.
Шаг 5: Подтверждение входа
Что делаем: Проверяем вход на 5m с Stochastic RSI.
Почему: Уточняет момент входа.
Код: См. "Торговая стратегия" выше.
Шаг 6: Расчет SL/TP и управление рисками
Что делаем: Устанавливаем SL/TP по ATR, риск 5%.
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
Шаг 7: Выставление ордеров и сопровождение позиции
Что делаем: Выставляем TP1 (70%), TP2 (30%), SL, запускаем Soft Exit, Break-Even, Trailing Stop.
Почему: Обеспечивает гибкое управление позицией.
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
safe_call_retry(exchange.create_order, symbol, "STOP_MARKET", "sell" if direction == "buy" else "buy", qty, params={"stopPrice": sl_price})
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
trailing_distance = entry_price \* 0.01
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
Шаг 8: Основной цикл и логирование
Что делаем: Перебираем пары каждую минуту, генерируем сигналы, логируем сделки.
Почему: Обеспечивает непрерывную торговлю и мониторинг.
Код (main.py):
python

Collapse

Unwrap

Copy
import time
import pandas as pd
from strategy import fetch_data, calculate_indicators, get_trend, generate_signal, confirm_entry
from trade_engine import enter_trade
from utils_core import get_cached_balance
from utils_logging import log

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
Бэктестинг стратегии
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
cerebro.run()
Обработка ошибок
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
raise
Оптимизация производительности
Описание: Ускорение бота с помощью асинхронных вызовов и кэширования.
Почему: Критично для скальпинга.
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

tickers = asyncio.run(fetch_multiple_symbols(SYMBOLS_ACTIVE))
Безопасность
Описание: Защита API-ключей через переменные окружения.
Почему: Предотвращает утечки и доступ.
Код:
python

Collapse

Unwrap

Copy
import os

API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')
exchange = ccxt.binance({'apiKey': API_KEY, 'secret': API_SECRET})
Мониторинг и отчеты
Описание: Логирование сделок и отчеты через Telegram.
Почему: Отслеживание производительности.
Код:
python

Collapse

Unwrap

Copy
def send_daily_report(pnl, win_rate):
message = f"Daily Report: PnL {pnl}, Win Rate {win_rate}%"
send_telegram_message(message)
Масштабирование и улучшения
Описание: Увеличение капитала до 600–1500 USD, ML-оптимизация TP/SL.
Почему: Достижение 50 USD в день.
Рекомендации:
Тест на 44 USD (1-2 недели).
Увеличение до 500 USD, затем до 1000 USD.
Использование tp_optimizer для анализа.
Код (config.py):

python

Collapse

Unwrap

Copy
RISK_PERCENT = 0.05
MAX_OPEN_POSITIONS = 3
MIN_NOTIONAL = 2
Таблица параметров
Параметр Значение Описание
BALANCE 44 USD Начальный депозит
RISK_PERCENT 0.05 5% риска на сделку
MIN_NOTIONAL 2 USD Минимальный нотинал
MAX_OPEN_POSITIONS 1 Максимум позиций на старте
TP1_PERCENT 0.007 Тейк-профит 1 (0.7%)
TP2_PERCENT 0.013 Тейк-профит 2 (1.3%)
SL_PERCENT 0.01 Стоп-лосс (1%)
Заключение
Этот план объединяет детальную реализацию стратегии с дополнительными функциями для надежности и масштабирования. Он охватывает все аспекты разработки бота, от загрузки данных до управления рисками и уведомлений. Рекомендуется начать с теста на 44 USD, затем масштабировать капитал для достижения цели 50 USD в день.
