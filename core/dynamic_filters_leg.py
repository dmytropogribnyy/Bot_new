# core/dynamic_filters.py
"""
Dynamic pair filtering system for BinanceBot
Implements adaptive filter thresholds based on market conditions and account size
Optimized for small USDC deposits and scalping strategies
"""

from filter_adaptation_leg import get_adaptive_relax_factor

from utils_core import get_runtime_config
from utils_logging import log


def get_dynamic_filter_thresholds(symbol, market_regime=None):
    """
    Get dynamic thresholds from runtime config, adjusted by relax_factor.
    Clean version optimized for full external control via runtime_config.json.
    """
    runtime_config = get_runtime_config()

    base_atr_percent = runtime_config.get("atr_threshold_percent", 2.0) / 100
    base_volume_usdc = runtime_config.get("volume_threshold_usdc", 3000)
    relax = runtime_config.get("relax_factor", 0.3)

    adjusted_atr = base_atr_percent * (1 - relax)
    adjusted_vol = base_volume_usdc * (1 - relax)

    log(f"{symbol} Final filter thresholds: ATR%={adjusted_atr*100:.2f}%, Volume={adjusted_vol:,.0f} USDC", level="INFO")

    return {"min_atr_percent": adjusted_atr, "min_volume_usdc": adjusted_vol}


def should_filter_pair(symbol, atr_percent, volume_usdc, market_regime=None, thresholds=None):
    """
    Determine if a pair should be filtered out based on dynamic thresholds,
    relax factors and market volatility adjustment.
    """
    from utils_core import get_market_volatility_index

    # 🧠 Если thresholds не переданы — взять дефолт из runtime_config
    if thresholds is None:
        runtime_config = get_runtime_config()
        thresholds = {
            "min_atr_percent": runtime_config.get("atr_threshold_percent", 1.5) / 100,
            "min_volume_usdc": runtime_config.get("volume_threshold_usdc", 2000),
        }

    relax = get_adaptive_relax_factor(symbol)
    volatility_index = get_market_volatility_index()

    # 🔁 Корректировка порогов в зависимости от волатильности рынка
    if volatility_index < 0.6:
        volatility_softener = 0.8
    elif volatility_index > 1.5:
        volatility_softener = 1.2
    else:
        volatility_softener = 1.0

    # 🎛️ Применение коэффициентов смягчения
    adjusted_atr = thresholds["min_atr_percent"] * (1 - relax) * volatility_softener
    adjusted_vol = thresholds["min_volume_usdc"] * (1 - relax) * volatility_softener

    # 🔒 Минимальные границы
    adjusted_atr = max(adjusted_atr, 0.003)  # 0.3%
    adjusted_vol = max(adjusted_vol, 500)  # 500 USDC

    log(f"{symbol} [Thresholds] ATR={atr_percent:.4f} vs {adjusted_atr:.4f}, Volume={volume_usdc:,.0f} vs {adjusted_vol:,.0f}", level="DEBUG")

    if atr_percent < adjusted_atr:
        log(f"[Filter] {symbol} ⛔️ Low ATR: {atr_percent:.4f} < {adjusted_atr:.4f}", level="DEBUG")
        return True, {"reason": "low_volatility", "current": atr_percent, "threshold": adjusted_atr}

    if volume_usdc < adjusted_vol:
        log(f"[Filter] {symbol} ⛔️ Low Volume: {volume_usdc:.0f} < {adjusted_vol:,.0f}", level="DEBUG")
        return True, {"reason": "low_volume", "current": volume_usdc, "threshold": adjusted_vol}

    return False, {"reason": "passed"}


def get_market_regime_from_indicators(adx, bb_width, recent_candles=None):
    """
    Determine market regime based on technical indicators
    Enhanced for scalping with more sensitive breakout detection

    Args:
        adx (float): Average Directional Index value
        bb_width (float): Bollinger Bands width relative to price
        recent_candles (list, optional): Recent price candles for additional analysis

    Returns:
        str: Market regime (breakout, trend, flat, neutral)
    """
    # NEW: More sensitive breakout detection for scalping
    # Lower ADX threshold and BB width for earlier breakout detection
    if adx > 22 and bb_width > 0.04:  # Reduced from 25 and 0.05
        return "breakout"

    # Strong trend - slightly lower threshold
    elif adx > 18:  # Reduced from 20
        return "trend"

    # Flat market - adjusted for scalping
    elif adx < 15:
        return "flat"

    # Neutral/normal market
    else:
        return "neutral"


def apply_filter_to_pairs(pairs, market_data, min_pairs=5):
    """
    Apply dynamic filters to a list of pairs
    Enhanced with better fallback selection for small accounts

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
        adx = pair_data.get("adx", 20)  # Default ADX
        bb_width = pair_data.get("bb_width", 0.03)  # Default BB width

        # Determine market regime
        market_regime = get_market_regime_from_indicators(adx, bb_width)

        # Apply filter
        should_filter, reason = should_filter_pair(symbol, atr_percent, volume_usdc, market_regime)

        if not should_filter:
            filtered_pairs.append(symbol)
        else:
            rejected_pairs.append({"symbol": symbol, "reason": reason, "score": _calculate_fallback_score(pair_data, reason)})

    # Enhanced fallback mechanism
    if len(filtered_pairs) < min_pairs and rejected_pairs:
        # Sort rejected pairs by how close they are to passing
        rejected_pairs.sort(key=lambda x: x["score"], reverse=True)

        # Add best rejected pairs until we reach minimum
        while len(filtered_pairs) < min_pairs and rejected_pairs:
            pair_to_add = rejected_pairs.pop(0)
            filtered_pairs.append(pair_to_add["symbol"])
            log(f"Added {pair_to_add['symbol']} to ensure minimum {min_pairs} pairs (score: {pair_to_add['score']:.3f})", level="WARNING")

    return filtered_pairs


def _calculate_fallback_score(pair_data, rejection_reason):
    """
    Calculate a score for rejected pairs to determine fallback priority
    Higher score means closer to passing filters

    Args:
        pair_data (dict): Market data for the pair
        rejection_reason (dict): Reason for rejection with current/threshold values

    Returns:
        float: Fallback score (0-1, higher is better)
    """
    if "current" in rejection_reason and "threshold" in rejection_reason:
        current = rejection_reason["current"]
        threshold = rejection_reason["threshold"]

        # Calculate how close the value is to threshold (0-1 scale)
        if threshold > 0:
            ratio = current / threshold
            # Cap at 1 and give exponential weight to values close to threshold
            return min(1.0, ratio**2)

    # Default score for other rejection types
    return 0.1
