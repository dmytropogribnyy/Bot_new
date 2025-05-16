# pair_selector.py
import json
import os
import time
from datetime import datetime
from threading import Lock

import pandas as pd

from common.config_loader import (
    DRY_RUN,
    FIXED_PAIRS,
    MISSED_OPPORTUNITIES_FILE,
    PAIR_COOLING_PERIOD_HOURS,
    PAIR_ROTATION_MIN_INTERVAL,
    PRIORITY_SMALL_BALANCE_PAIRS,
    USDC_SYMBOLS,
    USDT_SYMBOLS,
    USE_TESTNET,
)
from constants import INACTIVE_CANDIDATES_FILE, PERFORMANCE_FILE, SIGNAL_FAILURES_FILE, SYMBOLS_FILE
from core.binance_api import convert_symbol
from core.dynamic_filters import get_market_regime_from_indicators, should_filter_pair
from core.exchange_init import exchange
from core.fail_stats_tracker import FAIL_STATS_FILE, is_symbol_blocked
from core.filter_adaptation import load_json_file, save_json_file
from symbol_activity_tracker import SIGNAL_ACTIVITY_FILE
from telegram.telegram_utils import send_telegram_message
from utils_core import get_cached_balance, get_market_volatility_index, get_runtime_config, is_optimal_trading_hour, safe_call_retry
from utils_logging import log

# Adaptive rotation interval - more frequent for small accounts and high volatility
BASE_UPDATE_INTERVAL = 60 * 15  # 15 минут вместо 30
symbols_file_lock = Lock()
performance_lock = Lock()

DRY_RUN_FALLBACK_SYMBOLS = USDT_SYMBOLS if USE_TESTNET else USDC_SYMBOLS

# Historical performance tracking
pair_performance = {}

# Добавить глобальную переменную
_last_logged_hour = None


def load_failure_stats():
    try:
        with open(FAIL_STATS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def fetch_all_symbols():
    """
    Fetch all available USDC futures pairs from the exchange.
    Enhanced to scan all pairs rather than just predefined list.
    """
    try:
        markets = safe_call_retry(exchange.load_markets, label="load_markets")
        if not markets:
            log("No markets returned from API", level="ERROR")
            if DRY_RUN:
                log("Using fallback symbols in DRY_RUN", level="WARNING")
                send_telegram_message("⚠️ Using fallback symbols due to API failure", force=True)
                return DRY_RUN_FALLBACK_SYMBOLS
            log("No active symbols available and DRY_RUN is False, stopping", level="ERROR")
            send_telegram_message("⚠️ No active symbols available, stopping bot", force=True)
            return []

        log(f"Loaded markets: {len(markets)} total symbols", level="DEBUG")

        # Проверяем список ключей и структуру для отладки
        sample_keys = list(markets.keys())[:3]
        log(f"Sample market keys: {sample_keys}", level="DEBUG")

        # Find all active USDC pairs using more flexible criteria
        all_usdc_futures_pairs = []

        # Сначала попробуем найти пары по нашему предпочтительному формату
        for symbol in USDC_SYMBOLS:
            api_symbol = convert_symbol(symbol)
            if api_symbol in markets and markets[api_symbol].get("active", False):
                all_usdc_futures_pairs.append(symbol)
                log(f"Found active pair from predefined list: {symbol}", level="DEBUG")

        # Если не нашли ни одной пары, используем запасной метод проверки
        if not all_usdc_futures_pairs:
            log("No pairs found using predefined list, trying alternate detection", level="WARNING")
            for symbol, market in markets.items():
                # Проверяем наличие "USDC" в имени символа
                if "USDC" in symbol and market.get("active", False):
                    # Преобразуем формат символа к нашему стандарту (с "/")
                    if "/" not in symbol:
                        # Находим позицию "USDC" и вставляем "/"
                        usdc_pos = symbol.find("USDC")
                        if usdc_pos > 0:
                            formatted_symbol = f"{symbol[:usdc_pos]}/USDC"
                            all_usdc_futures_pairs.append(formatted_symbol)
                            log(f"Found and reformatted pair: {symbol} → {formatted_symbol}", level="DEBUG")
                    else:
                        all_usdc_futures_pairs.append(symbol)
                        log(f"Found pair with slash: {symbol}", level="DEBUG")

        # Если все равно не нашли пар, используем предопределенный список
        if not all_usdc_futures_pairs:
            log("No USDC pairs found at all. Using predefined USDC_SYMBOLS list.", level="WARNING")
            send_telegram_message("⚠️ Symbol detection failed - using default list", force=True)
            return USDC_SYMBOLS

        log(f"Found {len(all_usdc_futures_pairs)} active USDC pairs", level="INFO")
        return all_usdc_futures_pairs

    except Exception as e:
        log(f"Error fetching all symbols: {str(e)}", level="ERROR")
        log(f"Exception type: {type(e)}, details: {e}", level="ERROR")
        log("Falling back to predefined USDC_SYMBOLS", level="WARNING")
        send_telegram_message(f"⚠️ Symbol detection error: {str(e)}", force=True)
        return USDC_SYMBOLS


def fetch_symbol_data(symbol, timeframe="15m", limit=100):
    """Fetch OHLCV data for a symbol."""
    try:
        api_symbol = convert_symbol(symbol)
        ohlcv = safe_call_retry(exchange.fetch_ohlcv, api_symbol, timeframe, limit=limit, label=f"fetch_ohlcv {symbol}")
        if not ohlcv:
            log(f"No OHLCV data returned for {symbol}", level="ERROR")
            return None

        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        return df
    except Exception as e:
        log(f"Error fetching data for {symbol}: {e}", level="ERROR")
        return None


def auto_cleanup_signal_failures(threshold=5000, keep_last=1000):
    try:
        if os.path.exists(SIGNAL_FAILURES_FILE):
            data = load_json_file(SIGNAL_FAILURES_FILE)
            if isinstance(data, list) and len(data) > threshold:
                trimmed = data[-keep_last:]
                save_json_file(SIGNAL_FAILURES_FILE, trimmed)
                log(f"🧹 Auto-cleaned signal_failures.json: kept last {keep_last} of {len(data)} entries", level="INFO")
    except Exception as e:
        log(f"⚠️ Error during auto-cleanup of signal_failures.json: {e}", level="ERROR")


def calculate_volatility(df):
    """Calculate volatility based on price range."""
    if df is None or len(df) < 2:
        return 0
    df["range"] = df["high"] - df["low"]
    return df["range"].mean() / df["close"].mean()


def calculate_atr_volatility(df, period=14):
    """Calculate ATR-based volatility."""
    if df is None or len(df) < period + 1:
        return 0

    # Calculate True Range
    df["tr1"] = abs(df["high"] - df["low"])
    df["tr2"] = abs(df["high"] - df["close"].shift(1))
    df["tr3"] = abs(df["low"] - df["close"].shift(1))
    df["tr"] = df[["tr1", "tr2", "tr3"]].max(axis=1)

    # Calculate ATR
    df["atr"] = df["tr"].rolling(period).mean()

    if len(df) > period and not pd.isna(df["atr"].iloc[-1]):
        return df["atr"].iloc[-1] / df["close"].iloc[-1]
    else:
        return 0


def calculate_short_term_metrics(df):
    """
    Calculate short-term trading metrics for pair evaluation.

    Args:
        df: DataFrame with OHLCV data

    Returns:
        Dictionary with short-term metrics
    """
    if df is None or len(df) < 20:
        return {"momentum": 0, "volatility_ratio": 1, "volume_trend": 0, "rsi_signal": 0, "price_trend": 0}

    try:
        # Short-term momentum (last 6 candles vs previous 6)
        recent_close = df["close"].iloc[-6:].mean()
        previous_close = df["close"].iloc[-12:-6].mean()
        momentum = (recent_close / previous_close - 1) * 100

        # Volatility ratio (recent vs historical)
        recent_range = (df["high"].iloc[-6:] - df["low"].iloc[-6:]).mean()
        historical_range = (df["high"].iloc[-24:-6] - df["low"].iloc[-24:-6]).mean()
        volatility_ratio = recent_range / historical_range if historical_range > 0 else 1

        # Volume trend
        recent_volume = df["volume"].iloc[-6:].mean()
        previous_volume = df["volume"].iloc[-12:-6].mean()
        volume_trend = recent_volume / previous_volume if previous_volume > 0 else 1

        # Basic RSI calculation
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        # RSI direction signal (-1 to 1 scale)
        rsi_signal = 0
        if not pd.isna(rsi.iloc[-1]) and not pd.isna(rsi.iloc[-2]):
            if rsi.iloc[-1] < 30:
                rsi_signal = 1  # Potential oversold (bullish)
            elif rsi.iloc[-1] > 70:
                rsi_signal = -1  # Potential overbought (bearish)

        # Recent price trend direction
        price_direction = df["close"].iloc[-1] > df["close"].iloc[-5]
        price_trend = 1 if price_direction else -1

        return {"momentum": momentum, "volatility_ratio": volatility_ratio, "volume_trend": volume_trend, "rsi_signal": rsi_signal, "price_trend": price_trend}
    except Exception as e:
        log(f"Error calculating short-term metrics: {e}", level="ERROR")
        return {"momentum": 0, "volatility_ratio": 1, "volume_trend": 0, "rsi_signal": 0, "price_trend": 0}


def calculate_correlation(price_data):
    """
    Calculate correlation matrix between pairs to avoid selecting highly correlated assets.

    Args:
        price_data: Dictionary with symbol -> price series

    Returns:
        DataFrame with correlation matrix
    """
    if not price_data:
        return None

    # Create DataFrame with all price series
    df_combined = pd.DataFrame(price_data)

    # Calculate correlation matrix
    try:
        corr_matrix = df_combined.corr(method="pearson")
        return corr_matrix
    except Exception as e:
        log(f"Error calculating correlation matrix: {e}", level="ERROR")
        return None


def load_pair_performance():
    """Load historical performance data for pairs."""
    global pair_performance

    try:
        if os.path.exists(PERFORMANCE_FILE):
            with performance_lock, open(PERFORMANCE_FILE, "r") as f:
                pair_performance = json.load(f)
        else:
            pair_performance = {}
    except Exception as e:
        log(f"Error loading pair performance data: {e}", level="ERROR")
        pair_performance = {}


def save_pair_performance():
    """Save historical performance data for pairs."""
    try:
        with performance_lock, open(PERFORMANCE_FILE, "w") as f:
            json.dump(pair_performance, f)
    except Exception as e:
        log(f"Error saving pair performance data: {e}", level="ERROR")


def update_pair_performance(symbol, win=None, pnl=None):
    """Update performance data for a specific pair."""
    global pair_performance

    load_pair_performance()

    with performance_lock:
        if symbol not in pair_performance:
            pair_performance[symbol] = {"total_trades": 0, "wins": 0, "losses": 0, "pnl": 0.0, "last_traded": None}

        if win is not None:
            pair_performance[symbol]["total_trades"] += 1
            if win:
                pair_performance[symbol]["wins"] += 1
            else:
                pair_performance[symbol]["losses"] += 1

        if pnl is not None:
            pair_performance[symbol]["pnl"] += pnl

        pair_performance[symbol]["last_traded"] = datetime.now().isoformat()

    save_pair_performance()


def get_performance_score(symbol):
    """
    Calculate performance score for a pair based on historical results.
    Uses PAIR_COOLING_PERIOD_HOURS for recency calculation and cooling period.

    Args:
        symbol: Trading symbol to evaluate

    Returns:
        float: Performance score (0.0-1.0) with higher being better
    """
    global pair_performance

    if symbol not in pair_performance:
        return 0

    data = pair_performance[symbol]

    # If fewer than 3 trades, return neutral score
    if data.get("total_trades", 0) < 3:
        return 0

    # Calculate win rate
    wins = data.get("wins", 0)
    total_trades = data.get("total_trades", 1)  # Avoid division by zero
    win_rate = wins / total_trades if total_trades > 0 else 0

    # Calculate average PnL
    avg_pnl = data.get("pnl", 0) / total_trades if total_trades > 0 else 0

    # Calculate recency factor using PAIR_COOLING_PERIOD_HOURS
    last_traded = datetime.fromisoformat(data.get("last_traded", datetime.min.isoformat())) if data.get("last_traded") else datetime.min
    hours_since_traded = (datetime.now() - last_traded).total_seconds() / 3600

    # Full weight if traded within the configured cooling period
    recency_factor = max(0, 1 - (hours_since_traded / PAIR_COOLING_PERIOD_HOURS))

    # Base score: 60% win rate, 20% profit, 20% recency
    score = (win_rate * 0.6) + (min(1, avg_pnl) * 0.2) + (recency_factor * 0.2)

    # Check for cooling period (3+ consecutive losses)
    # If the pair has had 3 or more consecutive losses, reduce its score
    last_3_trades_were_losses = False
    if "trade_history" in data and len(data.get("trade_history", [])) >= 3:
        last_3 = data["trade_history"][-3:]
        last_3_trades_were_losses = all(not trade.get("win", False) for trade in last_3)

        # Check if still in cooling period based on time since last trade
        if last_3_trades_were_losses and hours_since_traded < PAIR_COOLING_PERIOD_HOURS:
            log(f"{symbol} in cooling period: {hours_since_traded:.1f} of {PAIR_COOLING_PERIOD_HOURS} hours after 3+ losses", level="DEBUG")
            score *= 0.5  # Reduce score by 50% during cooling period

    return score


def select_active_symbols():
    """
    Select the most promising symbols for trading.
    Enhanced for short-term trading and small account optimization.
    Now using adaptive filtering instead of fallback mechanism.
    """
    # Initialize rejection tracking
    rejected_pairs = {}

    # Load performance data
    load_pair_performance()

    # Get runtime config for failure threshold and blocked symbols
    runtime_config = get_runtime_config()
    blocked_symbols = runtime_config.get("blocked_symbols", {})

    # Use the same threshold as fail_stats_tracker.py
    MAX_FAILURES_PER_SYMBOL = runtime_config.get("FAILURE_BLOCK_THRESHOLD", 30)
    FAILURE_PENALTY = 0.2

    # Load failure statistics
    failure_stats = load_failure_stats()

    # Load missed opportunities and symbol activity data
    missed_data = load_json_file(MISSED_OPPORTUNITIES_FILE)
    activity_data = load_json_file(SIGNAL_ACTIVITY_FILE)

    # Get all available symbols
    all_symbols = fetch_all_symbols()

    # 🔎 Mass block check before selection
    from datetime import datetime, timezone

    current_time = datetime.now(timezone.utc)
    active_blocked_count = 0
    active_blocked_details = []

    for symbol, block_info in blocked_symbols.items():
        block_until_str = block_info.get("block_until")
        if block_until_str:
            try:
                block_until = datetime.fromisoformat(block_until_str.replace("Z", "+00:00"))
                if block_until > current_time:
                    active_blocked_count += 1
                    time_remaining = block_until - current_time
                    hours_remaining = time_remaining.total_seconds() / 3600
                    active_blocked_details.append(f"{symbol} ({hours_remaining:.1f}h remaining)")
            except Exception:
                continue

    # Dynamic thresholds for blocking detection
    MIN_REQUIRED_PAIRS = 3
    WARNING_THRESHOLD = 0.3  # 30% blocked triggers warning
    CRITICAL_THRESHOLD = 0.5  # 50% blocked triggers critical alert

    if all_symbols:
        block_ratio = active_blocked_count / len(all_symbols)
        unblocked_count = len(all_symbols) - active_blocked_count
        is_critical = block_ratio >= CRITICAL_THRESHOLD
        is_warning = block_ratio >= WARNING_THRESHOLD
        is_insufficient = unblocked_count < MIN_REQUIRED_PAIRS * 2

        if is_critical or (is_warning and is_insufficient):
            active_blocked_details.sort()
            examples = active_blocked_details[:10]

            message = f"⚠️ Mass blocking detected: {active_blocked_count} of {len(all_symbols)} " f"symbols ({block_ratio:.1%})\n" f"Only {unblocked_count} symbols available for trading.\n"

            if examples:
                message += "Next unblocks:\n" + "\n".join(examples)

            if is_critical:
                message = "🛑 CRITICAL: " + message
            elif is_insufficient:
                message += f"\n⚡ Below recommended minimum ({MIN_REQUIRED_PAIRS * 2} pairs)"

            send_telegram_message(message, force=True)

            log_level = "ERROR" if is_critical else "WARNING"
            log(f"Mass blocking: {active_blocked_count}/{len(all_symbols)} " f"({block_ratio:.1%}) symbols blocked", level=log_level)

    # Determine pair limits based on account size using new function
    balance = get_cached_balance()
    min_dyn, max_dyn = get_pair_limits()

    # Adapt pair count based on market volatility
    market_volatility = get_market_volatility_index()
    if market_volatility > 1.5:  # High volatility - trending market
        # Focus on fewer pairs during high volatility
        max_dyn = min(max_dyn, 4)  # Limit to maximum 4 pairs
        log(f"Market volatility high ({market_volatility:.2f}) - limiting to max {max_dyn} pairs", level="INFO")
    elif market_volatility < 0.8:  # Low volatility - ranging market
        # Increase pairs during low volatility
        min_dyn = min(min_dyn + 2, max_dyn)
        log(f"Market volatility low ({market_volatility:.2f}) - increasing to min {min_dyn} pairs", level="INFO")

    log(f"Adaptive pair limits: min={min_dyn}, max={max_dyn}", level="INFO")

    # Fixed pairs and priority pairs
    fixed = FIXED_PAIRS
    priority_pairs = PRIORITY_SMALL_BALANCE_PAIRS if balance < 150 else []

    # Dictionary to store price data for correlation analysis
    price_data = {}

    # Collect data for all symbols
    dynamic_data = {}
    for s in all_symbols:
        if s in fixed:
            rejected_pairs[s] = "fixed_pair"
            continue

        # Check if symbol is auto-blocked
        is_blocked, block_info = is_symbol_blocked(s)
        if is_blocked:
            block_until = block_info.get("block_until", "unknown")
            rejected_pairs[s] = f"auto_blocked_until_{block_until}"
            log(f"{s} is auto-blocked until {block_until} (failures: {block_info.get('total_failures', 0)})", level="DEBUG")
            continue

        # Fetch 15min data for general analysis
        df_15m = fetch_symbol_data(s, timeframe="15m", limit=100)
        if df_15m is None or len(df_15m) < 20:
            rejected_pairs[s] = "insufficient_data"
            continue

        # Store price data for correlation analysis
        price_data[s] = df_15m["close"].values

        # Calculate standard metrics
        vol = calculate_volatility(df_15m)
        atr_vol = calculate_atr_volatility(df_15m)
        vol_avg = df_15m["volume"].mean()

        # Calculate short-term metrics
        st_metrics = calculate_short_term_metrics(df_15m)

        # Get historical performance score
        perf_score = get_performance_score(s)

        # Reject if performance score too low (only if not ignored)
        runtime_config = get_runtime_config()
        if not runtime_config.get("ignore_performance_score", False):
            # Adaptive threshold based on balance/aggressiveness
            base_threshold = 0.2
            balance = get_cached_balance()
            if balance < 100:
                base_threshold = 0.1
            elif balance < 250:
                base_threshold = 0.15

            if perf_score < base_threshold:
                rejected_pairs[s] = "low_score"
                log(f"{s} ⛔️ Rejected due to low performance score: {perf_score:.2f} < {base_threshold:.2f}", level="DEBUG")
                continue
        else:
            log(f"{s} ⚠️ Score={perf_score:.2f} ignored due to ignore_performance_score=True", level="DEBUG")

        # Always calculate volatility score if not rejected
        volatility_score = vol * 0.3 + atr_vol * 0.7

        # Current price
        current_price = df_15m["close"].iloc[-1]

        # Store all metrics
        dynamic_data[s] = {
            "volatility": volatility_score,
            "volume": vol_avg,
            "vol_to_volatility": vol_avg / (volatility_score + 0.00001),
            "price": current_price,
            "symbol": s,
            "momentum": st_metrics["momentum"],
            "volatility_ratio": st_metrics["volatility_ratio"],
            "volume_trend": st_metrics["volume_trend"],
            "rsi_signal": st_metrics["rsi_signal"],
            "price_trend": st_metrics["price_trend"],
            "performance_score": perf_score,
        }

        # Boost for missed opportunities
        if s in missed_data and missed_data[s].get("count", 0) >= 2:
            bonus = 0.2
            dynamic_data[s]["performance_score"] += bonus
            dynamic_data[s]["missed_bonus"] = bonus
            log(f"{s} ⬆️ Missed bonus applied: +{bonus}", level="DEBUG")

        # Boost for symbol activity
        activity_timestamps = activity_data.get(s, [])
        activity_count = len(activity_timestamps)
        if activity_count >= 10:
            activity_bonus = 0.1 + min(activity_count / 100, 0.2)  # capped at +0.2
            dynamic_data[s]["performance_score"] += activity_bonus
            dynamic_data[s]["activity_bonus"] = round(activity_bonus, 3)
            log(f"{s} ⬆️ Activity bonus applied: +{activity_bonus:.2f} (activity: {activity_count})", level="DEBUG")

        # Adjust score for failure penalties
        failures = failure_stats.get(s, {})
        total_failures = sum(failures.values())
        if total_failures >= MAX_FAILURES_PER_SYMBOL:
            penalty = FAILURE_PENALTY * (total_failures / MAX_FAILURES_PER_SYMBOL)
            dynamic_data[s]["failure_penalty"] = round(penalty, 3)
            dynamic_data[s]["performance_score"] = max(dynamic_data[s]["performance_score"] - penalty, 0)
            log(f"{s} ⚠️ Failure penalty applied: -{penalty:.2f} (failures: {total_failures})", level="DEBUG")

    # Get adaptive filter thresholds based on current number of candidates
    current_candidates = len(dynamic_data)
    adaptive_thresholds = get_adaptive_filter_thresholds(current_candidates, min_dyn)

    # Apply dynamic filters with adaptive thresholds
    filtered_data = {}
    for s, d in dynamic_data.items():
        atr = d.get("volatility", 0)
        volume = d.get("volume", 0)
        # Set default values for missing indicators
        adx = 20  # Default ADX value
        bb_width = 0.03  # Default Bollinger Bands width

        # Determine market regime
        market_regime = get_market_regime_from_indicators(adx, bb_width)

        log(f"{s} FILTER CHECK: ATR={atr:.4f}, Vol={volume:.0f}, Regime={market_regime}", level="DEBUG")

        # Apply filter with adaptive thresholds
        should_filter, reason = should_filter_pair(s, atr, volume, market_regime, adaptive_thresholds)

        if should_filter:
            rejected_pairs[s] = reason["reason"]
            log(f"{s} ⛔️ Filtered: {reason['reason']} (ATR={atr:.4f}, Vol={volume:.0f}, Regime={market_regime})", level="DEBUG")
        else:
            filtered_data[s] = d

    # Calculate correlation matrix if we have enough pairs
    corr_matrix = calculate_correlation(price_data) if len(price_data) > 1 else None

    # Different selection strategy based on account size
    if balance < 150:
        # For small accounts: prioritize short-term momentum and low price
        sorted_dyn = []

        for s, data in filtered_data.items():
            # Calculate composite score for small accounts
            short_term_score = (
                data["momentum"] * 0.4  # 40% weight to recent momentum
                + data["volume_trend"] * 0.3  # 30% weight to volume trend
                + (data["performance_score"] * 2)  # Double weight to historical performance
                + data["rsi_signal"] * 0.5  # 50% weight to RSI signal
            )

            # Add micro-trade suitability score based on price
            micro_trade_suitability = 0
            price = data["price"]
            if price < 1:
                micro_trade_suitability += 3  # Strong bonus for ultra-low price assets
            elif price < 10:
                micro_trade_suitability += 2  # Medium bonus for low price assets
            elif price < 50:
                micro_trade_suitability += 1  # Small bonus for medium price assets

            # Add to short-term score with 50% weight
            short_term_score += micro_trade_suitability * 0.5
            data["micro_trade_suitability"] = micro_trade_suitability

            # Price factor - strongly prefer lower-priced assets
            price_factor = 1 / (data["price"] + 0.1)

            # Final score combines short-term signals and price factor
            final_score = short_term_score * price_factor

            # Skip pairs in cooling period
            if "trade_history" in pair_performance.get(s, {}) and len(pair_performance[s]["trade_history"]) >= 3:
                last_3 = pair_performance[s]["trade_history"][-3:]
                if all(not t.get("win", False) for t in last_3):
                    # Get time since last trade
                    last_traded = datetime.fromisoformat(pair_performance[s].get("last_traded", datetime.min.isoformat())) if pair_performance[s].get("last_traded") else datetime.min
                    hours_since_traded = (datetime.now() - last_traded).total_seconds() / 3600

                    # Check if still in cooling period
                    if hours_since_traded < PAIR_COOLING_PERIOD_HOURS:
                        log(f"Skipping {s} due to cooling period: {hours_since_traded:.1f} of {PAIR_COOLING_PERIOD_HOURS} hours after 3+ losses", level="INFO")
                        rejected_pairs[s] = "cooling_period"
                        continue
                    else:
                        log(f"Pair {s} had 3+ losses but cooling period ({PAIR_COOLING_PERIOD_HOURS}h) has expired", level="INFO")

            sorted_dyn.append((s, final_score))

        # Sort by final score
        sorted_dyn.sort(key=lambda x: x[1], reverse=True)

        # Create final list prioritizing specified pairs
        final_pairs = []

        # First add priority pairs
        for pair in priority_pairs:
            if pair in filtered_data:
                final_pairs.append(pair)
                log(f"Added priority pair for small account: {pair}", level="INFO")

        # Then add other pairs, avoiding high correlation
        remaining_slots = min(min_dyn, max_dyn) - len(final_pairs)
        if remaining_slots > 0:
            added_pairs = set(final_pairs)

            for pair, score in sorted_dyn:
                if pair in added_pairs or pair in fixed:
                    rejected_pairs[pair] = "already_added"
                    continue

                # Check correlation with already selected pairs
                if corr_matrix is not None and len(added_pairs) > 0:
                    highly_correlated = False
                    correlation_threshold = 0.9

                    for added_pair in added_pairs:
                        if pair in corr_matrix.index and added_pair in corr_matrix.columns:
                            if abs(corr_matrix.loc[pair, added_pair]) > correlation_threshold:
                                highly_correlated = True
                                log(f"Skipping {pair} due to high correlation with {added_pair} (threshold: {correlation_threshold})", level="DEBUG")
                                break

                    if highly_correlated:
                        rejected_pairs[pair] = "high_correlation"
                        continue

                final_pairs.append(pair)
                added_pairs.add(pair)
                remaining_slots -= 1
                log(f"Added dynamic pair: {pair} (score: {score:.2f})", level="DEBUG")

                if remaining_slots <= 0:
                    break

        selected_dyn = final_pairs
    else:
        # For larger accounts: standard algorithm with short-term enhancements
        pairs_with_scores = []

        for s, data in filtered_data.items():
            # Composite score balancing short-term and standard metrics
            composite_score = (
                data["volatility"] * data["volume"] * 0.5  # Standard volatility & volume (50%)
                + data["momentum"] * 10 * 0.3  # Short-term momentum (30%)
                + data["performance_score"] * 0.2  # Historical performance (20%)
            )

            # Skip pairs in cooling period
            if "trade_history" in pair_performance.get(s, {}) and len(pair_performance[s]["trade_history"]) >= 3:
                last_3 = pair_performance[s]["trade_history"][-3:]
                if all(not t.get("win", False) for t in last_3):
                    # Get time since last trade
                    last_traded = datetime.fromisoformat(pair_performance[s].get("last_traded", datetime.min.isoformat())) if pair_performance[s].get("last_traded") else datetime.min
                    hours_since_traded = (datetime.now() - last_traded).total_seconds() / 3600

                    # Check if still in cooling period
                    if hours_since_traded < PAIR_COOLING_PERIOD_HOURS:
                        log(f"Skipping {s} due to cooling period: {hours_since_traded:.1f} of {PAIR_COOLING_PERIOD_HOURS} hours after 3+ losses", level="INFO")
                        rejected_pairs[s] = "cooling_period"
                        continue
                    else:
                        log(f"Pair {s} had 3+ losses but cooling period ({PAIR_COOLING_PERIOD_HOURS}h) has expired", level="INFO")

            pairs_with_scores.append((s, composite_score))

        # Sort by composite score
        sorted_dyn = sorted(pairs_with_scores, key=lambda x: x[1], reverse=True)

        # Filter for correlation
        uncorrelated_pairs = []
        added_pairs = set()

        for pair, score in sorted_dyn:
            if pair in added_pairs:
                rejected_pairs[pair] = "already_added"
                continue

            # Check correlation with already selected pairs
            if corr_matrix is not None and len(added_pairs) > 0:
                highly_correlated = False
                correlation_threshold = 0.9

                for added_pair in added_pairs:
                    if pair in corr_matrix.index and added_pair in corr_matrix.columns:
                        if abs(corr_matrix.loc[pair, added_pair]) > correlation_threshold:
                            highly_correlated = True
                            break

                if highly_correlated:
                    rejected_pairs[pair] = "high_correlation"
                    continue

            uncorrelated_pairs.append(pair)
            added_pairs.add(pair)

            # Limit selection
            if len(uncorrelated_pairs) >= max_dyn:
                break

        # Ensure we have at least min_dyn pairs
        dyn_count = max(min_dyn, min(max_dyn, len(uncorrelated_pairs)))
        selected_dyn = uncorrelated_pairs[:dyn_count]

    # Combine fixed and dynamic pairs
    active_symbols = fixed + selected_dyn

    # 🆘 EMERGENCY RECOVERY: Check if too few pairs remain
    MIN_ACTIVE_PAIRS = 3
    if len(active_symbols) < MIN_ACTIVE_PAIRS:
        log(f"🛑 Only {len(active_symbols)} pairs passed filtering. Triggering emergency recovery...", level="WARNING")

        # Get blocked symbols to avoid them in recovery
        blocked_symbols = get_runtime_config().get("blocked_symbols", {})

        # 🔁 Try to recover from inactive_candidates.json if needed
        inactive_candidates = load_json_file(INACTIVE_CANDIDATES_FILE)
        for entry in inactive_candidates:
            symbol = entry.get("symbol")
            if symbol and symbol not in active_symbols and symbol not in blocked_symbols:
                active_symbols.append(symbol)
                log(f"[Fallback] Added {symbol} from inactive_candidates.json", level="INFO")
                if len(active_symbols) >= MIN_ACTIVE_PAIRS:
                    break

        # ✅ If recovery worked — skip manual fallback
        if len(active_symbols) >= MIN_ACTIVE_PAIRS:
            log(f"✅ Emergency recovery succeeded using inactive_candidates.json. Total: {len(active_symbols)}", level="INFO")
        else:
            # Temporarily relax filters
            emergency_thresholds = {
                "min_atr_percent": 0.002,  # 0.2% ATR minimum
                "min_volume_usdc": 400,  # 400 USDC minimum volume
            }

            # Look for fallback candidates
            fallback_candidates = []

        for symbol in rejected_pairs:
            if symbol in active_symbols or symbol in blocked_symbols:
                continue

            # Re-evaluate with relaxed thresholds
            if symbol in dynamic_data:
                data = dynamic_data[symbol]
                atr = data.get("volatility", 0)
                volume = data.get("volume", 0)

                # Check against emergency thresholds
                should_filter, reason = should_filter_pair(symbol, atr, volume, market_regime="neutral", thresholds=emergency_thresholds)

                if not should_filter:
                    # Sort by volume for priority
                    vol_usdc = volume * data.get("price", 0)
                    fallback_candidates.append((symbol, vol_usdc))

        # Sort by volume (highest first)
        fallback_candidates.sort(key=lambda x: x[1], reverse=True)

        # Add best candidates up to minimum required
        needed = MIN_ACTIVE_PAIRS - len(active_symbols)
        recovered = [s for s, _ in fallback_candidates[:needed]]

        if recovered:
            active_symbols.extend(recovered)

            # Send Telegram notification
            send_telegram_message(f"🆘 Emergency fallback triggered:\n" f"Recovered symbols: {', '.join(recovered)}\n" f"Total active pairs now: {len(active_symbols)}", force=True)

            log(f"Emergency recovery added: {recovered}. Total pairs: {len(active_symbols)}", level="INFO")
        else:
            log("No suitable symbols found for emergency recovery", level="ERROR")
            send_telegram_message(f"⚠️ CRITICAL: Only {len(active_symbols)} active pairs and no recovery candidates found", force=True)

    # Initialize relax_factor for new active symbols
    try:
        filter_path = "data/filter_adaptation.json"
        filter_data = load_json_file(filter_path)
        updated = False

        for symbol in active_symbols:
            normalized = symbol.replace("/", "").upper()
            if normalized not in filter_data:
                filter_data[normalized] = {"relax_factor": get_runtime_config().get("relax_factor", 0.35)}
                log(f"[FilterAdapt] Initialized relax_factor for {symbol}", level="INFO")
                updated = True

        if updated:
            save_json_file(filter_path, filter_data)
            log("[FilterAdapt] Updated filter_adaptation.json with new symbols", level="INFO")
    except Exception as e:
        log(f"[FilterAdapt] Error initializing relax_factor for active symbols: {e}", level="ERROR")

    # Calculate final rejection statistics
    final_selected = set(selected_dyn)
    total_analyzed = len(all_symbols)
    total_selected = len(selected_dyn)
    total_ultimately_rejected = total_analyzed - total_selected

    # Count rejection reasons for final rejected pairs only
    final_rejection_reasons = {}
    for symbol in all_symbols:
        if symbol not in final_selected and symbol not in fixed:
            # Find the last rejection reason for this symbol
            if symbol in rejected_pairs:
                reason = rejected_pairs[symbol]
                final_rejection_reasons[reason] = final_rejection_reasons.get(reason, 0) + 1

    # Log clearer statistics
    log(f"[Pair Selector] {total_analyzed} pairs analyzed, {total_selected} selected, {total_ultimately_rejected} ultimately rejected", level="INFO")
    log(f"[Pair Selector] {len(filtered_data)} pairs passed filters", level="INFO")

    # Log final rejection reasons
    if final_rejection_reasons:
        log("[Final Rejection Stats]:", level="INFO")
        for reason, count in final_rejection_reasons.items():
            log(f"  {reason}: {count} pairs", level="INFO")

    # Log and save results
    log(f"Selected {len(active_symbols)} active symbols: {active_symbols}", level="INFO")

    try:
        os.makedirs(os.path.dirname(SYMBOLS_FILE), exist_ok=True)
        with symbols_file_lock, open(SYMBOLS_FILE, "w") as f:
            json.dump(active_symbols, f)
        log(f"Saved active symbols to {SYMBOLS_FILE}", level="INFO")
    except Exception as e:
        log(f"Error saving active symbols to {SYMBOLS_FILE}: {e}", level="ERROR")

    # Send notification with improved summary
    msg = (
        f"🔄 Symbol rotation completed:\n"
        f"Total pairs: {len(active_symbols)}\n"
        f"Fixed: {len(fixed)}, Dynamic: {len(selected_dyn)}\n"
        f"Balance: {balance:.2f} USDC\n"
        f"Market volatility: {market_volatility:.2f}"
    )

    if balance < 150 and priority_pairs:
        priority_in_selection = [p for p in priority_pairs if p in active_symbols]
        if priority_in_selection:
            msg += f"\nPriority pairs included: {', '.join(priority_in_selection)}"

    send_telegram_message(msg, force=True)

    return active_symbols


def get_pair_limits():
    """
    Get adaptive pair limits based on account balance
    """
    balance = get_cached_balance()
    if balance < 150:
        return 6, 8
    elif balance < 250:
        return 8, 10
    else:
        return 10, 12


def get_adaptive_filter_thresholds(current_candidates, target_minimum):
    """
    Adaptively adjust filter thresholds if not enough pairs pass

    Args:
        current_candidates: Number of pairs currently available for filtering
        target_minimum: Minimum required pairs

    Returns:
        dict: Adaptive thresholds for filtering
    """
    runtime_config = get_runtime_config()

    base_thresholds = {"min_atr_percent": runtime_config.get("atr_threshold_percent", 1.5) / 100, "min_volume_usdc": runtime_config.get("volume_threshold_usdc", 2000)}

    # If we have fewer candidates than needed, relax thresholds
    if current_candidates < target_minimum:
        relax_factor = 0.5  # Can be adjusted based on how aggressive we want to be
        base_thresholds["min_atr_percent"] *= relax_factor
        base_thresholds["min_volume_usdc"] *= relax_factor
        log(
            f"⚠️ Only {current_candidates} candidates for {target_minimum} target. "
            f"Relaxing thresholds: ATR={base_thresholds['min_atr_percent'] * 100:.2f}%, "
            f"Vol={base_thresholds['min_volume_usdc']:.0f} USDC",
            level="WARNING",
        )

    return base_thresholds


def get_update_interval():
    """
    Determine the optimal symbol rotation interval based on:
    1. Account size
    2. Market volatility
    3. Trading hours
    """
    balance = get_cached_balance()
    base_interval = BASE_UPDATE_INTERVAL

    # Adjust for account size
    if balance < 120:
        account_factor = 0.75  # 25% быстрее для маленьких счетов
    elif balance < 200:
        account_factor = 0.9  # 10% быстрее для средних счетов
    else:
        account_factor = 1.0

    # Adjust for trading hours
    hour_factor = 0.75 if is_optimal_trading_hour() else 1.0

    # Adjust for market volatility
    market_volatility = get_market_volatility_index()
    if market_volatility > 1.5:
        volatility_factor = 0.7  # 30% быстрее при высокой волатильности
    elif market_volatility > 1.2:
        volatility_factor = 0.85  # 15% быстрее при средней волатильности
    else:
        volatility_factor = 1.0

    # Ensure minimum interval from config
    final_interval = max(PAIR_ROTATION_MIN_INTERVAL, int(base_interval * account_factor * hour_factor * volatility_factor))
    return final_interval


def start_symbol_rotation(stop_event):
    """
    Start periodic symbol rotation with adaptive interval.
    """
    while not stop_event.is_set():
        try:
            # Get the adaptive update interval
            update_interval = get_update_interval()

            # Perform symbol rotation
            select_active_symbols()

            # Sleep for the dynamic interval
            log(f"Next symbol rotation in {update_interval/60:.1f} minutes", level="DEBUG")

            # Sleep in smaller increments to respond faster to stop events
            sleep_interval = 10  # seconds
            for _ in range(int(update_interval / sleep_interval)):
                if stop_event.is_set():
                    break
                time.sleep(sleep_interval)

        except Exception as e:
            log(f"Symbol rotation error: {e}", level="ERROR")
            send_telegram_message(f"⚠️ Symbol rotation failed: {e}", force=True)
            time.sleep(60)  # Short delay before retry on error


missed_opportunities = {}


def track_missed_opportunities():
    """Track pairs that were missed but performed well."""
    global missed_opportunities

    all_pairs = fetch_all_symbols()

    active_pairs = []
    if os.path.exists(SYMBOLS_FILE):
        with symbols_file_lock, open(SYMBOLS_FILE, "r") as f:
            active_pairs = json.load(f)

    missed_opportunities = {}
    missed_logs = []  # Новый список для аккуратного сбора логов

    for pair in all_pairs:
        if pair in active_pairs:
            continue

        df = fetch_symbol_data(pair, timeframe="15m", limit=96)
        if df is None or len(df) < 20:
            continue

        price_24h_ago = df["close"].iloc[0]
        price_now = df["close"].iloc[-1]
        potential_profit = ((price_now - price_24h_ago) / price_24h_ago) * 100

        if abs(potential_profit) > 5:
            metrics = calculate_short_term_metrics(df)
            atr_vol = calculate_atr_volatility(df)
            avg_volume = df["volume"].mean()

            missed_opportunities[pair] = {
                "count": missed_opportunities.get(pair, {}).get("count", 0) + 1,
                "profit": missed_opportunities.get(pair, {}).get("profit", 0) + potential_profit,
                "momentum": metrics.get("momentum", 0),
                "atr_volatility": atr_vol,
                "avg_volume": avg_volume,
            }

            if abs(potential_profit) > 10:
                # Вместо логирования сразу — добавляем в список
                missed_logs.append(f"- {pair} ({potential_profit:.2f}% profit, Momentum: {metrics.get('momentum', 0):.2f}%, " f"ATR vol: {atr_vol:.4f}, Avg volume: {avg_volume:,.0f})")

    # Групповое логирование одним сообщением
    if missed_logs:
        log("[Missed Opportunities]\n" + "\n".join(missed_logs), level="WARNING")

    # Сохраняем файл
    try:
        with open(MISSED_OPPORTUNITIES_FILE, "w") as f:
            json.dump(missed_opportunities, f, indent=2)
        log(f"Saved missed opportunities to {MISSED_OPPORTUNITIES_FILE}", level="INFO")
    except Exception as e:
        log(f"Error saving missed opportunities: {e}", level="ERROR")
