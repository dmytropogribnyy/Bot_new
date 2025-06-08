# core/fail_stats_tracker.py
import json
import os
from datetime import datetime
from threading import Lock

from constants import FAIL_STATS_FILE
from utils_core import extract_symbol, get_runtime_config, update_runtime_config
from utils_logging import log

fail_stats_lock = Lock()

# Configuration constants
MAX_FAILURES_THRESHOLD = 30  # For warnings only, not blocking

# Temporal decay configuration
FAILURE_DECAY_HOURS = 3  # Failures decay every 3 hours
FAILURE_DECAY_AMOUNT = 1  # Reduce by 1 per period


def record_failure_reason(symbol, reasons):
    """
    Increment counters for failure reasons by symbol.
    No longer triggers any blocking mechanism.

    Args:
        symbol (str): Trading pair symbol
        reasons (list): List of failure reasons (strings)
    """
    symbol = extract_symbol(symbol)

    if not reasons:
        return

    with fail_stats_lock:
        try:
            if os.path.exists(FAIL_STATS_FILE):
                with open(FAIL_STATS_FILE, "r") as f:
                    data = json.load(f)
            else:
                data = {}

            if symbol not in data:
                data[symbol] = {}

            for reason in reasons:
                data[symbol][reason] = data[symbol].get(reason, 0) + 1

            # Calculate total failures for logging purposes
            total_failures = sum(data[symbol].values())

            # Log high failure counts but do not block
            if total_failures >= MAX_FAILURES_THRESHOLD:
                log(f"[HighRisk] {symbol} has {total_failures} failures - trading with reduced risk", level="WARNING")

                # Optional notification for very high risk
                if total_failures % 10 == 0:  # Send every 10 failures to avoid spam
                    from telegram.telegram_utils import send_telegram_message

                    risk_factor, _ = get_symbol_risk_factor(symbol)
                    send_telegram_message(
                        f"⚠️ {symbol} marked high risk (risk_factor={risk_factor:.2f}, failures: {total_failures})\n" f"Position size will be reduced accordingly.", force=True
                    )

            with open(FAIL_STATS_FILE, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            log(f"[FailStats] Error recording failure for {symbol}: {e}", level="ERROR")


def schedule_failure_decay(scheduler=None):
    """
    Schedule periodic failure decay.
    Call this from main.py to enable automatic decay.

    Args:
        scheduler: APScheduler instance (optional)
    """
    if scheduler:
        scheduler.add_job(
            apply_failure_decay,
            "interval",
            hours=1,  # Check every hour
            id="failure_decay",
            replace_existing=True,
        )
        log("Scheduled failure decay job", level="INFO")
    else:
        # Run directly
        apply_failure_decay()


def apply_failure_decay(accelerated=False):
    """
    Apply temporal decay to failure counters.
    Reduces failure counts over time for recovery.

    Args:
        accelerated (bool): Apply stronger decay for faster recovery
    """
    with fail_stats_lock:
        try:
            if not os.path.exists(FAIL_STATS_FILE):
                return

            with open(FAIL_STATS_FILE, "r") as f:
                data = json.load(f)

            # Load decay timestamps
            decay_timestamps_file = "data/failure_decay_timestamps.json"
            if os.path.exists(decay_timestamps_file):
                with open(decay_timestamps_file, "r") as f:
                    timestamps = json.load(f)
            else:
                timestamps = {}

            current_time = datetime.now()
            updated = False

            # Enhanced decay amount for accelerated recovery
            decay_amount = FAILURE_DECAY_AMOUNT * 3 if accelerated else FAILURE_DECAY_AMOUNT

            # Log accelerated decay if active
            if accelerated:
                log(f"Applying accelerated decay ({decay_amount}x) to all symbols", level="INFO")

            for symbol in data:
                last_decay = timestamps.get(symbol)
                if last_decay:
                    last_decay_time = datetime.fromisoformat(last_decay)
                    hours_passed = (current_time - last_decay_time).total_seconds() / 3600

                    if hours_passed >= FAILURE_DECAY_HOURS:
                        # Apply decay
                        decay_cycles = int(hours_passed / FAILURE_DECAY_HOURS)

                        for reason in data[symbol]:
                            current_count = data[symbol][reason]
                            new_count = max(0, current_count - (decay_amount * decay_cycles))
                            data[symbol][reason] = new_count

                        timestamps[symbol] = current_time.isoformat()
                        updated = True
                else:
                    # First time record
                    timestamps[symbol] = current_time.isoformat()
                    updated = True

            if updated:
                # Save updated data
                with open(FAIL_STATS_FILE, "w") as f:
                    json.dump(data, f, indent=2)

                with open(decay_timestamps_file, "w") as f:
                    json.dump(timestamps, f, indent=2)

                # Calculate statistics for logging
                reduced_symbols = sum(1 for s in data if any(data[s].values()))
                zero_symbols = sum(1 for s in data if not any(data[s].values()))

                log(f"Applied failure decay to {reduced_symbols} symbols, {zero_symbols} reset to zero", level="INFO" if accelerated else "DEBUG")

        except Exception as e:
            log(f"Error applying failure decay: {e}", level="ERROR")


def get_symbol_risk_factor(symbol):
    """
    Calculate risk factor based on failure count.
    Returns a value between 0.1–1.0 with 1.0 being full risk.

    Returns:
        tuple: (risk_factor: float 0.0–1.0, info: dict or None)
        - 1.0 means full position size (no risk reduction)
        - 0.0–0.25 means high risk reduction
    """
    symbol = extract_symbol(symbol)

    try:
        # Get total failures for the symbol
        stats = get_signal_failure_stats()
        if symbol not in stats:
            return 1.0, None  # No failures = full risk

        total_failures = sum(stats[symbol].values())

        # Progressive risk factor calculation
        if total_failures <= 5:
            risk_factor = 1.0
        elif total_failures <= 15:
            risk_factor = max(0.7, 1.0 - (total_failures - 5) / 30)
        elif total_failures <= 30:
            risk_factor = max(0.4, 0.7 - (total_failures - 15) / 50)
        else:
            risk_factor = max(0.1, 0.4 - (total_failures - 30) / 100)

        info = {"total_failures": total_failures}
        return risk_factor, info

    except Exception as e:
        log(f"Error calculating risk factor for {symbol}: {e}", level="ERROR")
        return 0.5, None  # Conservative fallback


def reset_failure_count(symbol):
    """
    Reset failure count for a symbol after successful trading.
    Also useful for manual intervention.

    Args:
        symbol (str): Trading pair symbol
    """
    symbol = extract_symbol(symbol)

    with fail_stats_lock:
        try:
            if os.path.exists(FAIL_STATS_FILE):
                with open(FAIL_STATS_FILE, "r") as f:
                    data = json.load(f)

                if symbol in data:
                    old_failures = sum(data[symbol].values()) if symbol in data else 0
                    data[symbol] = {}
                    with open(FAIL_STATS_FILE, "w") as f:
                        json.dump(data, f, indent=2)

                    log(f"[FailStats] Reset failure count for {symbol} (was: {old_failures})", level="INFO")

                    # Notify for significant resets
                    if old_failures > 20:
                        from telegram.telegram_utils import send_telegram_message

                        send_telegram_message(f"✅ {symbol} risk reset after successful trading (cleared {old_failures} failures)", force=True)
        except Exception as e:
            log(f"[FailStats] Error resetting failures for {symbol}: {e}", level="ERROR")


def get_signal_failure_stats():
    """
    Retrieve aggregated statistics about signal failures from the tracking data.

    Returns:
        dict: Dictionary with aggregated failure statistics by symbol and reason
    """
    with fail_stats_lock:
        try:
            if os.path.exists(FAIL_STATS_FILE):
                with open(FAIL_STATS_FILE, "r") as f:
                    data = json.load(f)
                return data
            else:
                return {}
        except Exception as e:
            log(f"[FailStats] Error retrieving failure stats: {e}", level="ERROR")
            return {}


def get_symbols_failure_count():
    """
    Get total failure count for each symbol.

    Returns:
        dict: Dictionary mapping symbols to their total failure counts
    """
    with fail_stats_lock:
        try:
            if os.path.exists(FAIL_STATS_FILE):
                with open(FAIL_STATS_FILE, "r") as f:
                    data = json.load(f)

                # Create a dictionary of symbol -> total failures
                symbol_failures = {}
                for symbol, reasons in data.items():
                    symbol_failures[symbol] = sum(reasons.values())

                return symbol_failures
            else:
                return {}
        except Exception as e:
            log(f"[FailStats] Error retrieving symbol failure counts: {e}", level="ERROR")
            return {}


def get_high_risk_symbols(threshold=0.5):
    """
    Get a list of symbols with risk factor below threshold.

    Args:
        threshold (float): Risk factor threshold (0.0-1.0)

    Returns:
        list: List of symbol tuples (symbol, risk_factor)
    """
    try:
        stats = get_signal_failure_stats()
        high_risk = []

        for symbol in stats:
            risk_factor, _ = get_symbol_risk_factor(symbol)
            if risk_factor < threshold:
                high_risk.append((symbol, risk_factor))

        # Sort by risk factor (lowest first)
        high_risk.sort(key=lambda x: x[1])
        return high_risk

    except Exception as e:
        log(f"[FailStats] Error retrieving high risk symbols: {e}", level="ERROR")
        return []


def check_risk_distribution():
    """
    Analyze risk distribution across all symbols.
    Useful for health monitoring.

    Returns:
        dict: Statistics about risk distribution
    """
    try:
        all_symbols = get_signal_failure_stats().keys()
        total_symbols = len(all_symbols)

        if total_symbols == 0:
            return {"total": 0}

        risk_levels = {
            "critical": 0,  # risk < 0.25
            "high": 0,  # 0.25 <= risk < 0.5
            "medium": 0,  # 0.5 <= risk < 0.75
            "low": 0,  # risk >= 0.75
        }

        for symbol in all_symbols:
            symbol = extract_symbol(symbol)
            risk_factor, _ = get_symbol_risk_factor(symbol)

            if risk_factor < 0.25:
                risk_levels["critical"] += 1
            elif risk_factor < 0.5:
                risk_levels["high"] += 1
            elif risk_factor < 0.75:
                risk_levels["medium"] += 1
            else:
                risk_levels["low"] += 1

        result = {
            "total": total_symbols,
            "levels": risk_levels,
            "percentages": {level: count / total_symbols for level, count in risk_levels.items()},
        }

        return result

    except Exception as e:
        log(f"[FailStats] Error checking risk distribution: {e}", level="ERROR")
        return {"error": str(e)}


# Legacy compatibility function - always returns False
def is_symbol_blocked(symbol):
    """
    Legacy function maintained for backward compatibility.
    Always returns False as we've moved to graduated risk system.

    Returns:
        tuple: (False, None) Always indicates not blocked
    """
    log(f"[FailStats] Warning: is_symbol_blocked() called for {symbol} but we're using graduated risk now", level="DEBUG")
    return False, None


# Function to migrate from blocked_symbols to risk factor system
def migrate_from_blocked_symbols():
    """
    One-time migration function to clear blocked_symbols from runtime_config.
    Call this during startup to ensure clean transition to risk factor system.

    Returns:
        bool: True if migration occurred, False if nothing to migrate
    """
    try:
        runtime_config = get_runtime_config()
        if "blocked_symbols" in runtime_config and runtime_config["blocked_symbols"]:
            # Log the migration
            blocked_count = len(runtime_config["blocked_symbols"])
            log(f"Migrating {blocked_count} blocked symbols to risk factor system", level="INFO")

            # Clear blocked_symbols
            runtime_config["blocked_symbols"] = {}
            update_runtime_config(runtime_config)

            # Apply accelerated decay to speed recovery
            apply_failure_decay(accelerated=True)

            return True  # Migration occurred
        return False  # Nothing to migrate
    except Exception as e:
        log(f"Error during migration from blocked_symbols: {e}", level="ERROR")
        return False  # Error occurred
