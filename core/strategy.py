# strategy.py
import threading
from datetime import datetime

import pandas as pd
import pytz
import ta

from common.config_loader import (
    BREAKOUT_DETECTION,
    HIGH_ACTIVITY_HOURS,
    MOMENTUM_LOOKBACK,
    SHORT_TERM_MODE,
    TRADING_HOURS_FILTER,
    VOLUME_SPIKE_THRESHOLD,
    WEEKEND_TRADING,
)
from core.trade_engine import get_position_size, trade_manager
from core.volatility_controller import get_volatility_filters
from telegram.telegram_utils import send_telegram_message
from tp_logger import get_trade_stats
from utils_core import get_cached_balance

last_trade_times = {}
last_trade_times_lock = threading.Lock()


def is_optimal_trading_hour():
    """
    Determine if the current time is during optimal trading hours.
    Returns True during hours of high market activity, False otherwise.
    """
    if not TRADING_HOURS_FILTER:
        return True  # Always allow if filter is disabled

    current_time = datetime.now(pytz.UTC)
    hour_utc = current_time.hour

    # Weekend check - skip trading on weekends if configured
    if not WEEKEND_TRADING and current_time.weekday() >= 5:  # 5=Saturday, 6=Sunday
        return False

    # Check if current hour is in high activity hours list
    return hour_utc in HIGH_ACTIVITY_HOURS


def fetch_data(symbol, tf="15m"):
    """
    Fetch market data with enhanced indicators for short-term trading.
    """
    from core.binance_api import fetch_ohlcv
    from utils_logging import log

    try:
        # Get more data for better indicator calculation
        data = fetch_ohlcv(symbol, timeframe=tf, limit=100)  # Increased from 50
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

        # Standard indicators
        df["rsi"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
        df["ema"] = ta.trend.EMAIndicator(df["close"], window=20).ema_indicator()
        df["macd"] = ta.trend.MACD(df["close"]).macd()
        df["macd_signal"] = ta.trend.MACD(df["close"]).macd_signal()
        df["atr"] = ta.volatility.AverageTrueRange(df["high"], df["low"], df["close"], window=14).average_true_range()

        # Enhanced short-term indicators
        df["fast_ema"] = ta.trend.EMAIndicator(df["close"], window=9).ema_indicator()
        df["slow_ema"] = ta.trend.EMAIndicator(df["close"], window=21).ema_indicator()
        df["adx"] = ta.trend.ADXIndicator(df["high"], df["low"], df["close"], window=14).adx()

        # Bollinger Bands for breakout detection
        bb = ta.volatility.BollingerBands(df["close"], window=20)
        df["bb_width"] = bb.bollinger_hband() - bb.bollinger_lband()
        df["bb_width_pct"] = df["bb_width"] / df["close"]  # Normalized width
        df["bb_upper"] = bb.bollinger_hband()
        df["bb_lower"] = bb.bollinger_lband()

        # Short-term momentum detection
        if len(df) >= MOMENTUM_LOOKBACK + 1:
            df["momentum"] = df["close"].pct_change(MOMENTUM_LOOKBACK) * 100

        # Calculate relative volume (compared to same time yesterday)
        if len(df) >= 96:  # At least 24 hours of data (96 periods in 15m)
            df["yesterday_vol"] = df["volume"].shift(96)  # 96 periods = 24h in 15m tf
            df["rel_volume"] = df["volume"] / df["yesterday_vol"]
        else:
            df["rel_volume"] = df["volume"] / df["volume"].mean()

        return df
    except Exception as e:
        log(f"Error fetching data for {symbol}: {e}", level="ERROR")
        return None


def get_htf_trend(symbol, tf="1h"):
    """
    Get higher timeframe trend with enhanced logic for breakout detection.
    """
    df_htf = fetch_data(symbol, tf=tf)
    if df_htf is None:
        return False

    # Standard trend check
    price_above_ema = df_htf["close"].iloc[-1] > df_htf["ema"].iloc[-1]

    # Enhanced trend check - look for momentum
    momentum_increasing = False
    if "momentum" in df_htf.columns and len(df_htf) >= 3:
        momentum_increasing = df_htf["momentum"].iloc[-1] > df_htf["momentum"].iloc[-2]

    return price_above_ema and momentum_increasing


def get_enhanced_market_regime(symbol):
    """
    Enhanced market regime detection with breakout identification.
    """
    from common.config_loader import ADX_FLAT_THRESHOLD, ADX_TREND_THRESHOLD
    from core.binance_api import fetch_ohlcv
    from utils_logging import log

    try:
        ohlcv = fetch_ohlcv(symbol, timeframe="15m", limit=50)
        log(f"{symbol} 🔍 Fetched {len(ohlcv)} candles for timeframe 15m", level="DEBUG")
        if not ohlcv or len(ohlcv) < 28:
            log(
                f"{symbol} ⚠️ Insufficient data: only {len(ohlcv) if ohlcv else 0} candles available, need at least 28 for ADX",
                level="WARNING",
            )
            return "neutral"

        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        closes = [c[4] for c in ohlcv]
        df = pd.DataFrame({"high": highs, "low": lows, "close": closes})

        # Calculate ADX for trend strength
        adx_series = ta.trend.ADXIndicator(df["high"], df["low"], df["close"], window=14).adx()
        if len(adx_series) < 1 or adx_series.isna().all():
            log(
                f"{symbol} ⚠️ ADX calculation failed: insufficient data after processing",
                level="WARNING",
            )
            return "neutral"
        adx = adx_series.iloc[-1]

        # Calculate Bollinger Bands for volatility
        bb = ta.volatility.BollingerBands(df["close"], window=20)
        bb_width = (bb.bollinger_hband() - bb.bollinger_lband()).iloc[-1] / df["close"].iloc[-1]

        log(f"{symbol} 🔍 Market regime: ADX = {adx:.2f}, BB Width = {bb_width:.4f}", level="DEBUG")

        # Breakout detection - wide BB width and strong ADX
        if BREAKOUT_DETECTION and bb_width > 0.05 and adx > 20:
            log(
                f"{symbol} 🔍 Breakout detected! (BB Width > 0.05, ADX > 20)",
                level="INFO",
            )
            return "breakout"
        elif adx > ADX_TREND_THRESHOLD:
            log(
                f"{symbol} 🔍 Market regime determined: trend (ADX > {ADX_TREND_THRESHOLD})",
                level="INFO",
            )
            return "trend"
        elif adx < ADX_FLAT_THRESHOLD:
            log(
                f"{symbol} 🔍 Market regime determined: flat (ADX < {ADX_FLAT_THRESHOLD})",
                level="INFO",
            )
            return "flat"
        else:
            log(
                f"{symbol} 🔍 Market regime determined: neutral (ADX between {ADX_FLAT_THRESHOLD} and {ADX_TREND_THRESHOLD})",
                level="INFO",
            )
            return "neutral"
    except Exception as e:
        log(f"[ERROR] Failed to determine market regime for {symbol}: {e}", level="ERROR")
        return "neutral"


def passes_filters(df, symbol):
    from common.config_loader import (
        DRY_RUN,
        FILTER_THRESHOLDS,
        VOLATILITY_ATR_THRESHOLD,
        VOLATILITY_RANGE_THRESHOLD,
        VOLATILITY_SKIP_ENABLED,
    )
    from utils_logging import log

    balance = get_cached_balance()
    filter_mode = "default_light" if balance < 100 else "default"
    normalized_symbol = symbol.split(":")[0].replace("/", "") if ":" in symbol else symbol.replace("/", "")
    base_filters = FILTER_THRESHOLDS.get(normalized_symbol, FILTER_THRESHOLDS[filter_mode])

    filters = get_volatility_filters(symbol, base_filters)
    relax_factor = filters["relax_factor"]

    # Relaxed filters during optimal trading hours
    if SHORT_TERM_MODE and is_optimal_trading_hour():
        filters["atr"] *= 0.9  # 10% more permissive during peak hours
        filters["adx"] *= 0.85  # 15% more permissive during peak hours
        filters["bb"] *= 0.9  # 10% more permissive during peak hours

    if DRY_RUN:
        filters["atr"] *= 0.6
        filters["adx"] *= 0.6
        filters["bb"] *= 0.6

    price = df["close"].iloc[-1]
    atr = df["atr"].iloc[-1] / price if not pd.isna(df["atr"].iloc[-1]) else 0
    adx = df["adx"].iloc[-1] if not pd.isna(df["adx"].iloc[-1]) else 0
    bb_width = df["bb_width"].iloc[-1] / price if not pd.isna(df["bb_width"].iloc[-1]) else 0

    if pd.isna(atr) or atr == 0:
        log(f"{symbol} ⛔️ Rejected: ATR is NaN or 0", level="ERROR")
        send_telegram_message(f"⚠️ ATR calculation failed for {symbol}", force=True)
        return False
    if atr < filters["atr"]:
        log(
            f"{symbol} ⛔️ Rejected: ATR {atr:.5f} < {filters['atr']} (relax={relax_factor})",
            level="DEBUG",
        )
        send_telegram_message(f"⚠️ {symbol} rejected: ATR {atr:.5f} < {filters['atr']}", force=True)
        return False
    if pd.isna(adx) or adx == 0:
        log(f"{symbol} ⛔️ Rejected: ADX is NaN or 0", level="ERROR")
        send_telegram_message(f"⚠️ ADX calculation failed for {symbol}", force=True)
        return False
    if adx < filters["adx"]:
        log(
            f"{symbol} ⛔️ Rejected: ADX {adx:.2f} < {filters['adx']} (relax={relax_factor})",
            level="DEBUG",
        )
        send_telegram_message(f"⚠️ {symbol} rejected: ADX {adx:.2f} < {filters['adx']}", force=True)
        return False
    if pd.isna(bb_width) or bb_width == 0:
        log(f"{symbol} ⛔️ Rejected: BB Width is NaN or 0", level="ERROR")
        send_telegram_message(f"⚠️ BB Width calculation failed for {symbol}", force=True)
        return False
    if bb_width < filters["bb"]:
        log(
            f"{symbol} ⛔️ Rejected: BB Width {bb_width:.5f} < {filters['bb']} (relax={relax_factor})",
            level="DEBUG",
        )
        send_telegram_message(f"⚠️ {symbol} rejected: BB Width {bb_width:.5f} < {filters['bb']}", force=True)
        return False

    # Volume spike check for short-term trading
    if SHORT_TERM_MODE and "rel_volume" in df.columns and not pd.isna(df["rel_volume"].iloc[-1]):
        rel_volume = df["rel_volume"].iloc[-1]
        if rel_volume < 0.7:  # Volume significantly below average
            log(f"{symbol} ⛔️ Rejected: Low relative volume {rel_volume:.2f}", level="DEBUG")
            return False

    if VOLATILITY_SKIP_ENABLED:
        price = df["close"].iloc[-1]
        high = df["high"].iloc[-1]
        low = df["low"].iloc[-1]
        atr = df["atr"].iloc[-1] / price
        range_ratio = (high - low) / price
        if atr < VOLATILITY_ATR_THRESHOLD and range_ratio < VOLATILITY_RANGE_THRESHOLD:
            if DRY_RUN:
                log(f"{symbol} ⛔️ Rejected: low volatility (ATR: {atr:.5f}, Range: {range_ratio:.5f})")
            return False
    return True


def should_enter_trade(symbol, df, exchange, last_trade_times, last_trade_times_lock):
    from common.config_loader import (
        AUTO_TP_SL_ENABLED,
        DRY_RUN,
        LEVERAGE_MAP,
        MIN_NOTIONAL_OPEN,
        MIN_NOTIONAL_ORDER,
        MIN_TRADE_SCORE,
        PRIORITY_SMALL_BALANCE_PAIRS,
        SL_PERCENT,
        TAKER_FEE_RATE,
        TP2_SHARE,
        TRADING_HOURS_FILTER,
        USE_TESTNET,
        get_min_net_profit,
    )
    from core.order_utils import calculate_order_quantity
    from core.risk_utils import get_adaptive_risk_percent
    from core.score_evaluator import calculate_score
    from core.score_logger import log_score_history
    from core.tp_utils import calculate_tp_levels
    from utils_logging import log

    if df is None:
        log(f"Skipping {symbol} due to data fetch error", level="WARNING")
        return None

    # Check if we're in optimal trading hours
    if TRADING_HOURS_FILTER and not is_optimal_trading_hour():
        # Only skip non-priority pairs during non-optimal hours
        balance = get_cached_balance()
        if balance < 150 and symbol in PRIORITY_SMALL_BALANCE_PAIRS:
            # Allow priority pairs for small accounts even in non-optimal hours
            log(f"{symbol} Priority pair allowed during non-optimal hours", level="DEBUG")
        else:
            log(f"{symbol} ⏰ Skipping due to non-optimal trading hours", level="DEBUG")
            return None

    utc_now = datetime.utcnow()
    balance = get_cached_balance()
    position_size = get_position_size(symbol)

    balance_info = exchange.fetch_balance()
    margin_info = balance_info["info"]
    total_margin_balance = float(margin_info.get("totalMarginBalance", 0))
    position_initial_margin = float(margin_info.get("totalPositionInitialMargin", 0))
    open_order_initial_margin = float(margin_info.get("totalOpenOrderInitialMargin", 0))
    available_margin = total_margin_balance - position_initial_margin - open_order_initial_margin
    if available_margin <= 0:
        log(
            f"⚠️ Skipping {symbol} — no available margin (total: {total_margin_balance:.2f}, positions: {position_initial_margin:.2f}, orders: {open_order_initial_margin:.2f})",
            level="ERROR",
        )
        return None

    log(f"{symbol} 🔎 Step 1: Cooldown check", level="DEBUG")
    with last_trade_times_lock:
        last_time = last_trade_times.get(symbol)
        # Reduced cooldown for short-term trading
        cooldown = 20 * 60 if SHORT_TERM_MODE else 30 * 60  # 20 or 30 minutes
        elapsed = utc_now.timestamp() - last_time.timestamp() if last_time else float("inf")
        if elapsed < cooldown:
            if DRY_RUN:
                log(f"{symbol} ⏳ Ignored due to cooldown")
            return None

    log(f"{symbol} 🔎 Step 2: Filter check", level="DEBUG")
    if not passes_filters(df, symbol):
        return None

    log(f"{symbol} 🔎 Step 3: Scoring check", level="DEBUG")
    trade_count, winrate = get_trade_stats()
    score = calculate_score(df, symbol, trade_count, winrate)
    min_required = MIN_TRADE_SCORE
    if MIN_TRADE_SCORE is not None and score < MIN_TRADE_SCORE:
        log(
            f"{symbol} ⛔️ Rejected: score {score:.2f} < MIN_TRADE_SCORE {MIN_TRADE_SCORE}",
            level="DEBUG",
        )
        return None

    # Adjust score requirement during optimal trading hours
    if SHORT_TERM_MODE and is_optimal_trading_hour():
        min_required *= 0.9  # 10% lower threshold during optimal hours

    if DRY_RUN:
        min_required *= 0.3
        log(f"{symbol} 🔎 Final Score: {score:.2f} / (Required: {min_required:.4f})")

    if score < min_required:
        if DRY_RUN:
            log(f"{symbol} ❌ No entry: insufficient score\n" f"Final Score: {score:.2f} / (Required: {min_required:.4f})")
        return None

    log(f"{symbol} 🔎 Step 4: Direction determination", level="DEBUG")
    # Ensure MACD values are not None
    if "macd" not in df.columns or "macd_signal" not in df.columns:
        log(f"{symbol} ⚠️ MACD columns missing from DataFrame", level="ERROR")
        return None

    macd_value = df["macd"].iloc[-1] if not pd.isna(df["macd"].iloc[-1]) else 0
    macd_signal_value = df["macd_signal"].iloc[-1] if not pd.isna(df["macd_signal"].iloc[-1]) else 0
    log(f"{symbol} DEBUG: MACD={macd_value}, Signal={macd_signal_value}", level="DEBUG")

    # Enhanced direction determination with EMA crossover confirmation
    ema_cross_confirmation = False
    if "fast_ema" in df.columns and "slow_ema" in df.columns:
        fast_cross_above = df["fast_ema"].iloc[-1] > df["slow_ema"].iloc[-1] and df["fast_ema"].iloc[-2] <= df["slow_ema"].iloc[-2]
        fast_cross_below = df["fast_ema"].iloc[-1] < df["slow_ema"].iloc[-1] and df["fast_ema"].iloc[-2] >= df["slow_ema"].iloc[-2]

        if (macd_value > macd_signal_value and fast_cross_above) or (macd_value < macd_signal_value and fast_cross_below):
            ema_cross_confirmation = True
            log(f"{symbol} ✅ EMA cross confirmation", level="DEBUG")

    # Base direction on MACD
    direction = "BUY" if macd_value > macd_signal_value else "SELL"

    # Check relative volume for confirmation
    volume_confirmation = False
    if "rel_volume" in df.columns and not pd.isna(df["rel_volume"].iloc[-1]):
        rel_volume = df["rel_volume"].iloc[-1]
        if rel_volume > VOLUME_SPIKE_THRESHOLD:
            volume_confirmation = True
            log(f"{symbol} ✅ Volume spike confirmation: {rel_volume:.2f}x average", level="DEBUG")

    # Enhanced direction confidence
    direction_confidence = 1.0
    if ema_cross_confirmation:
        direction_confidence += 0.2
    if volume_confirmation:
        direction_confidence += 0.2

    entry_price = df["close"].iloc[-1]
    stop_price = entry_price * (1 - SL_PERCENT) if direction == "BUY" else entry_price * (1 + SL_PERCENT)

    # Apply direction confidence to risk_percent for stronger signals
    base_risk_percent = get_adaptive_risk_percent(balance)
    risk_percent = min(base_risk_percent * direction_confidence, base_risk_percent * 1.4)  # Cap at 40% increase

    try:
        qty = calculate_order_quantity(entry_price, stop_price, balance, risk_percent)
        if qty is None:
            log(f"{symbol} ⚠️ Quantity calculation returned None, using default", level="WARNING")
            qty = MIN_NOTIONAL_OPEN / entry_price
    except Exception as e:
        log(f"{symbol} ⚠️ Error calculating quantity: {e}", level="WARNING")
        return None

    log(f"{symbol} 🔎 Step 5: Notional check", level="DEBUG")
    leverage_key = symbol.split(":")[0].replace("/", "") if USE_TESTNET else symbol.replace("/", "")
    leverage = LEVERAGE_MAP.get(leverage_key, 5)

    # Verify all values before multiplication
    if None in (balance, leverage):
        log(f"{symbol} ⚠️ Invalid values: balance={balance}, leverage={leverage}", level="ERROR")
        return None

    max_notional = balance * leverage

    # Verify qty before multiplication
    if qty is None:
        log(f"{symbol} ⚠️ Invalid quantity: None", level="ERROR")
        return None

    notional = qty * entry_price

    if notional > max_notional:
        qty = max_notional / entry_price
        notional = qty * entry_price
        log(
            f"{symbol} Adjusted qty to {qty:.6f} to meet notional limit (max: {max_notional:.2f})",
            level="DEBUG",
        )

    # Use enhanced market regime detection
    regime = get_enhanced_market_regime(symbol) if AUTO_TP_SL_ENABLED else None
    log(f"DEBUG: About to calculate TP/SL for {symbol} with regime={regime}", level="DEBUG")

    tp1_price, tp2_price, sl_price, qty_tp1_share, qty_tp2_share = calculate_tp_levels(entry_price, direction, regime, score, df)

    # Add validation for tp_levels values
    log(f"DEBUG: TP/SL values for {symbol}: tp1={tp1_price}, tp2={tp2_price}, sl={sl_price}, tp1_share={qty_tp1_share}, tp2_share={qty_tp2_share}", level="DEBUG")

    if tp1_price is None or sl_price is None:
        log(f"⚠️ Skipping {symbol} — invalid TP/SL values: tp1={tp1_price}, sl={sl_price}", level="ERROR")
        return None

    if notional < MIN_NOTIONAL_OPEN:
        qty = MIN_NOTIONAL_OPEN / entry_price
        notional = qty * entry_price
        log(
            f"{symbol} Adjusted qty to {qty:.6f} to meet minimum notional for opening position (min: {MIN_NOTIONAL_OPEN:.2f})",
            level="DEBUG",
        )
        if notional > max_notional:
            log(
                f"{symbol} ⛔️ Cannot meet minimum notional {MIN_NOTIONAL_OPEN:.2f} without exceeding max_notional {max_notional:.2f}",
                level="WARNING",
            )
            return None

    # Handle TP2 calculations only if tp2_price is not None
    if tp2_price is not None:
        qty_tp2 = qty * TP2_SHARE
        tp2_notional = qty_tp2 * tp2_price

        if tp2_notional < MIN_NOTIONAL_ORDER:
            qty_tp2 = MIN_NOTIONAL_ORDER / tp2_price
            qty = qty_tp2 / TP2_SHARE
            notional = qty * entry_price
            log(
                f"{symbol} Adjusted qty to {qty:.6f} to meet minimum TP2 notional (min: {MIN_NOTIONAL_ORDER:.2f}, TP2 notional: {qty_tp2 * tp2_price:.2f})",
                level="DEBUG",
            )
            if notional > max_notional:
                log(
                    f"{symbol} ⛔️ Cannot meet minimum TP2 notional {MIN_NOTIONAL_ORDER:.2f} without exceeding max_notional {max_notional:.2f}",
                    level="WARNING",
                )
                return None
    else:
        # Handle the case when tp2_price is None (for weak signals)
        log(f"{symbol} ℹ️ No TP2 price set (likely due to weak signal), using TP1 only", level="DEBUG")
        qty_tp2 = 0

    log(f"{symbol} 🔎 Step 6: TP1 share check", level="DEBUG")
    if qty_tp1_share == 0:
        log(f"{symbol} ⛔️ Rejected: qty_tp1_share is 0", level="DEBUG")
        return None

    qty_tp1 = qty * qty_tp1_share
    gross_profit_tp1 = qty_tp1 * abs(tp1_price - entry_price)
    commission = 2 * (qty * entry_price * TAKER_FEE_RATE)
    net_profit_tp1 = gross_profit_tp1 - commission

    log(f"{symbol} 🔎 Step 7: MIN_NET_PROFIT check", level="DEBUG")
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

    log(f"{symbol} 🔎 Step 8: Smart re-entry logic", level="DEBUG")
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

            # Use safe MACD check
            direction = "BUY" if macd_value > macd_signal_value else "SELL"

            log(
                f"{symbol} 🔍 Generated signal: {direction}, MACD: {macd_value:.5f}, Signal: {macd_signal_value:.5f}",
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
            # Use safe MACD check
            direction = "BUY" if macd_value > macd_signal_value else "SELL"

            log(
                f"{symbol} 🔍 Generated signal: {direction}, MACD: {macd_value:.5f}, Signal: {macd_signal_value:.5f}",
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

    log(f"{symbol} 🔎 Step 9: Final return", level="DEBUG")
    with last_trade_times_lock:
        last_trade_times[symbol] = utc_now

    # Use safe MACD check
    direction = "BUY" if macd_value > macd_signal_value else "SELL"

    log(
        f"{symbol} 🔍 Generated signal: {direction}, MACD: {macd_value:.5f}, Signal: {macd_signal_value:.5f}",
        level="DEBUG",
    )
    if not DRY_RUN:
        log_score_history(symbol, score)
        log(f"{symbol} ✅ {direction} signal triggered (score: {score:.2f}/5)")
    else:
        msg = f"🧪-DRY-RUN-{symbol}-{direction}-Score-{score:.2f}-of-5"
        send_telegram_message(msg, force=True, parse_mode="")

    return ("buy" if direction == "BUY" else "sell", score, False)
