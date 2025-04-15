Ключевые моменты
Исследования показывают, что предложенные доработки (шаг 3: объединение last_trade_times, шаг 4: масштабирование TP/SL, шаг 5: учет комиссий в PnL, шаг 6: переход на JSON для TP-оптимизатора, плюс мелкие улучшения) реализуемы с минимальными рисками при последовательном внедрении и тестировании.
Кажется вероятным, что изменения улучшат модульность, отладку и гибкость стратегии, сохраняя текущую стабильность бота (v1.6.4).
Доказательства склоняются к тому, что шаги можно внедрить за 1-2 недели, начиная с низкорисковых изменений, с последующим тестированием в DRY_RUN.
Финальный план внедрения шагов 3-6 и мелких улучшений
Обзор
План включает последовательное внедрение шагов 3-6 из Roadmap v1.6.4, а также предложенные мелкие доработки (перемещение get_market_regime(), отладочные логи, настройка TP2). Каждый шаг сопровождается полным кодом, пояснениями и рекомендациями по тестированию. Цель — улучшить организацию кода, отладку и гибкость стратегии, минимизируя риски.

Общие рекомендации
Порядок внедрения: Начинайте с низкорисковых шагов (3, 6, мелкие улучшения), затем переходите к шагам 4 и 5, завершая стратегической доработкой (TP2).
Тестирование: После каждого шага запускайте бот в DRY_RUN=True минимум 1-2 дня, проверяя логи и функциональность.
Резервное копирование: Сохраните текущую версию кода перед внесением изменений.
Пошаговый план с кодом и пояснениями
Шаг 1: Перемещение get_market_regime() в volatility_tools.py (Мелкое улучшение)
Описание:

Перемещаем функцию get_market_regime() из trade_engine.py в новый модуль volatility_tools.py, чтобы улучшить организацию кода и упростить масштабирование.

Код:

Создание volatility_tools.py:
python

Copy

# volatility_tools.py

import pandas as pd
import ta
from utils_logging import log
from config import ADX_FLAT_THRESHOLD, ADX_TREND_THRESHOLD

def get_market_regime(symbol, exchange):
try:
ohlcv = exchange.fetch_ohlcv(symbol, timeframe="15m", limit=50)
if len(ohlcv) < 14:
return "neutral", 1.0

        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        closes = [c[4] for c in ohlcv]
        df = pd.DataFrame({"high": highs, "low": lows, "close": closes})
        adx = ta.trend.ADXIndicator(df["high"], df["low"], df["close"], window=14).adx().iloc[-1]

        if adx > ADX_TREND_THRESHOLD:
            regime = "trend"
            scaling_factor = min(adx / 50, 1.5)
        elif adx < ADX_FLAT_THRESHOLD:
            regime = "flat"
            scaling_factor = max(0.5, 1 - (ADX_FLAT_THRESHOLD - adx) / ADX_FLAT_THRESHOLD)
        else:
            regime = "neutral"
            scaling_factor = 1.0
        return regime, scaling_factor
    except Exception as e:
        log(f"Failed to determine market regime for {symbol}: {e}", level="ERROR")
        return "neutral", 1.0

Обновление trade_engine.py:
Удаляем get_market_regime() и обновляем импорты.
python

Copy

# trade_engine.py

import threading
import time

import pandas as pd
import ta

from config import (
ADX_FLAT_THRESHOLD,
ADX_TREND_THRESHOLD,
AGGRESSIVENESS_THRESHOLD,
AUTO_TP_SL_ENABLED,
BREAKEVEN_TRIGGER,
DRY_RUN,
ENABLE_BREAKEVEN,
ENABLE_TRAILING,
MIN_NOTIONAL,
SL_PERCENT,
SOFT_EXIT_ENABLED,
SOFT_EXIT_SHARE,
SOFT_EXIT_THRESHOLD,
TAKER_FEE_RATE,
TP1_PERCENT,
TP2_PERCENT,
exchange,
)
from core.aggressiveness_controller import get_aggressiveness_score
from core.tp_utils import calculate_tp_levels
from volatility_tools import get_market_regime # Новый импорт
from telegram.telegram_utils import send_telegram_message
from tp_logger import log_trade_result
from utils_core import get_cached_positions, load_state, safe_call_retry
from utils_logging import log, now

# ... (удаляем get_market_regime)

def enter_trade(symbol, side, qty, score=5, is_reentry=False): # ... (предыдущий код)
regime, scaling_factor = get_market_regime(symbol, exchange) # ... (остальной код)
Обновление strategy.py:
Обновляем импорт get_market_regime.
python

Copy

# strategy.py

import threading
from datetime import datetime

import pandas as pd
import ta

from config import (
AUTO_TP_SL_ENABLED,
DRY_RUN,
FILTER_THRESHOLDS,
LEVERAGE_MAP,
SL_PERCENT,
TAKER_FEE_RATE,
VOLATILITY_ATR_THRESHOLD,
VOLATILITY_RANGE_THRESHOLD,
VOLATILITY_SKIP_ENABLED,
exchange,
get_min_net_profit,
)
from core.order_utils import calculate_order_quantity
from core.score_evaluator import calculate_score, get_adaptive_min_score
from core.score_logger import log_score_history
from core.trade_engine import get_position_size, trade_manager
from core.tp_utils import calculate_tp_levels
from core.volatility_controller import get_volatility_filters
from volatility_tools import get_market_regime # Новый импорт
from telegram.telegram_utils import send_telegram_message
from tp_logger import get_trade_stats
from utils_core import get_adaptive_risk_percent, get_cached_balance, safe_call_retry
from utils_logging import log

# ... (остальной код)

Пояснение:

Перемещение функции улучшает модульность, делая код более организованным. Это также упрощает добавление новых функций, связанных с волатильностью, в будущем.

Тестирование:

Проверьте, что regime и scaling_factor корректно определяются в DRY_RUN.
Убедитесь, что TP/SL масштабируются так же, как раньше.
Риски: Минимальные. Возможны ошибки в импортах, но легко исправляются.

Шаг 2: Объединение last_trade_times в TradeInfoManager (Шаг 3)
Описание:

Переносим управление last_trade_times из strategy.py в TradeInfoManager, чтобы централизовать логику Smart Re-entry.

Код:

Обновление TradeInfoManager в trade_engine.py:
Добавляем методы для работы с last_trade_times.
python

Copy

# trade_engine.py

class TradeInfoManager:
def **init**(self):
self.\_trades = {}
self.\_last_trade_times = {} # Новый словарь
self.\_lock = threading.Lock()

    def add_trade(self, symbol, trade_data):
        with self._lock:
            self._trades[symbol] = trade_data

    def get_trade(self, symbol):
        with self._lock:
            return self._trades.get(symbol)

    def update_trade(self, symbol, key, value):
        with self._lock:
            if symbol in self._trades:
                self._trades[symbol][key] = value

    def remove_trade(self, symbol):
        with self._lock:
            return self._trades.pop(symbol, None)

    def get_last_score(self, symbol):
        with self._lock:
            return self._trades.get(symbol, {}).get("score", 0)

    def get_last_closed_time(self, symbol):
        with self._lock:
            return self._trades.get(symbol, {}).get("last_closed_time", None)

    def set_last_closed_time(self, symbol, timestamp):
        with self._lock:
            if symbol not in self._trades:
                self._trades[symbol] = {}
            self._trades[symbol]["last_closed_time"] = timestamp

    def set_last_trade_time(self, symbol, timestamp):
        with self._lock:
            self._last_trade_times[symbol] = timestamp

    def get_last_trade_time(self, symbol):
        with self._lock:
            return self._last_trade_times.get(symbol)

Обновление strategy.py:
Удаляем last_trade_times и используем trade_manager.
python

Copy

# strategy.py

import threading
from datetime import datetime

import pandas as pd
import ta

from config import (
AUTO_TP_SL_ENABLED,
DRY_RUN,
FILTER_THRESHOLDS,
LEVERAGE_MAP,
SL_PERCENT,
TAKER_FEE_RATE,
VOLATILITY_ATR_THRESHOLD,
VOLATILITY_RANGE_THRESHOLD,
VOLATILITY_SKIP_ENABLED,
exchange,
get_min_net_profit,
)
from core.order_utils import calculate_order_quantity
from core.score_evaluator import calculate_score, get_adaptive_min_score
from core.score_logger import log_score_history
from core.trade_engine import get_position_size, trade_manager
from core.tp_utils import calculate_tp_levels
from core.volatility_controller import get_volatility_filters
from volatility_tools import get_market_regime
from telegram.telegram_utils import send_telegram_message
from tp_logger import get_trade_stats
from utils_core import get_adaptive_risk_percent, get_cached_balance, safe_call_retry
from utils_logging import log

last_trade_times_lock = threading.Lock()

def fetch_data(symbol, tf="15m"):
try:
data = safe_call_retry(
exchange.fetch_ohlcv, symbol, timeframe=tf, limit=50, label=f"fetch_ohlcv {symbol}"
)
if not data:
log(f"No data returned for {symbol} on timeframe {tf}", level="ERROR")
return None
df = pd.DataFrame(
data,
columns=["time", "open", "high", "low", "close", "volume"],
)
if df.empty:
log(f"Empty DataFrame for {symbol} on timeframe {tf}", level="ERROR")
return None
if len(df) < 14:
log(f"Not enough data for {symbol} on timeframe {tf} (rows: {len(df)})", level="ERROR")
return None
df["rsi"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
df["ema"] = ta.trend.EMAIndicator(df["close"], window=20).ema_indicator()
df["macd"] = ta.trend.MACD(df["close"]).macd()
df["macd_signal"] = ta.trend.MACD(df["close"]).macd_signal()
df["atr"] = ta.volatility.AverageTrueRange(
df["high"], df["low"], df["close"], window=14
).average_true_range()
df["fast_ema"] = ta.trend.EMAIndicator(df["close"], window=9).ema_indicator()
df["slow_ema"] = ta.trend.EMAIndicator(df["close"], window=21).ema_indicator()
df["adx"] = ta.trend.ADXIndicator(df["high"], df["low"], df["close"], window=14).adx()
bb = ta.volatility.BollingerBands(df["close"], window=20)
df["bb_width"] = bb.bollinger_hband() - bb.bollinger_lband()
return df
except Exception as e:
log(f"Error fetching data for {symbol}: {e}", level="ERROR")
return None

def get_htf_trend(symbol, tf="1h"):
df_htf = fetch_data(symbol, tf=tf)
if df_htf is None:
return False
return df_htf["close"].iloc[-1] > df_htf["ema"].iloc[-1]

def passes_filters(df, symbol):
balance = get_cached_balance()
filter_mode = "default_light" if balance < 100 else "default"
base_filters = FILTER_THRESHOLDS.get(symbol, FILTER_THRESHOLDS[filter_mode])

    filters = get_volatility_filters(symbol, base_filters)
    relax_factor = filters["relax_factor"]

    if DRY_RUN:
        filters["atr"] *= 0.6
        filters["adx"] *= 0.6
        filters["bb"] *= 0.6

    price = df["close"].iloc[-1]
    atr = df["atr"].iloc[-1] / price
    adx = df["adx"].iloc[-1]
    bb_width = df["bb_width"].iloc[-1] / price

    if atr < filters["atr"]:
        log(
            f"{symbol} ⛔️ Rejected: ATR {atr:.5f} < {filters['atr']} (relax={relax_factor})",
            level="DEBUG",
        )
        return False
    if adx < filters["adx"]:
        log(
            f"{symbol} ⛔️ Rejected: ADX {adx:.2f} < {filters['adx']} (relax={relax_factor})",
            level="DEBUG",
        )
        return False
    if bb_width < filters["bb"]:
        log(
            f"{symbol} ⛔️ Rejected: BB Width {bb_width:.5f} < {filters['bb']} (relax={relax_factor})",
            level="DEBUG",
        )
        return False
    return True

def should_enter_trade(symbol, df, exchange, last_trade_times_lock):
if df is None:
log(f"Skipping {symbol} due to data fetch error", level="WARNING")
return None

    utc_now = datetime.utcnow()
    balance = get_cached_balance()
    position_size = get_position_size(symbol)
    has_long_position = position_size > 0
    has_short_position = position_size < 0
    available_margin = balance * 0.1

    with last_trade_times_lock:
        last_time = trade_manager.get_last_trade_time(symbol)
        cooldown = 30 * 60  # 30 минут
        elapsed = utc_now.timestamp() - last_time.timestamp() if last_time else float("inf")
        if elapsed < cooldown:
            if DRY_RUN:
                log(f"{symbol} ⏳ Ignored due to cooldown")
            return None

    if VOLATILITY_SKIP_ENABLED:
        price = df["close"].iloc[-1]
        high = df["high"].iloc[-1]
        low = df["low"].iloc[-1]
        atr = df["atr"].iloc[-1] / price
        range_ratio = (high - low) / price
        if atr < VOLATILITY_ATR_THRESHOLD and range_ratio < VOLATILITY_RANGE_THRESHOLD:
            if DRY_RUN:
                log(
                    f"{symbol} ⛔️ Rejected: low volatility (ATR: {atr:.5f}, Range: {range_ratio:.5f})"
                )
            return None

    if not passes_filters(df, symbol):
        return None

    trade_count, winrate = get_trade_stats()
    score = calculate_score(df, symbol, trade_count, winrate)
    min_required = get_adaptive_min_score(trade_count, winrate)

    if DRY_RUN:
        min_required *= 0.3
        log(f"{symbol} 🔎 Final Score: {score:.2f} / (Required: {min_required:.4f})")

    if has_long_position or has_short_position or available_margin < 10:
        score -= 0.5

    direction = "BUY" if df["macd"].iloc[-1] > df["macd_signal"].iloc[-1] else "SELL"

    # Проверка чистой прибыли
    entry_price = df["close"].iloc[-1]
    stop_price = (
        entry_price * (1 - SL_PERCENT) if direction == "BUY" else entry_price * (1 + SL_PERCENT)
    )
    risk_percent = get_adaptive_risk_percent(balance)
    qty = calculate_order_quantity(entry_price, stop_price, balance, risk_percent)

    # Проверка номинальной стоимости с учетом плеча
    leverage = LEVERAGE_MAP.get(symbol, 5)
    max_notional = balance * leverage
    notional = qty * entry_price
    if notional > max_notional:
        log(
            f"{symbol} ⛔️ Rejected: Notional {notional:.2f} exceeds max {max_notional:.2f} with leverage {leverage}x (balance: {balance:.2f})",
            level="DEBUG",
        )
        return None

    # Расчет чистой прибыли на TP1
    regime, scaling_factor = get_market_regime(symbol, exchange) if AUTO_TP_SL_ENABLED else (None, 1.0)
    tp1_price, _, _, qty_tp1_share, _ = calculate_tp_levels(entry_price, direction, symbol, regime, score, scaling_factor)

    # Проверка на нулевое значение qty_tp1_share
    if qty_tp1_share == 0:
        log(f"{symbol} ⛔️ Rejected: qty_tp1_share is 0", level="DEBUG")
        return None

    qty_tp1 = qty * qty_tp1_share
    gross_profit_tp1 = qty_tp1 * abs(tp1_price - entry_price)
    commission = 2 * (qty * entry_price * TAKER_FEE_RATE)
    net_profit_tp1 = gross_profit_tp1 - commission

    # Проверка минимального порога прибыли
    min_target_pnl = get_min_net_profit(balance)
    log(
        f"[{symbol}] Qty={qty:.4f}, Entry={entry_price:.4f}, TP1={tp1_price:.4f}, ExpPnl=${net_profit_tp1:.3f}, Min=${min_target_pnl:.3f}",
        level="DEBUG",
    )
    if net_profit_tp1 < min_target_pnl:
        log(
            f"⚠️ Skipping {symbol} — expected PnL ${net_profit_tp1:.2f} < min ${min_target_pnl:.2f}",
            level="DEBUG",
        )
        return None

    # Smart Re-entry Logic
    with last_trade_times_lock:
        last_time = trade_manager.get_last_trade_time(symbol)
        now = utc_now.timestamp()
        elapsed = now - last_time.timestamp() if last_time else float("inf")

        last_closed_time = trade_manager.get_last_closed_time(symbol)
        closed_elapsed = now - last_closed_time if last_closed_time else float("inf")
        last_score = trade_manager.get_last_score(symbol)

        if (elapsed < cooldown or closed_elapsed < cooldown) and position_size == 0:
            if score <= 4:
                log(f"Skipping {symbol}: cooldown active, score {score:.2f} <= 4", level="DEBUG")
                return None
            direction = "BUY" if df["macd"].iloc[-1] > df["macd_signal"].iloc[-1] else "SELL"
            log(
                f"{symbol} 🔍 Generated signal: {direction}, MACD: {df['macd'].iloc[-1]:.5f}, Signal: {df['macd_signal'].iloc[-1]:.5f}",
                level="DEBUG",
            )
            trade_manager.set_last_trade_time(symbol, utc_now)
            if not DRY_RUN:
                log_score_history(symbol, score)
                log(f"{symbol} ✅ Re-entry {direction} signal triggered (score: {score:.2f}/5)")
            else:
                msg = f"🧪-DRY-RUN-REENTRY-{symbol}-{direction}-Score-{score:.2f}-of-5"
                send_telegram_message(msg, force=True, parse_mode="")
            return ("buy" if direction == "BUY" else "sell", score, True)

        if last_score and score - last_score >= 1.5 and position_size == 0:
            direction = "BUY" if df["macd"].iloc[-1] > df["macd_signal"].iloc[-1] else "SELL"
            log(
                f"{symbol} 🔍 Generated signal: {direction}, MACD: {df['macd'].iloc[-1]:.5f}, Signal: {df['macd_signal'].iloc[-1]:.5f}",
                level="DEBUG",
            )
            trade_manager.set_last_trade_time(symbol, utc_now)
            if not DRY_RUN:
                log_score_history(symbol, score)
                log(f"{symbol} ✅ Re-entry {direction} signal triggered (score: {score:.2f}/5)")
            else:
                msg = f"🧪-DRY-RUN-REENTRY-{symbol}-{direction}-Score-{score:.2f}-of-5"
                send_telegram_message(msg, force=True, parse_mode="")
            return ("buy" if direction == "BUY" else "sell", score, True)

        # Обычный вход
        if score < min_required:
            if DRY_RUN:
                log(
                    f"{symbol} ❌ No entry: insufficient score\n"
                    f"Final Score: {score:.2f} / (Required: {min_required:.4f})"
                )
            return None

    with last_trade_times_lock:
        trade_manager.set_last_trade_time(symbol, utc_now)

    direction = "BUY" if df["macd"].iloc[-1] > df["macd_signal"].iloc[-1] else "SELL"
    log(
        f"{symbol} 🔍 Generated signal: {direction}, MACD: {df['macd'].iloc[-1]:.5f}, Signal: {df['macd_signal'].iloc[-1]:.5f}",
        level="DEBUG",
    )
    if not DRY_RUN:
        log_score_history(symbol, score)
        log(f"{symbol} ✅ {direction} signal triggered (score: {score:.2f}/5)")
    else:
        msg = f"🧪-DRY-RUN-{symbol}-{direction}-Score-{score:.2f}-of-5"
        send_telegram_message(msg, force=True, parse_mode="")

    return ("buy" if direction == "BUY" else "sell", score, False)

Пояснение:

Централизация управления временем сделок в TradeInfoManager упрощает код, снижая риск рассинхронизации. Потокобезопасность обеспечивается через Lock.

Тестирование:

Проверьте, что Smart Re-entry работает корректно: cooldown (30 минут) соблюдается, повторный вход срабатывает при score > 4 или росте скора на 1.5.
Убедитесь, что логи отражают правильные временные метки.
Риски: Минимальные, так как это рефакторинг без изменения логики.

Шаг 3: Масштабирование TP/SL по тренду (Шаг 4)
Описание:

Улучшаем масштабирование TP/SL, используя scaling_factor из get_market_regime() для адаптации к силе тренда.

Код:

Обновление tp_utils.py:
Учитываем scaling_factor при расчете TP/SL.
python

Copy

# tp_utils.py

import json
from config import AUTO_TP_SL_ENABLED, FLAT_ADJUSTMENT, SL_PERCENT, TP1_PERCENT, TP2_PERCENT, TP1_SHARE, TP2_SHARE, TREND_ADJUSTMENT, CONFIG_DYNAMIC_FILE
from utils_logging import log

def calculate_tp_levels(entry_price: float, side: str, symbol: str, regime: str = None, score: float = 5, scaling_factor: float = 1.0, atr: float = None, price: float = None):
"""
Вычисляет цены TP1, TP2 и SL на основе цены входа, стороны, режима рынка и волатильности (ATR).
"""
try:
with open(CONFIG_DYNAMIC_FILE, "r") as f:
config_data = json.load(f)
if symbol in config_data:
tp1_pct = config_data[symbol]["tp1"]
tp2_pct = config_data[symbol]["tp2"]
log(f"{symbol} using TP1={tp1_pct}, TP2={tp2_pct} (source: dynamic)", level="DEBUG")
else:
tp1_pct = TP1_PERCENT
tp2_pct = TP2_PERCENT
log(f"{symbol} using TP1={tp1_pct}, TP2={tp2_pct} (source: default)", level="DEBUG")
except Exception as e:
log(f"Failed to load dynamic config for {symbol}: {e}", level="WARNING")
tp1_pct = TP1_PERCENT
tp2_pct = TP2_PERCENT
log(f"{symbol} using TP1={tp1_pct}, TP2={tp2_pct} (source: default, error)", level="DEBUG")

    # Адаптация SL на основе ATR (если передано)
    sl_pct = SL_PERCENT
    if atr is not None and price is not None:
        atr_ratio = atr / price
        if atr_ratio > 0.002:
            sl_pct *= 1.5
        elif atr_ratio < 0.001:
            sl_pct *= 0.5

    # Масштабирование TP/SL по тренду
    tp1_pct *= scaling_factor
    tp2_pct = tp2_pct * scaling_factor if tp2_pct else None
    sl_pct *= scaling_factor

    if AUTO_TP_SL_ENABLED and regime:
        if regime == "flat":
            tp1_pct *= FLAT_ADJUSTMENT
            tp2_pct = tp2_pct * FLAT_ADJUSTMENT if tp2_pct else None
            sl_pct *= FLAT_ADJUSTMENT
        elif regime == "trend":
            tp2_pct = tp2_pct * TREND_ADJUSTMENT if tp2_pct else None
            sl_pct *= TREND_ADJUSTMENT

    if score == 3:
        tp1_pct *= 0.8
        tp2_pct = None
        sl_pct *= 0.8

    if side.lower() == "buy":
        tp1_price = entry_price * (1 + tp1_pct)
        tp2_price = entry_price * (1 + tp2_pct) if tp2_pct else None
        sl_price = entry_price * (1 - sl_pct)
    else:  # side == "sell"
        tp1_price = entry_price * (1 - tp1_pct)
        tp2_price = entry_price * (1 - tp2_pct) if tp2_pct else None
        sl_price = entry_price * (1 + sl_pct)

    qty_tp1 = TP1_SHARE
    qty_tp2 = TP2_SHARE if tp2_price else 0

    return round(tp1_price, 4), round(tp2_price, 4) if tp2_price else None, round(sl_price, 4), qty_tp1, qty_tp2

Обновление вызовов в strategy.py и trade_engine.py:
Уже выполнено ранее (передаем scaling_factor).
Пояснение:

Масштабирование TP/SL по силе тренда делает стратегию более гибкой, увеличивая TP в сильных трендах и уменьшая в слабых, что улучшает баланс риска и прибыли.

Тестирование:

Проверьте, что TP/SL масштабируются корректно:
В сильных трендах (ADX > 25) TP/SL увеличиваются (например, до 1,5x).
Во флетах (ADX < 15) уменьшаются (например, до 0,5x).
Убедитесь, что это не приводит к чрезмерным убыткам (слишком широкий SL) или пропуску целей (слишком узкий TP).
Риски: Низкие, но требуется тестирование в DRY_RUN (1-2 дня).

Шаг 4: Учет комиссий в PnL (Шаг 5)
Описание:

Добавляем учет комиссий в расчет PnL в логах и отчетах для более точной оценки прибыльности.

Код:

Обновление tp_logger.py:
Рассчитываем чистую прибыль с учетом комиссий.
python

Copy

# tp_logger.py

import pandas as pd
from config import TAKER_FEE_RATE
from utils_logging import log

def log_trade_result(trade_data):
symbol = trade_data["symbol"]
side = trade_data["side"]
entry_price = trade_data["entry_price"]
exit_price = trade_data["exit_price"]
qty = trade_data["qty"]
tp1_hit = trade_data["tp1_hit"]
tp2_hit = trade_data["tp2_hit"]
sl_hit = trade_data["sl_hit"]
pnl_percent = trade_data["pnl_percent"]
result = trade_data["result"]
duration_minutes = trade_data["duration_minutes"]
htf_trend = trade_data["htf_trend"]

    # Расчет чистой прибыли
    gross_pnl = (exit_price - entry_price) * qty if side == "buy" else (entry_price - exit_price) * qty
    commission = 2 * qty * entry_price * TAKER_FEE_RATE
    net_pnl = gross_pnl - commission
    net_pnl_percent = net_pnl / (entry_price * qty) * 100

    log(
        f"{symbol} Trade Result: {result}, Gross PnL: {gross_pnl:.2f} USDC, Net PnL: {net_pnl:.2f} USDC ({net_pnl_percent:.2f}%), Duration: {duration_minutes} min",
        level="INFO"
    )

    # Запись в CSV
    trade_record = {
        "Date": pd.Timestamp.now(),
        "Symbol": symbol,
        "Side": side,
        "EntryPrice": entry_price,
        "ExitPrice": exit_price,
        "Qty": qty,
        "GrossPnL": gross_pnl,
        "NetPnL": net_pnl,
        "NetPnLPercent": net_pnl_percent,
        "Result": result,
        "DurationMinutes": duration_minutes,
        "TP1Hit": tp1_hit,
        "TP2Hit": tp2_hit,
        "SLHit": sl_hit,
        "HTFTrend": htf_trend
    }

    df = pd.DataFrame([trade_record])
    df.to_csv("data/tp_performance.csv", mode="a", header=not pd.io.common.file_exists("data/tp_performance.csv"), index=False)

Обновление trade_engine.py:
Корректируем record_trade_result для учета комиссий.
python

Copy

# trade_engine.py

def record_trade_result(symbol, side, entry_price, exit_price, result_type):
global open_positions_count, dry_run_positions_count
with open_positions_lock:
if DRY_RUN:
dry_run_positions_count -= 1
else:
open_positions_count -= 1

    trade = trade_manager.get_trade(symbol)
    if not trade:
        log(f"⚠️ No trade info for {symbol} — cannot record result")
        return

    qty = trade["qty"]
    duration = int((time.time() - trade["start_time"].timestamp()) / 60)
    gross_pnl = (exit_price - entry_price) / entry_price * 100 if side == "buy" else (entry_price - exit_price) / entry_price * 100
    commission = 2 * qty * entry_price * TAKER_FEE_RATE
    net_pnl = ((exit_price - entry_price) * qty - commission) / (entry_price * qty) * 100 if side == "buy" else ((entry_price - exit_price) * qty - commission) / (entry_price * qty) * 100

    log_trade_result({
        "symbol": symbol,
        "side": side,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "qty": qty,
        "tp1_hit": trade.get("tp1_hit", False),
        "tp2_hit": trade.get("tp2_hit", False),
        "sl_hit": (result_type == "sl"),
        "pnl_percent": net_pnl,  # Используем чистую прибыль
        "result": "WIN" if net_pnl > 0 else "LOSS",
        "duration_minutes": duration,
        "htf_trend": trade.get("htf_trend", False),
    })

    msg = (
        f"📤 *Trade Closed* [{result_type.upper()}{' + Soft Exit' if trade.get('soft_exit_hit', False) else ''}]\n"
        f"• {symbol} — {side.upper()}\n"
        f"• Entry: {round(entry_price, 4)} → Exit: {round(exit_price, 4)}\n"
        f"• Net PnL: {round(net_pnl, 2)}% | Held: {duration} min"
    )
    send_telegram_message(msg, force=True)

    trade_manager.remove_trade(symbol)

Пояснение:

Учет комиссий в PnL дает более точную картину прибыльности, что важно для отчетов и будущих улучшений (например, UI).

Тестирование:

Проверьте, что логи и отчеты показывают чистую прибыль (Net PnL), а не только валовую.
Убедитесь, что значения совпадают с расчетами (валовая прибыль - комиссии).
Риски: Минимальные. Это улучшение отчетности, не затрагивающее торговую логику.

Шаг 5: Фиксация конфигурации TP-оптимизатора (Шаг 6)
Описание:

Переходим с редактирования config.py на использование config_dynamic.json в tp_optimizer_ml.py для надежности.

Код:

Обновление config.py:
Добавляем путь к файлу config_dynamic.json.
python

Copy

# config.py

CONFIG_DYNAMIC_FILE = "data/config_dynamic.json"
Обновление tp_optimizer_ml.py:
Переключаемся на JSON.
python

Copy

# tp_optimizer_ml.py

import json
from config import CONFIG_DYNAMIC_FILE
from utils_logging import log

def update_tp_config(symbol, tp1, tp2):
try:
try:
with open(CONFIG_DYNAMIC_FILE, "r") as f:
config_data = json.load(f)
except FileNotFoundError:
config_data = {}

        config_data[symbol] = {"tp1": tp1, "tp2": tp2}

        with open(CONFIG_DYNAMIC_FILE, "w") as f:
            json.dump(config_data, f, indent=4)

        log(f"TP config updated for {symbol}: TP1={tp1}, TP2={tp2}", level="INFO")
    except Exception as e:
        log(f"Failed to update config for {symbol}: {e}", level="ERROR")

Обновление tp_utils.py:
Добавляем отладочный лог (см. следующий шаг).
Пояснение:

JSON упрощает управление настройками, снижая риск ошибок парсинга. Это также делает систему более масштабируемой для будущих параметров (например, SL).

Тестирование:

Убедитесь, что TP-оптимизатор корректно обновляет config_dynamic.json.
Проверьте, что tp_utils.py читает значения из JSON с fallback на дефолтные.
Риски: Низкие. Требуется базовое тестирование.

Шаг 6: Добавление отладочного лога в tp_utils.py (Мелкое улучшение)
Описание:

Добавляем отладочный лог, чтобы видеть источник значений TP (динамический или дефолтный).

Код:

Обновляем tp_utils.py (уже частично обновлен выше):
python

Copy

# tp_utils.py

import json
from config import AUTO_TP_SL_ENABLED, FLAT_ADJUSTMENT, SL_PERCENT, TP1_PERCENT, TP2_PERCENT, TP1_SHARE, TP2_SHARE, TREND_ADJUSTMENT, CONFIG_DYNAMIC_FILE
from utils_logging import log

def calculate_tp_levels(entry_price: float, side: str, symbol: str, regime: str = None, score: float = 5, scaling_factor: float = 1.0, atr: float = None, price: float = None):
"""
Вычисляет цены TP1, TP2 и SL на основе цены входа, стороны, режима рынка и волатильности (ATR).
"""
try:
with open(CONFIG_DYNAMIC_FILE, "r") as f:
config_data = json.load(f)
if symbol in config_data:
tp1_pct = config_data[symbol]["tp1"]
tp2_pct = config_data[symbol]["tp2"]
log(f"{symbol} using TP1={tp1_pct}, TP2={tp2_pct} (source: dynamic)", level="DEBUG")
else:
tp1_pct = TP1_PERCENT
tp2_pct = TP2_PERCENT
log(f"{symbol} using TP1={tp1_pct}, TP2={tp2_pct} (source: default)", level="DEBUG")
except Exception as e:
log(f"Failed to load dynamic config for {symbol}: {e}", level="WARNING")
tp1_pct = TP1_PERCENT
tp2_pct = TP2_PERCENT
log(f"{symbol} using TP1={tp1_pct}, TP2={tp2_pct} (source: default, error)", level="DEBUG")

    # Адаптация SL на основе ATR (если передано)
    sl_pct = SL_PERCENT
    if atr is not None and price is not None:
        atr_ratio = atr / price
        if atr_ratio > 0.002:
            sl_pct *= 1.5
        elif atr_ratio < 0.001:
            sl_pct *= 0.5

    # Масштабирование TP/SL по тренду
    tp1_pct *= scaling_factor
    tp2_pct = tp2_pct * scaling_factor if tp2_pct else None
    sl_pct *= scaling_factor

    if AUTO_TP_SL_ENABLED and regime:
        if regime == "flat":
            tp1_pct *= FLAT_ADJUSTMENT
            tp2_pct = tp2_pct * FLAT_ADJUSTMENT if tp2_pct else None
            sl_pct *= FLAT_ADJUSTMENT
        elif regime == "trend":
            tp2_pct = tp2_pct * TREND_ADJUSTMENT if tp2_pct else None
            sl_pct *= TREND_ADJUSTMENT

    if score == 3:
        tp1_pct *= 0.8
        tp2_pct = None
        sl_pct *= 0.8

    if side.lower() == "buy":
        tp1_price = entry_price * (1 + tp1_pct)
        tp2_price = entry_price * (1 + tp2_pct) if tp2_pct else None
        sl_price = entry_price * (1 - sl_pct)
    else:  # side == "sell"
        tp1_price = entry_price * (1 - tp1_pct)
        tp2_price = entry_price * (1 - tp2_pct) if tp2_pct else None
        sl_price = entry_price * (1 + sl_pct)

    qty_tp1 = TP1_SHARE
    qty_tp2 = TP2_SHARE if tp2_price else 0

    return round(tp1_price, 4), round(tp2_price, 4) if tp2_price else None, round(sl_price, 4), qty_tp1, qty_tp2

Пояснение:

Логи на уровне DEBUG помогают отслеживать, откуда берутся значения TP (динамические или дефолтные), что упрощает отладку проблем с оптимизатором.

Тестирование:

Проверьте логи в DRY_RUN с LOG_LEVEL="DEBUG".
Убедитесь, что источники TP (динамический или дефолтный) корректно отображаются.
Риски: Минимальные, так как это добавление логов.

Шаг 7: Настройка TP2 = None при низком score (Мелкое улучшение)
Описание:

Устанавливаем TP2 = None для слабых сигналов (score < 3), чтобы уменьшить рассеяние TP и сосредоточиться на TP1.

Код:

Обновляем tp_utils.py:
python

Copy

# tp_utils.py (фрагмент)

if score < 3:
tp2_pct = None
log(f"{symbol} TP2 set to None due to low score {score}", level="DEBUG")
Пояснение:

Это улучшает стратегию, снижая рассеяние TP на слабых сигналах, что может повысить винрейт за счет фиксации прибыли на TP1.

Тестирование:

Проверьте в DRY_RUN, что TP2 устанавливается в None при score < 3.
Сравните винрейт и общую прибыль с/без этого изменения (1-2 недели).
Риски: Умеренные. Может уменьшить прибыль от сильных движений, если TP2 не используется. Требуется тестирование.

Заключение
План включает 7 шагов:

Перемещение get_market_regime() (низкий риск).
Объединение last_trade_times (низкий риск).
Масштабирование TP/SL (низкий риск).
Учет комиссий в PnL (минимальный риск).
Переход на JSON в TP-оптимизаторе (низкий риск).
Отладочные логи в tp_utils.py (минимальный риск).
Настройка TP2 (умеренный риск).
Рекомендация:

Внедряйте шаги последовательно, начиная с 1-6 (низкий риск), тестируя каждый в DRY_RUN.
Шаг 7 (TP2) внедряйте последним, с длительным тестированием (1-2 недели), чтобы оценить влияние на винрейт и прибыль.
После внедрения всех шагов переходите к следующему приоритету из Roadmap (например, WebSocket).
