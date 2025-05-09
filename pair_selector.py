# pair_selector.py
import json
import os
import threading
import time
from datetime import datetime
from threading import Lock

import pandas as pd

from common.config_loader import (
    DRY_RUN,
    FIXED_PAIRS,
    MAX_DYNAMIC_PAIRS,
    MIN_DYNAMIC_PAIRS,
    MISSED_OPPORTUNITIES_FILE,
    PAIR_COOLING_PERIOD_HOURS,
    PAIR_ROTATION_MIN_INTERVAL,
    PRIORITY_SMALL_BALANCE_PAIRS,
    TRADING_HOURS_FILTER,
    USDC_SYMBOLS,
    USDT_SYMBOLS,
    USE_TESTNET,
)
from core.binance_api import convert_symbol
from core.exchange_init import exchange
from core.fail_stats_tracker import FAIL_STATS_FILE
from symbol_activity_tracker import SIGNAL_ACTIVITY_FILE
from telegram.telegram_utils import send_telegram_message
from utils_core import get_cached_balance, get_market_volatility_index, safe_call_retry
from utils_logging import log

SYMBOLS_FILE = "data/dynamic_symbols.json"
PERFORMANCE_FILE = "data/pair_performance.json"
# Adaptive rotation interval - more frequent for small accounts and high volatility
BASE_UPDATE_INTERVAL = 60 * 15  # 15 минут вместо 30
symbols_file_lock = Lock()
performance_lock = Lock()

DRY_RUN_FALLBACK_SYMBOLS = USDT_SYMBOLS if USE_TESTNET else USDC_SYMBOLS

# Historical performance tracking
pair_performance = {}

# Добавить глобальную переменную
_last_logged_hour = None


def load_json_file(filepath):
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except Exception:
        return {}


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


def is_peak_trading_hour():
    """
    Check if current time is during peak trading hours.
    Log only once per hour to avoid spam.
    """
    global _last_logged_hour

    if not TRADING_HOURS_FILTER:
        return True

    now = datetime.utcnow()
    hour_utc = now.hour

    # Log only if hour changed
    if _last_logged_hour != hour_utc:
        _last_logged_hour = hour_utc

        # Weekend check (Saturday=5, Sunday=6)
        if now.weekday() >= 5:
            log(f"[Time Check] Current UTC hour: {hour_utc} — Weekend (inactive)", level="INFO")
            return False

        # Peak hours: European/US overlap and Asian open
        peak_hours = [0, 1, 2, 8, 9, 10, 11, 12, 13, 14, 15, 16, 20, 21, 22]

        if hour_utc in peak_hours:
            log(f"[Time Check] Current UTC hour: {hour_utc} — Trading active (peak hour)", level="INFO")
        else:
            log(f"[Time Check] Current UTC hour: {hour_utc} — Trading inactive (off-peak)", level="INFO")

    # Реальная проверка
    return hour_utc in [0, 1, 2, 8, 9, 10, 11, 12, 13, 14, 15, 16, 20, 21, 22]


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
    """
    # Load performance data
    load_pair_performance()

    # Load failure statistics
    failure_stats = load_failure_stats()
    MAX_FAILURES_PER_SYMBOL = 6
    FAILURE_PENALTY = 0.2

    # Load missed opportunities and symbol activity data
    missed_data = load_json_file(MISSED_OPPORTUNITIES_FILE)
    activity_data = load_json_file(SIGNAL_ACTIVITY_FILE)

    # Determine pair limits based on account size
    balance = get_cached_balance()

    if balance < 120:
        min_dyn = min(MIN_DYNAMIC_PAIRS, 3)  # Max 3 dynamic pairs for very small accounts
        max_dyn = min(MAX_DYNAMIC_PAIRS, 5)  # Max 5 dynamic pairs for very small accounts
    elif balance < 200:
        min_dyn = min(MIN_DYNAMIC_PAIRS, 5)
        max_dyn = min(MAX_DYNAMIC_PAIRS, 8)
    else:
        min_dyn = MIN_DYNAMIC_PAIRS
        max_dyn = MAX_DYNAMIC_PAIRS

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

    # Get all available symbols
    all_symbols = fetch_all_symbols()
    fixed = FIXED_PAIRS

    # Priority pairs for small accounts
    priority_pairs = PRIORITY_SMALL_BALANCE_PAIRS if balance < 150 else []

    # Dictionary to store price data for correlation analysis
    price_data = {}

    # Collect data for all symbols
    dynamic_data = {}
    for s in all_symbols:
        if s in fixed:
            continue

        # Fetch 15min data for general analysis
        df_15m = fetch_symbol_data(s, timeframe="15m", limit=100)
        if df_15m is None or len(df_15m) < 20:
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

        # Calculate volatility score combining different metrics
        volatility_score = vol * 0.3 + atr_vol * 0.7  # Weighted towards ATR-based volatility

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

        # 🔼 Boost for missed opportunities
        if s in missed_data and missed_data[s].get("count", 0) >= 2:
            bonus = 0.2
            dynamic_data[s]["performance_score"] += bonus
            dynamic_data[s]["missed_bonus"] = bonus
            log(f"{s} ⬆️ Missed bonus applied: +{bonus}", level="DEBUG")

        # 🔼 Boost for symbol activity
        activity_count = activity_data.get(s, 0)
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

    # Calculate correlation matrix if we have enough pairs
    corr_matrix = calculate_correlation(price_data) if len(price_data) > 1 else None

    # Different selection strategy based on account size
    if balance < 150:
        # For small accounts: prioritize short-term momentum and low price
        sorted_dyn = []

        for s, data in dynamic_data.items():
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

            # Skip pairs in cooling period (3+ consecutive losses within PAIR_COOLING_PERIOD_HOURS)
            if "trade_history" in pair_performance.get(s, {}) and len(pair_performance[s]["trade_history"]) >= 3:
                last_3 = pair_performance[s]["trade_history"][-3:]
                if all(not t.get("win", False) for t in last_3):
                    # Get time since last trade
                    last_traded = datetime.fromisoformat(pair_performance[s].get("last_traded", datetime.min.isoformat())) if pair_performance[s].get("last_traded") else datetime.min
                    hours_since_traded = (datetime.now() - last_traded).total_seconds() / 3600

                    # Check if still in cooling period
                    if hours_since_traded < PAIR_COOLING_PERIOD_HOURS:
                        log(f"Skipping {s} due to cooling period: {hours_since_traded:.1f} of {PAIR_COOLING_PERIOD_HOURS} hours after 3+ losses", level="INFO")
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
            if pair in dynamic_data:
                final_pairs.append(pair)
                log(f"Added priority pair for small account: {pair}", level="INFO")

        # Then add other pairs, avoiding high correlation
        remaining_slots = min(min_dyn, max_dyn) - len(final_pairs)
        if remaining_slots > 0:
            added_pairs = set(final_pairs)

            for pair, score in sorted_dyn:
                if pair in added_pairs or pair in fixed:
                    continue

                # Check correlation with already selected pairs
                if corr_matrix is not None and len(added_pairs) > 0:
                    highly_correlated = False
                    for added_pair in added_pairs:
                        if abs(corr_matrix.loc[pair, added_pair]) > 0.8:  # 0.8 correlation threshold
                            highly_correlated = True
                            log(f"Skipping {pair} due to high correlation with {added_pair}", level="DEBUG")
                            break

                    if highly_correlated:
                        continue

                final_pairs.append(pair)
                added_pairs.add(pair)
                remaining_slots -= 1
                log(f"Added dynamic pair: {pair} (score: {score:.2f})", level="DEBUG")

                if remaining_slots <= 0:
                    break

        selected_dyn = final_pairs

        # Ensure minimum number of pairs
        if len(selected_dyn) < min_dyn:
            for pair, _ in sorted_dyn:
                if pair not in selected_dyn and pair not in fixed:
                    selected_dyn.append(pair)
                    if len(selected_dyn) >= min_dyn:
                        break
    else:
        # For larger accounts: standard algorithm with short-term enhancements
        pairs_with_scores = []

        for s, data in dynamic_data.items():
            # Composite score balancing short-term and standard metrics
            composite_score = (
                data["volatility"] * data["volume"] * 0.5  # Standard volatility & volume (50%)
                + data["momentum"] * 10 * 0.3  # Short-term momentum (30%)
                + data["performance_score"] * 0.2  # Historical performance (20%)
            )

            # Skip pairs in cooling period (3+ consecutive losses within PAIR_COOLING_PERIOD_HOURS)
            if "trade_history" in pair_performance.get(s, {}) and len(pair_performance[s]["trade_history"]) >= 3:
                last_3 = pair_performance[s]["trade_history"][-3:]
                if all(not t.get("win", False) for t in last_3):
                    # Get time since last trade
                    last_traded = datetime.fromisoformat(pair_performance[s].get("last_traded", datetime.min.isoformat())) if pair_performance[s].get("last_traded") else datetime.min
                    hours_since_traded = (datetime.now() - last_traded).total_seconds() / 3600

                    # Check if still in cooling period
                    if hours_since_traded < PAIR_COOLING_PERIOD_HOURS:
                        log(f"Skipping {s} due to cooling period: {hours_since_traded:.1f} of {PAIR_COOLING_PERIOD_HOURS} hours after 3+ losses", level="INFO")
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
                continue

            # Check correlation with already selected pairs
            if corr_matrix is not None and len(added_pairs) > 0:
                highly_correlated = False
                for added_pair in added_pairs:
                    if abs(corr_matrix.loc[pair, added_pair]) > 0.8:  # 0.8 correlation threshold
                        highly_correlated = True
                        break

                if highly_correlated:
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

    # Log and save results
    log(f"Selected {len(active_symbols)} active symbols: {active_symbols}", level="INFO")

    try:
        os.makedirs(os.path.dirname(SYMBOLS_FILE), exist_ok=True)
        with symbols_file_lock, open(SYMBOLS_FILE, "w") as f:
            json.dump(active_symbols, f)
        log(f"Saved active symbols to {SYMBOLS_FILE}", level="INFO")
    except Exception as e:
        log(f"Error saving active symbols to {SYMBOLS_FILE}: {e}", level="ERROR")

    # Send notification
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

    # Track missed opportunities after rotation
    threading.Thread(target=track_missed_opportunities, daemon=True).start()

    return active_symbols


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
    hour_factor = 0.75 if is_peak_trading_hour() else 1.0  # 25% быстрее в часы пик

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
