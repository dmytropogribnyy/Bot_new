# core/dynamic_filters.py
"""
Dynamic pair filtering system for BinanceBot
Implements adaptive filter thresholds based on market conditions and account size
Optimized for 120 USDC deposit target
"""

from core.aggressiveness_controller import get_aggressiveness_score
from core.filter_adaptation import get_adaptive_relax_factor
from utils_core import get_cached_balance, get_runtime_config
from utils_logging import log


def get_dynamic_filter_thresholds(symbol, market_regime=None):
    """
    Dynamic filter thresholds optimized for small USDC deposits (e.g. 120–250 USDC)

    Args:
        symbol (str): Trading pair symbol
        market_regime (str, optional): Current market regime (breakout, trend, flat, neutral)

    Returns:
        dict: Filter thresholds including min_atr_percent and min_volume_usdc
    """
    # Base values (slightly lowered for smaller accounts)
    base_atr_percent = 0.17
    base_volume_usdc = 14000

    # Get current balance and aggressiveness score
    balance = get_cached_balance()
    aggr_score = get_aggressiveness_score()

    # Relax factor from runtime_config
    relax = get_runtime_config().get("relax_factor", 0.35)

    # Market regime adjustments
    if market_regime == "breakout":
        base_atr_percent *= 0.75
        base_volume_usdc *= 0.75
        log(f"{symbol} Market regime: Breakout (-25%)", level="DEBUG")
    elif market_regime == "trend":
        base_atr_percent *= 0.85
        base_volume_usdc *= 0.85
        log(f"{symbol} Market regime: Trend (-15%)", level="DEBUG")
    elif market_regime == "flat":
        base_atr_percent *= 1.05
        log(f"{symbol} Market regime: Flat (+5%)", level="DEBUG")

    # Balance-based adjustment
    if balance < 100:
        account_factor = 0.85
        log(f"{symbol} Balance adjustment: Ultra-small (-15%)", level="DEBUG")
    elif balance < 150:
        account_factor = 0.9
        log(f"{symbol} Balance adjustment: Small (-10%)", level="DEBUG")
    else:
        account_factor = 1.0

    base_atr_percent *= account_factor
    base_volume_usdc *= account_factor

    # Aggressiveness adjustment
    if aggr_score > 0.7:
        base_atr_percent *= 0.9
        base_volume_usdc *= 0.9
        log(f"{symbol} Aggression adjustment: High (-10%)", level="DEBUG")

    # Apply relax factor
    base_atr_percent *= 1 - relax
    base_volume_usdc *= 1 - relax

    # Hard floors (safety limits)
    min_atr_percent = max(base_atr_percent, 0.11)
    min_volume_usdc = max(base_volume_usdc, 9500)

    log(f"{symbol} Final filter thresholds: ATR%={min_atr_percent*100:.2f}%, Volume={min_volume_usdc:,} USDC", level="INFO")
    return {"min_atr_percent": min_atr_percent, "min_volume_usdc": min_volume_usdc}


def should_filter_pair(symbol, atr_percent, volume_usdc, market_regime=None):
    """
    Determine if a pair should be filtered out based on dynamic thresholds
    with additional relaxation based on per-symbol configuration.

    Args:
        symbol (str): Trading pair symbol
        atr_percent (float): Current ATR percentage
        volume_usdc (float): Current 24h volume in USDC
        market_regime (str, optional): Current market regime

    Returns:
        tuple: (bool, dict) - (Should filter, Reason dict)
    """
    # Get dynamic thresholds
    thresholds = get_dynamic_filter_thresholds(symbol, market_regime)

    # Get per-symbol relax_factor
    relax = get_adaptive_relax_factor(symbol)

    # Adjust thresholds with relax_factor
    adjusted_atr = thresholds["min_atr_percent"] * (1 - relax)
    adjusted_vol = thresholds["min_volume_usdc"] * (1 - relax)

    # Debug logging
    log(f"{symbol} [Thresholds] ATR={atr_percent:.4f} vs {adjusted_atr:.4f}, Volume={volume_usdc:,.0f} vs {adjusted_vol:,.0f}", level="DEBUG")

    # Check ATR percent
    if atr_percent < adjusted_atr:
        return True, {"reason": "low_volatility", "current": atr_percent, "threshold": adjusted_atr}

    # Check volume
    if volume_usdc < adjusted_vol:
        return True, {"reason": "low_volume", "current": volume_usdc, "threshold": adjusted_vol}

    # Pair passes all filters
    return False, {"reason": "passed"}


def get_market_regime_from_indicators(adx, bb_width, recent_candles=None):
    """
    Determine market regime based on technical indicators

    Args:
        adx (float): Average Directional Index value
        bb_width (float): Bollinger Bands width relative to price
        recent_candles (list, optional): Recent price candles for additional analysis

    Returns:
        str: Market regime (breakout, trend, flat, neutral)
    """
    # Breakout detection - high ADX and wide BB
    if adx > 25 and bb_width > 0.05:
        return "breakout"

    # Strong trend - high ADX
    elif adx > 20:
        return "trend"

    # Flat market - low ADX
    elif adx < 15:
        return "flat"

    # Neutral/normal market
    else:
        return "neutral"


def apply_filter_to_pairs(pairs, market_data, min_pairs=5):
    """
    Apply dynamic filters to a list of pairs

    Args:
        pairs (list): List of trading pairs to filter
        market_data (dict): Market data including ATR and volume
        min_pairs (int, optional): Minimum number of pairs to return

    Returns:
        list: Filtered pairs that pass thresholds
    """
    filtered_pairs = []
    rejected_pairs = []

    for symbol in pairs:
        # Get market data for this pair
        pair_data = market_data.get(symbol, {})
        atr_percent = pair_data.get("atr_percent", 0)
        volume_usdc = pair_data.get("volume_usdc", 0)
        adx = pair_data.get("adx", 0)
        bb_width = pair_data.get("bb_width", 0)

        # Determine market regime
        market_regime = get_market_regime_from_indicators(adx, bb_width)

        # Apply filter
        should_filter, reason = should_filter_pair(symbol, atr_percent, volume_usdc, market_regime)

        if not should_filter:
            filtered_pairs.append(symbol)
        else:
            rejected_pairs.append({"symbol": symbol, "reason": reason})

    # Ensure we have minimum number of pairs
    if len(filtered_pairs) < min_pairs and rejected_pairs:
        # Sort rejected pairs by closeness to threshold
        if rejected_pairs and "threshold" in rejected_pairs[0]["reason"]:
            rejected_pairs.sort(key=lambda x: abs(x["reason"]["threshold"] - x["reason"]["current"]))

            # Add pairs until we reach minimum
            while len(filtered_pairs) < min_pairs and rejected_pairs:
                pair_to_add = rejected_pairs.pop(0)
                filtered_pairs.append(pair_to_add["symbol"])
                log(f"Added {pair_to_add['symbol']} despite not meeting filters to ensure minimum {min_pairs} pairs", level="WARNING")

    return filtered_pairs
