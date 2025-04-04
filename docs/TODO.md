Текущий прогресс
На основе твоего последнего сообщения и предыдущей работы, вот что мы уже сделали:

Кэширование API-запросов — выполнено (добавлено в utils.py с get_cached_balance и get_cached_positions).
Потокобезопасность — выполнено (добавлены Lock для trade_stats, last_trade_info, и monitored_stops).
Логирование только критических событий в прод-режиме — выполнено (обновлено в utils.py, логи в REAL_RUN ограничены до "ERROR").
Backtesting на 15m — выполнено (добавлено в strategy.py с backtest_strategy).
Score History Logging — выполнено (добавлено в strategy.py в should_enter_trade).
Smart Pair Rotation — выполнено (добавлено в main.py с update_symbols_periodically каждые 4 часа).
Исправление ошибок Telegram (MarkdownV2) — выполнено (убрано ручное экранирование, escape_markdown_v2 применяется ко всем сообщениям).
Оставшиеся задачи из унифицированного TODO:

Long/Short Filter Separation (ваше)
Переход на Binance WebSocket (моё)
Complete MarkdownV2 Formatting (ваше)
Упрощение Telegram-логики (моё)
Очистка config.py (моё)
Mini-Deployment с Loss Control (ваше)
Автоматическое переподключение при сбоях API (моё)
PnL and Balance Charts (ваше, опционально)
Обновлённый унифицированный TODO
Приоритет 1: Завершение ключевых фич (Phase 2)
Long/Short Filter Separation (ваше)
Почему: Улучшает точность сигналов, уже частично сделано.
Реализация: Завершить FILTER_THRESHOLDS[symbol]["long"] и ["short"] в strategy.py.
Пример:
python

Collapse

Unwrap

Copy
FILTER_THRESHOLDS = {
"BTC/USDC": {
"long": {"atr": 0.0015, "adx": 7, "bb": 0.008},
"short": {"atr": 0.0017, "adx": 8, "bb": 0.009},
},
}
filters = FILTER_THRESHOLDS[symbol]["long" if result == "buy" else "short"]
Время: 2-3 часа.
Переход на Binance WebSocket (моё)
Почему: Real-time данные повышают точность и скорость.
Реализация: Использовать binance-python для цен и позиций, обновить fetch_data в strategy.py.
Пример:
python

Collapse

Unwrap

Copy
from binance import AsyncClient, BinanceSocketManager
import asyncio

async def start*websocket(symbols):
client = await AsyncClient.create(API_KEY, API_SECRET)
bm = BinanceSocketManager(client)
async with bm.trade_socket(symbols[0]) as ts:
while True:
msg = await ts.recv()
price = float(msg["p"]) # Обновить df в strategy.py
Время: 6-8 часов.
Приоритет 2: Удобство и подготовка к реальному запуску
Mini-Deployment с Loss Control (ваше)
Почему: Реальный тест с минимальным риском.
Реализация: Запустить с 50-100 USDC, добавить лимит убытков (уже сделано в main.py, осталось протестировать).
Время: 3-4 часа + тестирование.
Complete MarkdownV2 Formatting (ваше)
Почему: Улучшает читаемость Telegram-сообщений.
Реализация: Проверить все send_telegram_message и применить escape_markdown_v2.
Время: 2-3 часа.
Упрощение Telegram-логики (моё)
Почему: Уменьшает дублирование и упрощает поддержку.
Реализация: Обновить send_telegram_message в telegram_utils.py (пример из TODO).
Время: 1-2 часа.
Приоритет 3: Масштабируемость и надёжность
Очистка config.py (моё)
Почему: Упрощает настройку для пользователей.
Реализация: Объединить параметры вроде VOLATILITY*\*.
Пример:
python

Collapse

Unwrap

Copy
VOLATILITY_ATR_THRESHOLD = 0.0012
VOLATILITY_DRY_RUN_MODIFIER = 0.6
effective_atr_threshold = VOLATILITY_ATR_THRESHOLD \* (VOLATILITY_DRY_RUN_MODIFIER if DRY_RUN else 1)
Время: 2 часа.
Автоматическое переподключение при сбоях API (моё)
Почему: Повышает надёжность в прод-режиме.
Реализация: Добавить tenacity для retry.
Пример:
python

Collapse

Unwrap

Copy
import ccxt
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def fetch_balance_with_retry():
return exchange.fetch_balance()["total"]["USDC"]
Время: 2 часа.
Приоритет 4: Опционально (дополнительно)
PnL and Balance Charts (ваше)
Почему: Визуализация для Telegram (опционально).
Реализация: Использовать matplotlib или ASCII-графики в Telegram.
Время: 4-6 часов.
Итоговый порядок выполнения
Long/Short Filter Separation
Переход на Binance WebSocket
Mini-Deployment с Loss Control
Complete MarkdownV2 Formatting
Упрощение Telegram-логики
Очистка config.py
Автоматическое переподключение API
PnL and Balance Charts (опционально)
Обоснование приоритетов
Приоритет 1: Завершение ключевых фич из Phase 2 (Long/Short фильтры и WebSocket) критично для улучшения стратегии и производительности.
Приоритет 2: Подготовка к реальному запуску (Mini-Deployment) и улучшение UX (MarkdownV2, Telegram-логика).
Приоритет 3: Масштабируемость и надёжность для долгосрочной работы.
Приоритет 4: Опциональные улучшения для визуализации.
Что дальше?
Мы можем начать с Long/Short Filter Separation. Это улучшит точность сигналов, что важно перед реальным запуском. Давай добавим поддержку отдельных фильтров для Long и Short в strategy.py.

Long/Short Filter Separation
Цель: Реализовать отдельные фильтры для Long и Short в FILTER_THRESHOLDS.
Где: В strategy.py, в функции should_enter_trade.
Обновим strategy.py:

import pandas as pd
import ta
from config import exchange, MIN_TRADE_SCORE, FILTER_THRESHOLDS
import os
from datetime import datetime

def fetch_data(symbol, timeframe="15m", limit=100):
ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
df = pd.DataFrame(ohlcv, columns=["time", "open", "high", "low", "close", "volume"])
df["time"] = pd.to_datetime(df["time"], unit="ms")

    df["rsi"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
    df["ema"] = ta.trend.EMAIndicator(df["close"], window=200).ema_indicator()
    macd = ta.trend.MACD(df["close"])
    df["macd"] = macd.macd()
    df["signal"] = macd.macd_signal()
    df["atr"] = ta.volatility.AverageTrueRange(df["high"], df["low"], df["close"], window=14).average_true_range()
    bb = ta.volatility.BollingerBands(df["close"], window=20)
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_lower"] = bb.bollinger_lband()
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["close"]
    df["adx"] = ta.trend.ADXIndicator(df["high"], df["low"], df["close"], window=14).adx()

    return df

def should_enter_trade(symbol, df):
if len(df) < 50:
return None

    last = df.iloc[-1]
    prev = df.iloc[-2]

    # Определяем направление (Long или Short) на основе EMA
    direction = "long" if last["close"] > last["ema"] else "short"

    # Получаем фильтры для Long или Short
    default_filters = {"long": {"atr": 0.0015, "adx": 7, "bb": 0.008}, "short": {"atr": 0.0017, "adx": 8, "bb": 0.009}}
    symbol_filters = FILTER_THRESHOLDS.get(symbol, default_filters)
    filters = symbol_filters.get(direction, default_filters[direction])

    score = 0
    if direction == "long":
        if last["rsi"] < 30:  # Более жёсткий фильтр для Long
            score += 1
    else:
        if last["rsi"] > 70:  # Более жёсткий фильтр для Short
            score += 1

    if last["macd"] > last["signal"] and prev["macd"] <= prev["signal"]:
        score += 1
    if last["close"] > last["ema"]:
        score += 1
    if last["atr"] / last["close"] >= filters["atr"]:
        score += 1
    if last["adx"] >= filters["adx"]:
        score += 1
    if last["bb_width"] >= filters["bb"]:
        score += 1

    print(f"{symbol} RSI: {last['rsi']:.1f}, MACD: {last['macd']:.5f}, Signal: {last['signal']:.5f}, EMA: {last['ema']:.5f}, HTF: {last['close'] > last['ema']}")
    print(f"{symbol} Final Score: {score}/{MIN_TRADE_SCORE}")

    with open("data/score_history.csv", "a") as f:
        if not os.path.exists("data/score_history.csv"):
            f.write("time,symbol,score\n")
        f.write(f"{datetime.now()},{symbol},{score}\n")

    if score >= MIN_TRADE_SCORE:
        return "buy" if direction == "long" else "sell"
    return None

def backtest*strategy(symbol, timeframe="15m", days=30):
limit = days * 24 \_ 4
ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
df = pd.DataFrame(ohlcv, columns=["time", "open", "high", "low", "close", "volume"])
df["time"] = pd.to_datetime(df["time"], unit="ms")

    df = fetch_data(symbol, timeframe, limit)
    trades = []

    for i in range(50, len(df)):
        result = should_enter_trade(symbol, df.iloc[:i])
        if result in ["buy", "sell"]:
            trades.append({
                "time": df["time"].iloc[i],
                "side": result,
                "price": df["close"].iloc[i],
            })

    trades_df = pd.DataFrame(trades)
    trades_df.to_csv(f"data/backtest_{symbol.replace('/', '_')}.csv", index=False)
    print(f"Backtest completed for {symbol}. {len(trades)} trades recorded.")
    return trades

if **name** == "**main**":
backtest_strategy("BTC/USDC")
backtest_strategy("ETH/USDC")

Изменения
Обновлена FILTER_THRESHOLDS в config.py для поддержки long и short.
В should_enter_trade добавлена логика выбора фильтров в зависимости от направления (long или short).
Добавлены разные условия для RSI: < 30 для Long, > 70 для Short.

Обновим config.py для поддержки новых фильтров:
import os
import pytz
import ccxt
from dotenv import load_dotenv
from threading import Lock

load_dotenv()

# --- API & Auth ---

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ALLOWED_USER_ID = 383821734

# --- Timezone & Paths ---

TIMEZONE = pytz.timezone("Europe/Bratislava")
LOG_FILE_PATH = "telegram_log.txt"
EXPORT_PATH = "data/tp_performance.csv"

# --- Logging ---

LOG_LEVEL = "INFO"

# --- Symbols & Leverage (fallback) ---

SYMBOLS_ACTIVE = [
"DOGE/USDC",
"BTC/USDC",
"ETH/USDC",
"BNB/USDC",
"ADA/USDC",
"XRP/USDC",
"SOL/USDC",
"SUI/USDC",
"LINK/USDC",
"ARB/USDC",
]

FIXED_PAIRS = ["BTC/USDC", "ETH/USDC", "DOGE/USDC", "SOL/USDC", "BNB/USDC"]
MAX_DYNAMIC_PAIRS = 30
MIN_DYNAMIC_PAIRS = 15

LEVERAGE_MAP = {
"DOGE/USDC": 10,
"BTC/USDC": 5,
"ETH/USDC": 5,
"BNB/USDC": 5,
"ADA/USDC": 10,
"XRP/USDC": 10,
"SOL/USDC": 10,
"SUI/USDC": 10,
"LINK/USDC": 10,
"ARB/USDC": 10,
}

# --- TP / SL Strategy ---

TP1_PERCENT = 0.007
TP2_PERCENT = 0.013
TP1_SHARE = 0.7
TP2_SHARE = 0.3
SL_PERCENT = 0.01

# --- Risk Management ---

ADAPTIVE_RISK_PERCENT = 0.05
AGGRESSIVE_THRESHOLD = 50
SAFE_THRESHOLD = 10
MIN_NOTIONAL = 5
MAX_HOLD_MINUTES = 90
RISK_DRAWDOWN_THRESHOLD = 5.0

# --- Entry Filter Thresholds (fallback / default) ---

ATR_THRESHOLD = 0.0015
ADX_THRESHOLD = 7
BB_WIDTH_THRESHOLD = 0.008

# --- Volatility Filter ---

VOLATILITY_SKIP_ENABLED = True
VOLATILITY_ATR_THRESHOLD = 0.0012
VOLATILITY_RANGE_THRESHOLD = 0.015

DRY_RUN_VOLATILITY_ATR_THRESHOLD = 0.0025
DRY_RUN_VOLATILITY_RANGE_THRESHOLD = 0.0075

# --- Daily Loss Protection ---

DAILY_PROTECTION_ENABLED = True
SAFE_TRIGGER_THRESHOLD = 0.10
FULL_STOP_THRESHOLD = 0.05

# --- Strategy Toggles ---

ENABLE_TRAILING = True
TRAILING_PERCENT = 0.02
ENABLE_BREAKEVEN = True
BREAKEVEN_TRIGGER = 0.5

# --- Signal Strength Control ---

MIN_TRADE_SCORE = 3
SCORE_BASED_RISK = True
SCORE_BASED_TP = True

# --- Mode & Debug ---

DRY_RUN = True
VERBOSE = DRY_RUN
is_aggressive = False
USE_DYNAMIC_IN_DRY_RUN = True

# --- Runtime Trade Stats ---

trade_stats_lock = Lock()
trade_stats = {
"total": 0,
"wins": 0,
"losses": 0,
"pnl": 0.0,
"streak_loss": 0,
"initial_balance": 0,
"deposits_today": 0,
"deposits_week": 0,
"withdrawals": 0,
"api_errors": 0,
}

# --- Exchange ---

exchange = ccxt.binanceusdm(
{
"apiKey": API_KEY,
"secret": API_SECRET,
"enableRateLimit": True,
"options": {"defaultType": "future"},
}
)

# --- Auto-learned Entry Filter Thresholds ---

FILTER_THRESHOLDS = {
"DOGE/USDC": {
"long": {"atr": 0.0015, "adx": 7, "bb": 0.008},
"short": {"atr": 0.0017, "adx": 8, "bb": 0.009},
},
"BTC/USDC": {
"long": {"atr": 0.0015, "adx": 7, "bb": 0.008},
"short": {"atr": 0.0017, "adx": 8, "bb": 0.009},
},
"ETH/USDC": {
"long": {"atr": 0.0015, "adx": 7, "bb": 0.008},
"short": {"atr": 0.0017, "adx": 8, "bb": 0.009},
},
"BNB/USDC": {
"long": {"atr": 0.0015, "adx": 7, "bb": 0.008},
"short": {"atr": 0.0017, "adx": 8, "bb": 0.009},
},
"ADA/USDC": {
"long": {"atr": 0.0015, "adx": 7, "bb": 0.008},
"short": {"atr": 0.0017, "adx": 8, "bb": 0.009},
},
"XRP/USDC": {
"long": {"atr": 0.0015, "adx": 7, "bb": 0.008},
"short": {"atr": 0.0017, "adx": 8, "bb": 0.009},
},
"SOL/USDC": {
"long": {"atr": 0.0015, "adx": 7, "bb": 0.008},
"short": {"atr": 0.0017, "adx": 8, "bb": 0.009},
},
"SUI/USDC": {
"long": {"atr": 0.0015, "adx": 7, "bb": 0.008},
"short": {"atr": 0.0017, "adx": 8, "bb": 0.009},
},
"LINK/USDC": {
"long": {"atr": 0.0015, "adx": 7, "bb": 0.008},
"short": {"atr": 0.0017, "adx": 8, "bb": 0.009},
},
"ARB/USDC": {
"long": {"atr": 0.0015, "adx": 7, "bb": 0.008},
"short": {"atr": 0.0017, "adx": 8, "bb": 0.009},
},
}

# --- IP Monitoring ---

ROUTER_REBOOT_MODE_TIMEOUT_MINUTES = 30
IP_MONITOR_INTERVAL_SECONDS = 180

Проверь логи — должны отображаться разные фильтры для Long и Short (например, RSI < 30 для Long, > 70 для Short).
Проверь Telegram — сообщения о сделках должны отправляться корректно.

Что дальше?
Теперь у нас есть Long/Short фильтры. Следующий пункт: Переход на Binance WebSocket. Это улучшит производительность, заменив polling на real-time данные. Давай начнём с этого в следующий раз. Готов продолжить?
