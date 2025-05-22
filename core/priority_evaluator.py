import json
import os
from datetime import datetime

from core.fail_stats_tracker import get_symbols_failure_count
from core.tp_utils import get_tp_performance_stats
from symbol_activity_tracker import get_symbol_activity_data
from utils_logging import log

PRIORITY_JSON_PATH = "data/priority_pairs.json"
MIN_PRIORITY_PAIRS = 6  # Ensure we always have enough priority pairs


def get_priority_score(symbol, data):
    """
    Calculate priority score for a symbol based on multiple criteria.
    Enhanced version: stronger weight on activity and TP performance.
    """
    score = 0
    weights = {"price": 0.20, "volatility": 0.20, "activity": 0.25, "performance": 0.30, "stability": 0.05}

    # --- Price factor (cheap coins preferred)
    price = data.get("price", 999)
    if price < 0.5:
        price_score = 1.0
    elif price < 1.0:
        price_score = 0.8
    elif price < 5.0:
        price_score = 0.6
    elif price < 10.0:
        price_score = 0.4
    else:
        price_score = 0.2

    # --- Volatility factor
    atr_percent = data.get("atr_percent", 0)
    volatility_score = min(1.0, max(0.0, (atr_percent * 100) / 0.4))  # Normalize to 0–1 for 0–0.4 ATR%

    # --- Activity factor
    signal_count = data.get("signal_activity", 0)
    activity_score = min(1.0, signal_count / 5)  # 5+ signals in 24h = max score

    # --- Performance factor
    tp_winrate = data.get("tp_winrate", 0)
    tp2_winrate = data.get("tp2_winrate", 0)
    performance_score = 0.6 * tp_winrate + 0.4 * tp2_winrate  # More focus on TP1 winrate

    # --- Stability factor
    fail_count = data.get("fail_count", 0)
    stability_score = max(0.0, 1 - (fail_count / 20))  # Normalize to 0–1

    # --- Final weighted score
    score = (
        weights["price"] * price_score
        + weights["volatility"] * volatility_score
        + weights["activity"] * activity_score
        + weights["performance"] * performance_score
        + weights["stability"] * stability_score
    )

    return round(score, 3)


def gather_symbol_data():
    """
    Collect data for all symbols from various sources.

    Returns:
        dict: Symbol data with metrics for scoring
    """
    try:
        symbols_data = {}

        # Get price and volatility data
        import json

        from constants import SYMBOLS_FILE
        from core.binance_api import get_ticker_data

        # Load active symbols from dynamic_symbols.json
        try:
            with open(SYMBOLS_FILE, "r") as f:
                active_symbols = json.load(f)
        except Exception as e:
            log(f"Error loading symbols file: {e}", level="ERROR")
            # Fallback to default symbols if file can't be loaded
            from common.config_loader import USDC_SYMBOLS

            active_symbols = USDC_SYMBOLS

        # Initialize empty dictionary for ticker data
        ticker_data = {}

        # Fetch data for each symbol individually
        for symbol in active_symbols:
            try:
                ticker_data[symbol] = get_ticker_data(symbol)
            except Exception as e:
                log(f"Error fetching ticker data for {symbol}: {e}", level="DEBUG")

        # Get TP performance data
        tp_stats = get_tp_performance_stats()

        # Get failure counts
        failure_counts = get_symbols_failure_count()

        # Get signal activity data
        activity_data = get_symbol_activity_data()

        # For each symbol, gather comprehensive data
        for symbol in ticker_data:
            symbol_data = {
                "price": ticker_data[symbol].get("last", 999),
                "atr": ticker_data[symbol].get("atr", 0),
                "atr_percent": ticker_data[symbol].get("atr_percent", 0),
                "volume_usdc": ticker_data[symbol].get("volume_usdc", 0),
                "signal_activity": activity_data.get(symbol, {}).get("signal_count_24h", 0),
                "tp_winrate": tp_stats.get(symbol, {}).get("winrate", 0),
                "tp2_winrate": tp_stats.get(symbol, {}).get("tp2_winrate", 0),
                "fail_count": failure_counts.get(symbol, 0),
            }
            symbols_data[symbol] = symbol_data

        return symbols_data
    except Exception as e:
        log(f"[PriorityEval] Error gathering symbol data: {e}", level="ERROR")
        return {}


def generate_priority_pairs(threshold=0.65, ensure_minimum=True):
    """
    Generate list of priority pairs based on current market conditions.

    Args:
        threshold: Minimum score to qualify as priority pair
        ensure_minimum: Ensure at least MIN_PRIORITY_PAIRS are returned

    Returns:
        list: Priority trading pairs
    """
    try:
        # Gather data for all symbols
        symbols_data = gather_symbol_data()

        # Calculate scores and sort
        scored_symbols = []
        for symbol, data in symbols_data.items():
            score = get_priority_score(symbol, data)
            scored_symbols.append({"symbol": symbol, "score": score, "data": data})

        # Sort by score descending
        scored_symbols.sort(key=lambda x: x["score"], reverse=True)

        # Select symbols above threshold
        priority_pairs = [item["symbol"] for item in scored_symbols if item["score"] >= threshold]

        # Ensure minimum number of pairs if needed
        if ensure_minimum and len(priority_pairs) < MIN_PRIORITY_PAIRS:
            priority_pairs = [item["symbol"] for item in scored_symbols[:MIN_PRIORITY_PAIRS]]

        # Enhanced log with signal stats
        log_message = f"[PriorityEval] Generated {len(priority_pairs)} priority pairs:"
        for i, item in enumerate(scored_symbols[:10]):
            d = item["data"]
            log_message += (
                f"\n  {i+1}. {item['symbol']}: Score={item['score']:.3f}, "
                f"Signals={d.get('signal_activity', 0)}, "
                f"TP1={d.get('tp_winrate', 0):.2f}, TP2={d.get('tp2_winrate', 0):.2f}, "
                f"ATR%={d.get('atr_percent', 0):.3f}"
            )
        log(log_message, level="INFO")

        return priority_pairs

    except Exception as e:
        log(f"[PriorityEval] Error generating priority pairs: {e}", level="ERROR")

        # Fallback to default pairs from config - moved inside function to avoid circular import
        try:
            from common.config_loader import DEFAULT_PRIORITY_SMALL_BALANCE_PAIRS

            return DEFAULT_PRIORITY_SMALL_BALANCE_PAIRS
        except Exception as e2:
            log(f"[PriorityEval] Fallback import failed: {e2}", level="ERROR")
            try:
                from common.config_loader import PRIORITY_SMALL_BALANCE_PAIRS

                return PRIORITY_SMALL_BALANCE_PAIRS
            except Exception as e3:
                log(f"[PriorityEval] Secondary fallback failed: {e3}", level="ERROR")
                return ["XRP/USDC", "DOGE/USDC", "ADA/USDC", "SOL/USDC", "MATIC/USDC", "DOT/USDC"]


def save_priority_pairs(pairs):
    """Save priority pairs to JSON file with timestamp."""
    try:
        os.makedirs("data", exist_ok=True)
        data = {"updated_at": datetime.now().isoformat(), "pairs": pairs}
        with open(PRIORITY_JSON_PATH, "w") as f:
            json.dump(data, f, indent=2)
        log(f"[PriorityEval] Saved {len(pairs)} priority pairs to {PRIORITY_JSON_PATH}", level="INFO")
        return True
    except Exception as e:
        log(f"[PriorityEval] Error saving priority pairs: {e}", level="ERROR")
        return False


def load_priority_pairs():
    """Load priority pairs from JSON file with fallback to defaults."""
    try:
        if os.path.exists(PRIORITY_JSON_PATH):
            with open(PRIORITY_JSON_PATH, "r") as f:
                data = json.load(f)
            pairs = data.get("pairs", [])
            log(f"[PriorityEval] Loaded {len(pairs)} priority pairs from file", level="DEBUG")
            return pairs
        else:
            log("[PriorityEval] Priority pairs file not found, using defaults", level="DEBUG")
    except Exception as e:
        log(f"[PriorityEval] Error loading priority pairs: {e}", level="ERROR")

    # Fallback to default pairs from config
    try:
        from common.config_loader import DEFAULT_PRIORITY_SMALL_BALANCE_PAIRS

        return DEFAULT_PRIORITY_SMALL_BALANCE_PAIRS
    except Exception as e2:
        log(f"[PriorityEval] Fallback failed: {e2}", level="ERROR")
        return []


def regenerate_priority_pairs():
    """Regenerate and save priority pairs, callable from Telegram."""
    pairs = generate_priority_pairs()
    if pairs:
        save_priority_pairs(pairs)
        return f"✅ Generated {len(pairs)} priority pairs"
    else:
        return "❌ Failed to generate priority pairs"
