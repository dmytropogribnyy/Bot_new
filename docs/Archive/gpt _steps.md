Финальный пошаговый план внедрения многофреймной скальпинговой стратегии
Цель стратегии:
– Торговать USDC futures на Binance с использованием трёх таймфреймов:
• 1 час для определения глобального тренда,
• 15 минут для генерации основных сигналов,
• 5 минут для точного подтверждения входа.
– Управлять рисками с установкой риска 5% от депозита (на начальном этапе) для повышения числа сделок (минимум 10 сделок в день).
– Последовательно масштабировать капитал при успешном тестировании (начиная с 44 USD, затем до 600–1500 USD).

Шаг 1. Загрузка данных и фильтрация по ликвидности
Что делаем:
– Подключаемся к Binance через ccxt и загружаем OHLCV-данные для трёх таймфреймов: 1h, 15m, 5m.
– Добавляем проверку ликвидности: если средний объём торгов ниже заданного порога (например, 10,000), инструмент отсекается.

Почему:
Это помогает избежать торговли на низколиквидных парах, где высокий риск проскальзывания и неустойчивых движений.

Пример кода (strategy.py):

python
Copy
import ccxt
import pandas as pd
import ta
from utils_logging import log

# Инициализация биржи (используйте настройки из config.py)

exchange = ccxt.binance({
'apiKey': 'YOUR_API_KEY',
'secret': 'YOUR_SECRET',
'enableRateLimit': True,
})

def fetch_data(symbol, timeframe, limit=100):
try:
ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms") # Фильтрация по ликвидности: если последние свечи имеют низкий объём, отсекаем
avg_vol = df["volume"].mean()
min_vol_threshold = 10000 # настройте порог по объёму
if avg_vol < min_vol_threshold:
log(f"{symbol} отклонён: низкая ликвидность (ср. объём {avg_vol:.2f})", level="INFO")
return None
return df
except Exception as e:
log(f"Error fetching data for {symbol}: {e}", level="ERROR")
return None
Краткое саммари: Функция fetch_data загружает данные и отсекает инструменты с недостаточным объёмом торгов, чтобы уменьшить риск проскальзывания.

Шаг 2. Расчёт индикаторов для разных таймфреймов
Что делаем:
– Для каждого таймфрейма рассчитываем соответствующие технические индикаторы:

1 час: EMA50 и EMA200 (для определения тренда).

15 минут: MACD (линия и сигнал), RSI, ATR (для генерации сигнала и расчёта SL/TP).

5 минут: Stochastic RSI (для подтверждения точного входа).

Почему:
Каждый индикатор помогает анализировать рынок на разных уровнях: EMA задаёт направление на старшем ТФ, MACD и RSI генерируют сигналы на 15m, а Stochastic RSI на 5m уточняет момент входа.

Пример кода (strategy.py):

python
Copy
def calculate_indicators(df, timeframe):
if timeframe == '1h':
df['EMA50'] = ta.trend.EMAIndicator(df['close'], window=50).ema_indicator()
df['EMA200'] = ta.trend.EMAIndicator(df['close'], window=200).ema_indicator()
elif timeframe == '15m':
macd_obj = ta.trend.MACD(df['close'])
df['MACD'] = macd_obj.macd()
df['MACD_signal'] = macd_obj.macd_signal()
df['RSI'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
df['ATR'] = ta.volatility.AverageTrueRange(df['high'], df['low'], df['close'], window=14).average_true_range()
elif timeframe == '5m': # Для 5-минутного таймфрейма используется Stochastic RSI для подтверждения входа
stochrsi = ta.momentum.StochRSIIndicator(df['close'], window=14)
df['Stoch_RSI_K'] = stochrsi.stochrsi_k() \* 100
return df
Краткое саммари: Вычисляем индикаторы для каждого интервала, чтобы получить всю необходимую информацию для анализа.

Шаг 3. Определение глобального тренда (1h)
Что делаем:
– Анализируем 1-часовой график по EMA50 и EMA200 для определения направления тренда.

Почему:
Определённый глобальный тренд помогает фильтровать сигналы, избегая входов против основного направления рынка.

Пример кода (strategy.py):

python
Copy
def get_trend(df_1h):
if df_1h is None or df_1h.empty:
return 'neutral'
return 'bullish' if df_1h['EMA50'].iloc[-1] > df_1h['EMA200'].iloc[-1] else 'bearish'
Краткое саммари: Функция возвращает 'bullish' для восходящего тренда и 'bearish' для нисходящего, что будет использоваться для фильтрации сигналов.

Шаг 4. Генерация торговых сигналов (15m) с учетом тренда
Что делаем:
– На 15-минутном графике анализируем MACD и RSI.
– Для входа в лонг: MACD > MACD_signal и RSI < 50 (при восходящем тренде).
– Для входа в шорт: MACD < MACD_signal и RSI > 50 (при нисходящем тренде).
– Дополнительно, если включено подтверждение по старшему таймфрейму (USE_HTF_CONFIRMATION), сигнал должен совпадать с направлением тренда.

Почему:
Эта комбинация обеспечивает, что торговый сигнал соответствует глобальному направлению рынка, снижая вероятность контртрендовых входов.

Пример кода (strategy.py):

python
Copy
def generate_signal(df_15m, trend, use_htf_confirmation=True):
if df_15m is None or df_15m.empty:
return None # Основной сигнал по MACD и RSI на 15m
if trend == 'bullish' and df_15m['MACD'].iloc[-1] > df_15m['MACD_signal'].iloc[-1] and df_15m['RSI'].iloc[-1] < 50:
direction = 'buy'
elif trend == 'bearish' and df_15m['MACD'].iloc[-1] < df_15m['MACD_signal'].iloc[-1] and df_15m['RSI'].iloc[-1] > 50:
direction = 'sell'
else:
return None

    # Фильтр тренда: сигнал должен совпадать со старшим таймфреймом
    if use_htf_confirmation:
        # Здесь предполагается, что функция get_trend уже определена для 1h
        if direction == 'buy' and trend != 'bullish':
            log("Buy сигнал отклонён: тренд не bullish", level="INFO")
            return None
        if direction == 'sell' and trend != 'bearish':
            log("Sell сигнал отклонён: тренд не bearish", level="INFO")
            return None

    return direction

Краткое саммари: Сигнал генерируется на основе MACD и RSI, а затем подтверждается соответствием глобальному тренду.

Шаг 5. Подтверждение входа (5m)
Что делаем:
– На 5-минутном графике используем Stochastic RSI для уточнения момента входа.
– Для лонга вход подтверждается, если значение Stoch_RSI_K < 20; для шорта – если > 80.

Почему:
Подтверждение на младшем таймфрейме помогает выбрать более выгодный момент входа и избежать ложных сигналов, обеспечивая точное таймирование.

Пример кода (strategy.py):

python
Copy
def confirm_entry(df_5m, signal):
if df_5m is None or df_5m.empty:
return False
if signal == 'buy' and df_5m['Stoch_RSI_K'].iloc[-1] < 20:
return True
elif signal == 'sell' and df_5m['Stoch_RSI_K'].iloc[-1] > 80:
return True
return False
Краткое саммари: Подтверждение входа через Stochastic RSI на 5m минимизирует риск ложного входа.

Шаг 6. Расчёт стоп-лосса и тейк-профита, управление рисками
Что делаем:
– Вычисляем уровни SL и TP на основе ATR, с учетом адаптации параметров в зависимости от рыночного режима.
– Риск на сделку устанавливаем в 5% от депозита.
– Рассчитываем размер позиции по формуле:
qty = risk_amount / |entry_price - stop_price|

Почему:
Это позволяет защитить депозит при неблагоприятном движении цены, а также обеспечить достаточную потенциальную прибыль (например, соотношение риск/вознаграждение ~1:1.33).

Настройки (config.py):

python
Copy

# Установить риск на сделку 5%

RISK_PERCENT = 0.05 # 5% от депозита

# Параметры TP/SL

TP1_PERCENT = 0.007 # 0.7% прироста
TP2_PERCENT = 0.013 # 1.3% прироста
SL_PERCENT = 0.01 # 1% стоп-лосс

# Минимальный нотионал (обновляем для маленького депозита)

MIN_NOTIONAL = 2
Пример кода (trade_engine.py):

python
Copy
def calculate_risk_amount(balance, risk_percent):
return balance \* risk_percent

def calculate_position_size(entry_price, stop_price, risk_amount):
risk_per_unit = abs(entry_price - stop_price)
if risk_per_unit == 0:
return 0
return round(risk_amount / risk_per_unit, 3)

def calculate_sl_tp(df_15m, entry_price, direction):
atr = df_15m['ATR'].iloc[-1]
if direction == 'buy':
sl = entry_price - atr _ 1.5
tp = entry_price + atr _ 2
else:
sl = entry_price + atr _ 1.5
tp = entry_price - atr _ 2
return sl, tp
Краткое саммари: Мы устанавливаем риск на сделку в 5% и рассчитываем размер позиции таким образом, чтобы потери при срабатывании стоп-лосса были ограничены. Также уровни TP/SL рассчитываются относительно ATR для адаптации к волатильности.

Шаг 7. Выставление ордеров и сопровождение позиции
Что делаем:
– После подтверждения сигнала на всех таймфреймах вычисляем точку входа, рассчитываем SL/TP, проверяем возможность открытия позиции (по количеству и нотионалу) и вызываем функцию исполнения сделки.
– В режиме REAL_RUN функция enter_trade() (в файле trade_engine.py) выставляет ордера:

Лимитный ордер на TP1 (для 70% позиции),

Лимитный ордер на TP2 (для оставшейся части, если применимо),

Стоп-ордер (STOP_MARKET) на SL. – Если активированы дополнительные механизмы (Soft Exit, Break-Even, Trailing Stop), они запускаются в отдельных потоках для сопровождения открытой позиции.

Пример кода (trade_engine.py):

python
Copy
def enter_trade(symbol, direction, qty, entry_price, score, is_reentry=False): # Рассчитать уровни TP и SL
tp1_price = entry_price _ (1 + TP1_PERCENT) if direction == "buy" else entry_price _ (1 - TP1_PERCENT)
tp2_price = entry_price _ (1 + TP2_PERCENT) if direction == "buy" else entry_price _ (1 - TP2_PERCENT)
sl_price = entry_price _ (1 - SL_PERCENT) if direction == "buy" else entry_price _ (1 + SL_PERCENT)

    # Проверка минимального нотионала
    if qty * entry_price < MIN_NOTIONAL:
        log(f"{symbol} ⚠️ Notional too low: {qty*entry_price:.2f} USD", level="WARNING")
        return

    # Логирование входа
    log(f"{symbol} 🚀 Открытие {direction.upper()} позиции: Цена входа {entry_price:.4f}, "
        f"QTY {qty}, SL {sl_price:.4f}, TP1 {tp1_price:.4f}, TP2 {tp2_price:.4f}", level="INFO")

    # Отправка уведомления в Telegram (REAL_RUN)
    if not DRY_RUN:
        message = f"🚀 OPEN {direction.upper()} {symbol} @ {entry_price:.4f}\n" \
                  f"SL: {sl_price:.4f}, TP1: {tp1_price:.4f}, TP2: {tp2_price:.4f}"
        send_telegram_message(message, force=True)

    # Вызов API для выставления ордеров (пример использования safe_call_retry)
    if DRY_RUN:
        log(f"[DRY] Симуляция входа {symbol}: {direction.upper()} @ {entry_price:.4f}", level="INFO")
    else:
        # Пример для TP1
        safe_call_retry(exchange.create_limit_order, symbol, "sell" if direction=="buy" else "buy",
                        qty * TP1_SHARE, tp1_price, label=f"create_limit_order TP1 {symbol}")
        # Пример для TP2, если применимо
        if tp2_price and qty * TP2_SHARE > 0:
            safe_call_retry(exchange.create_limit_order, symbol, "sell" if direction=="buy" else "buy",
                            qty * TP2_SHARE, tp2_price, label=f"create_limit_order TP2 {symbol}")
        # Стоп-ордер
        safe_call_retry(exchange.create_order, symbol, "STOP_MARKET",
                        "sell" if direction=="buy" else "buy", qty,
                        params={"stopPrice": round(sl_price,4), "reduceOnly": True},
                        label=f"create_stop_order {symbol}")

Краткое саммари: Функция enter_trade выставляет ордера согласно рассчитанным уровням, используя безопасные вызовы к API, и запускает вспомогательные процессы для сопровождения позиции (Soft Exit, Trailing Stop, Break-Even).

Шаг 8. Основной цикл бота и логирование сделок
Что делаем:
– Собираем все этапы в единый цикл, который периодически (например, каждую минуту) обновляет данные, генерирует сигналы и, если условия выполнены, запускает вход в позицию.
– Логируем каждую сделку и отправляем уведомления через Telegram.

Пример кода (main.py):

python
Copy
import time
import pandas as pd
from strategy import fetch_data, calculate_indicators, get_trend, generate_signal, confirm_entry
from trade_engine import enter_trade
from utils_core import get_cached_balance
from utils_logging import log

# Список активных торговых пар (например, из config.py или динамически из pair_selector)

SYMBOLS_ACTIVE = ['BTC/USDC', 'ETH/USDC', 'ADA/USDC']

while True:
balance = get_cached_balance()
for symbol in SYMBOLS_ACTIVE:
df_1h = fetch_data(symbol, '1h', limit=100)
if not df_1h: continue
df_1h = calculate_indicators(df_1h, '1h')
trend = get_trend(df_1h) # 'bullish' или 'bearish'

        df_15m = fetch_data(symbol, '15m', limit=100)
        if not df_15m: continue
        df_15m = calculate_indicators(df_15m, '15m')
        direction = generate_signal(df_15m, trend, use_htf_confirmation=True)
        if direction is None:
            continue

        df_5m = fetch_data(symbol, '5m', limit=20)
        if not df_5m: continue
        df_5m = calculate_indicators(df_5m, '5m')
        if not confirm_entry(df_5m, direction):
            log(f"{symbol} ⏳ Вход не подтверждён на 5m", level="DEBUG")
            continue

        entry_price = df_5m["close"].iloc[-1]
        # Расчёт SL и TP на основе данных 15m
        sl, tp = calculate_sl_tp(df_15m, entry_price, direction)

        # Риск-менеджмент: расчет суммы риска (5% от баланса)
        risk_amount = balance * 0.05
        qty = calculate_position_size(entry_price, sl, risk_amount)

        # Проверка минимального нотионала
        if qty * entry_price < MIN_NOTIONAL:
            log(f"{symbol} ⚠️ Notional слишком мал: {qty*entry_price:.2f} USD", level="WARNING")
            continue

        # Вызов исполнения ордеров
        enter_trade(symbol, direction, qty, entry_price, score=5, is_reentry=False)

    time.sleep(60)  # Цикл повторяется каждую минуту

Краткое саммари: Основной цикл в main.py проходит по активным парам, обновляет данные, генерирует сигналы с использованием трёх таймфреймов и вызывает функцию enter_trade, если все условия выполнены. Логирование и уведомления помогут отслеживать работу бота в режиме реального времени.

Шаг 9. Масштабирование, контроль прибыли и дальнейшие улучшения
Что делаем:
– Для достижения цели (50 USD прибыли в день) необходимо увеличивать капитал после успешного тестового периода.
– Мониторьте статистику (win rate, PnL, drawdown) с помощью отчетов из stats.py и score_heatmap.py.
– Регулярно пересматривайте настройки (например, множитель ATR, пороги индикаторов) с учетом накопленной статистики через модули TP Optimizer.

Почему:
С увеличением капитала (например, до 600–1500 USD) бот сможет совершать сделки с более высоким объемом, а 5% риск на сделку обеспечит достаточную доходность (например, при 50 сделках в день, как расчеты показывают). Постоянный анализ и адаптация стратегии позволят поддерживать положительный результат даже при волатильном рынке.

Рекомендации по масштабированию:
– После тестового периода (1–2 недели) рассмотреть увеличение капитала: сначала до 500 USD, затем до 1,000 USD.
– Внести изменения в конфигурацию:

python
Copy

# config.py

RISK_PERCENT = 0.05
MAX_OPEN_POSITIONS = 3 # например, для более агрессивного режима
MIN_NOTIONAL = 2
– Использовать отчёты и оптимизаторы (tp_optimizer, tp_optimizer_ml) для регулярной корректировки параметров.

Шаг 10. Итог и мониторинг эффективности стратегии
Что делаем:
– Объединить всю логику в непрерывный рабочий процесс, реализовать систему логирования (entry_logger, tp_logger) и интегрировать уведомления через Telegram для критических событий (открытие, закрытие, срабатывание стоп-ордера, переключение стратегии). – Анализировать статистику: ежедневно и еженедельно формировать отчёты с данными о количестве сделок, win rate, PnL и эффективности каждого элемента стратегии.

Почему:
Постоянный мониторинг – ключ к стабильности. Если стратегия начинает работать не так, как ожидалось, по отчетам можно быстро скорректировать настройки.

Заключение
Резюме плана:

Данные и ликвидность: Загружаем данные для 1h, 15m, 5m и отсекаем неликвидные пары.

Индикаторы: Рассчитываем EMA, MACD, RSI, ATR для 15m и 1h; Stochastic RSI для 5m.

Тренд: Определяем глобальный тренд по 1h (EMA50 vs EMA200).

Сигнал: На 15m генерируем сигнал (buy/sell) с фильтрацией по MACD/RSI, дополнительно отсекая сигналы, противоречащие тренду.

Подтверждение: На 5m подтверждаем вход через Stochastic RSI.

Риск-менеджмент: Риск 5% от депозита, рассчитываем позицию, проверяем MIN_NOTIONAL.

Исполнение: Выставляем ордера (TP1, TP2, SL) с учетом авто-адаптации TP/SL на основе рыночного режима, а также включаем Soft Exit, Trailing Stop и Break-Even.

Основной цикл: Перебираем активные пары, регулярно обновляя данные и сигналы.

Масштабирование: По успешным тестам увеличиваем капитал и корректируем параметры, ориентируясь на достижение 50 USD прибыли в день.

Мониторинг и отчеты: Логируем каждую сделку, отправляем уведомления в Telegram и анализируем результаты для дальнейшей оптимизации.

Достижение целевой прибыли в 50 USD в день возможно при увеличении капитала до 600–1500 USD и уверенной работе стратегии, рассчитанной на 20–50 сделок в день, при условии стабильного win rate (50–55%) и хорошей адаптации параметров.
