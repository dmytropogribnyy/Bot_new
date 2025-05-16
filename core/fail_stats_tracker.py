# core/fail_stats_tracker.py
import json
import os
from datetime import datetime, timedelta
from threading import Lock

from constants import FAIL_STATS_FILE
from stats import now_with_timezone
from utils_core import get_runtime_config, update_runtime_config
from utils_logging import log

fail_stats_lock = Lock()

# Configuration constants
MAX_FAILURES_THRESHOLD = get_runtime_config().get("FAILURE_BLOCK_THRESHOLD", 15)

BLOCK_DURATION_HOURS = 6  # Initial blocking duration
MAX_BLOCK_DURATION_HOURS = 12  # Maximum blocking duration for repeat offenders

# NEW: Temporal decay configuration
FAILURE_DECAY_HOURS = 3  # Failures decay every 3 hours
FAILURE_DECAY_AMOUNT = 1  # Reduce by 1 per period
SHORT_BLOCK_DURATION = 2  # Short blocking for 2 hours


def record_failure_reason(symbol, reasons):
    """
    Increment counters for failure reasons by symbol and check for auto-blocking.

    Args:
        symbol (str): Trading pair symbol
        reasons (list): List of failure reasons (strings)
    """
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

            # Calculate total failures for the symbol
            total_failures = sum(data[symbol].values())

            # Check if symbol should be auto-blocked
            if total_failures >= MAX_FAILURES_THRESHOLD:
                _check_and_apply_autoblock(symbol, total_failures)

            with open(FAIL_STATS_FILE, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            log(f"[FailStats] Error recording failure for {symbol}: {e}", level="ERROR")


def schedule_failure_decay(scheduler=None):
    """
    NEW FUNCTION: Schedule periodic failure decay
    Call this from main.py to enable automatic decay

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


def apply_failure_decay():
    """
    Apply temporal decay to failure counters
    NEW FUNCTION: Reduces failure counts over time
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
                            new_count = max(0, current_count - (FAILURE_DECAY_AMOUNT * decay_cycles))
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

                log("Applied failure decay to statistics", level="DEBUG")

        except Exception as e:
            log(f"Error applying failure decay: {e}", level="ERROR")


def _check_and_apply_autoblock(symbol, total_failures):
    """
    Check if a symbol should be auto-blocked based on failure count.
    MODIFIED: Uses progressive blocking with shorter initial periods

    Args:
        symbol (str): Trading pair symbol
        total_failures (int): Total number of failures for the symbol
    """
    runtime_config = get_runtime_config()
    blocked_symbols = runtime_config.get("blocked_symbols", {})

    # Progressive blocking: start with short periods
    previous_blocks = blocked_symbols.get(symbol, {}).get("block_count", 0)

    if total_failures < 30:
        block_duration = SHORT_BLOCK_DURATION  # 2 hours for first blocks
    elif total_failures < 50:
        block_duration = 4  # 4 hours for medium violations
    else:
        block_duration = min(6 + previous_blocks * 2, 12)  # From 6 to 12 hours

    # Apply blocking using proper timezone
    now = now_with_timezone()
    block_until = (now + timedelta(hours=block_duration)).isoformat()

    blocked_symbols[symbol] = {"block_until": block_until, "block_count": previous_blocks + 1, "total_failures": total_failures, "blocked_at": now.isoformat()}

    # Update runtime configuration
    runtime_config["blocked_symbols"] = blocked_symbols
    update_runtime_config(runtime_config)

    log(f"[AutoBlock] {symbol} blocked for {block_duration}h (failures: {total_failures})", level="WARNING")

    # Send notification
    from telegram.telegram_utils import send_telegram_message

    send_telegram_message(f"⚫️ Auto-blocked {symbol} for {block_duration} hours\n" f"Failures: {total_failures}, Block #: {previous_blocks + 1}", force=True)


def is_symbol_blocked(symbol):
    """
    Check if a symbol is currently blocked.

    Args:
        symbol (str): Trading pair symbol

    Returns:
        tuple: (is_blocked: bool, block_info: dict or None)
    """
    runtime_config = get_runtime_config()
    blocked_symbols = runtime_config.get("blocked_symbols", {})

    if symbol not in blocked_symbols:
        return False, None

    block_info = blocked_symbols[symbol]

    try:
        # Parse the block_until timestamp
        from dateutil import parser

        block_until = parser.parse(block_info["block_until"])

        # Make timezone-aware comparison
        now = now_with_timezone()

        if now < block_until:
            return True, block_info
        else:
            # Block expired, remove from blocked list
            _remove_block(symbol)
            return False, None
    except Exception as e:
        log(f"[AutoBlock] Error parsing block time for {symbol}: {e}", level="ERROR")
        # On error, consider block expired to avoid permanent blocking
        _remove_block(symbol)
        return False, None


def _remove_block(symbol):
    """Remove expired block for a symbol."""
    runtime_config = get_runtime_config()
    blocked_symbols = runtime_config.get("blocked_symbols", {})

    if symbol in blocked_symbols:
        del blocked_symbols[symbol]
        runtime_config["blocked_symbols"] = blocked_symbols
        update_runtime_config(runtime_config)
        log(f"[AutoBlock] Block expired for {symbol}", level="INFO")


def reset_failure_count(symbol):
    """
    Reset failure count for a symbol after successful trading.

    Args:
        symbol (str): Trading pair symbol
    """
    with fail_stats_lock:
        try:
            if os.path.exists(FAIL_STATS_FILE):
                with open(FAIL_STATS_FILE, "r") as f:
                    data = json.load(f)

                if symbol in data:
                    data[symbol] = {}
                    with open(FAIL_STATS_FILE, "w") as f:
                        json.dump(data, f, indent=2)
                    log(f"[FailStats] Reset failure count for {symbol}", level="INFO")
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
