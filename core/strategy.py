# strategy.py
import threading
from datetime import datetime

import pandas as pd
import ta

from core.trade_engine import get_market_regime, get_position_size, trade_manager
from core.volatility_controller import get_volatility_filters
from telegram.telegram_utils import send_telegram_message
from tp_logger import get_trade_stats
from utils_core import get_cached_balance

last_trade_times = {}
last_trade_times_lock = threading.Lock()


def fetch_data(symbol, tf="15m"):
    from core.binance_api import fetch_ohlcv
    from utils_logging import log

    try:
        data = fetch_ohlcv(symbol, timeframe=tf, limit=50)
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
        df["atr"] = ta.volatility.AverageTrueRange(df["high"], df["low"], df["close"], window=14).average_true_range()
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
        SL_PERCENT,
        TAKER_FEE_RATE,
        TP2_SHARE,
        USE_TESTNET,
        get_min_net_profit,
    )
    from core.order_utils import calculate_order_quantity
    from core.risk_utils import get_adaptive_risk_percent
    from core.score_evaluator import calculate_score  # Moved inside the function
    from core.score_logger import log_score_history  # Moved inside the function
    from core.tp_utils import calculate_tp_levels  # Moved inside the function
    from utils_logging import log

    if df is None:
        log(f"Skipping {symbol} due to data fetch error", level="WARNING")
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
        cooldown = 30 * 60  # 30 минут
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

    if DRY_RUN:
        min_required *= 0.3
        log(f"{symbol} 🔎 Final Score: {score:.2f} / (Required: {min_required:.4f})")

    if score < min_required:
        if DRY_RUN:
            log(f"{symbol} ❌ No entry: insufficient score\n" f"Final Score: {score:.2f} / (Required: {min_required:.4f})")
        return None

    log(f"{symbol} 🔎 Step 4: Direction determination", level="DEBUG")
    direction = "BUY" if df["macd"].iloc[-1] > df["macd_signal"].iloc[-1] else "SELL"

    entry_price = df["close"].iloc[-1]
    stop_price = entry_price * (1 - SL_PERCENT) if direction == "BUY" else entry_price * (1 + SL_PERCENT)
    risk_percent = get_adaptive_risk_percent(balance)
    qty = calculate_order_quantity(entry_price, stop_price, balance, risk_percent)

    log(f"{symbol} 🔎 Step 5: Notional check", level="DEBUG")
    leverage_key = symbol.split(":")[0].replace("/", "") if USE_TESTNET else symbol.replace("/", "")
    leverage = LEVERAGE_MAP.get(leverage_key, 5)
    max_notional = balance * leverage
    notional = qty * entry_price

    if notional > max_notional:
        qty = max_notional / entry_price
        notional = qty * entry_price
        log(
            f"{symbol} Adjusted qty to {qty:.6f} to meet notional limit (max: {max_notional:.2f})",
            level="DEBUG",
        )

    regime = get_market_regime(symbol) if AUTO_TP_SL_ENABLED else None
    tp1_price, tp2_price, sl_price, qty_tp1_share, qty_tp2_share = calculate_tp_levels(entry_price, direction, regime, score)

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

    log(f"{symbol} 🔎 Step 9: Final return", level="DEBUG")
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
