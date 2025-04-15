# strategy.py
import threading
from datetime import datetime

import pandas as pd
import ta

from config import (
    AUTO_TP_SL_ENABLED,  # Добавляем импорт
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
from core.tp_utils import calculate_tp_levels
from core.trade_engine import get_market_regime, get_position_size, trade_manager
from core.volatility_controller import get_volatility_filters
from telegram.telegram_utils import send_telegram_message
from tp_logger import get_trade_stats
from utils_core import get_adaptive_risk_percent, get_cached_balance, safe_call_retry
from utils_logging import log

last_trade_times = {}
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


def should_enter_trade(symbol, df, exchange, last_trade_times, last_trade_times_lock):
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
        last_time = last_trade_times.get(symbol)
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
    regime = get_market_regime(symbol) if AUTO_TP_SL_ENABLED else None  # Уточняем расчет режима
    tp1_price, _, _, qty_tp1_share, _ = calculate_tp_levels(entry_price, direction, regime, score)

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
        last_time = last_trade_times.get(symbol)
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
            last_trade_times[symbol] = utc_now
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
            last_trade_times[symbol] = utc_now
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
        last_trade_times[symbol] = utc_now

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
