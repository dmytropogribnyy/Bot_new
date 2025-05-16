# risk_utils.py
"""
Risk management utilities for BinanceBot
Implements adaptive risk allocation, position limits, and drawdown protection
"""

from datetime import datetime

from core.exchange_init import exchange
from telegram.telegram_utils import send_telegram_message
from utils_logging import log


def get_adaptive_risk_percent(balance, atr_percent=None, volume_usdc=None, win_streak=0, score=0):
    """
    Optimized risk allocation with progressive caps based on performance

    Args:
        balance (float): Current account balance
        atr_percent (float, optional): ATR percentage of the trading pair
        volume_usdc (float, optional): 24h volume in USDC
        win_streak (int, optional): Current consecutive winning trades
        score (float, optional): Signal quality score

    Returns:
        float: Risk percentage (0.02-0.038) based on inputs
    """
    # Base risk - conservative foundation
    if balance < 100:
        base_risk = 0.020  # 2.0% base for very small accounts
    elif balance < 150:
        base_risk = 0.023  # 2.3% base for small accounts
    else:
        base_risk = 0.028  # 2.8% base for larger accounts

    # Quality bonuses for exceptional opportunities
    asset_quality_bonus = 0.0
    if atr_percent is not None:
        if atr_percent > 0.4:
            asset_quality_bonus += 0.008  # +0.8% for high volatility
        elif atr_percent > 0.3:
            asset_quality_bonus += 0.005  # +0.5% for good volatility

    if volume_usdc is not None:
        if volume_usdc > 100000:
            asset_quality_bonus += 0.006  # +0.6% for high liquidity
        elif volume_usdc > 50000:
            asset_quality_bonus += 0.004  # +0.4% for good liquidity

    # Win streak bonus - confidence builder
    win_streak_bonus = min(win_streak * 0.002, 0.006)  # Up to +0.6% for streak

    # Signal quality bonus
    signal_bonus = 0.0
    if score > 4.0:
        signal_bonus = 0.006  # +0.6% for exceptional signals
    elif score > 3.5:
        signal_bonus = 0.003  # +0.3% for strong signals

    # Get current performance stats
    try:
        from stats import get_performance_stats

        stats = get_performance_stats()

        # Progressive risk cap based on proven performance
        if stats["win_rate"] >= 0.75 and stats["profit_factor"] >= 2.0:
            max_risk = 0.038  # 3.8% cap for excellent performance
        elif stats["win_rate"] >= 0.70 and stats["profit_factor"] >= 1.8:
            max_risk = 0.035  # 3.5% cap for very good performance
        else:
            max_risk = 0.030  # 3.0% cap otherwise
    except Exception as e:
        # Fallback if stats not available
        log(f"Unable to get performance stats for risk calculation: {e}", level="DEBUG")
        max_risk = 0.030  # Default conservative cap

    # Calculate final risk with all factors
    final_risk = min(base_risk + asset_quality_bonus + win_streak_bonus + signal_bonus, max_risk)

    log(
        f"Adaptive risk calculation: base={base_risk:.3f}, asset={asset_quality_bonus:.3f}, " f"streak={win_streak_bonus:.3f}, signal={signal_bonus:.3f}, final={final_risk:.3f}",
        level="DEBUG",
    )

    return final_risk


def get_max_positions(balance):
    """
    Return maximum allowed simultaneous positions based on account size

    Args:
        balance (float): Current account balance

    Returns:
        int: Maximum number of positions
    """
    if balance < 100:
        return 2  # Limit to 2 positions for ultra-small accounts
    elif balance < 150:
        return 2  # Limit to 2 positions for small accounts (stricter than before)
    elif balance < 300:
        return 3  # Limited to 3 for medium accounts (reduced from 4)
    else:
        return 4  # Limited to 4 for larger accounts (reduced from 5)


def get_max_risk():
    """
    Get the current maximum risk value from stored settings

    Returns:
        float: Maximum risk value (default 0.03)
    """
    try:
        import json
        import os

        if not os.path.exists("data/risk_settings.json"):
            return 0.03  # Default 3% if file doesn't exist

        with open("data/risk_settings.json", "r") as f:
            data = json.load(f)
            return data.get("max_risk", 0.03)  # Default 3% if key not found
    except Exception as e:
        log(f"Error reading max risk: {e}", level="ERROR")
        return 0.03  # Default 3% if there's an error


def check_capital_utilization(balance: float, new_position_value: float = 0) -> bool:
    """
    Ensure total capital utilization stays under 70%, including active positions and open limit orders.
    """
    try:
        # 1. Calculate exposure from open positions
        positions = exchange.fetch_positions()
        current_exposure = sum(abs(float(pos.get("contracts", 0)) * float(pos.get("entryPrice", 0))) for pos in positions if pos.get("contracts") and pos.get("entryPrice"))

        # 2. Add exposure from open limit orders
        open_orders = exchange.fetch_open_orders()
        orders_exposure = sum(float(order.get("amount", 0)) * float(order.get("price", 0)) for order in open_orders if order.get("type") == "limit")

        # 3. Combine all exposures
        total_exposure = current_exposure + orders_exposure + new_position_value
        max_allowed = balance * 0.7

        if total_exposure > max_allowed:
            log(f"[Risk] Capital utilization too high: {total_exposure:.2f} > {max_allowed:.2f} (limit = 70%)", level="WARNING")
            return False
        return True
    except Exception as e:
        log(f"[Risk] Error checking capital utilization: {e}", level="ERROR")
        return True  # Fail-safe: allow trade if can't check


def set_max_risk(risk):
    """
    Set the current maximum risk value

    Args:
        risk (float): Risk value between 0.01 and 0.05

    Returns:
        bool: Success status
    """
    try:
        import json
        import os
        from datetime import datetime

        # Ensure risk is capped between 1% and 5%
        risk = max(0.01, min(0.05, risk))

        # Create directory if it doesn't exist
        os.makedirs("data", exist_ok=True)

        # Write to risk settings file
        with open("data/risk_settings.json", "w") as f:
            json.dump({"max_risk": risk, "updated_at": datetime.now().isoformat()}, f)

        log(f"Maximum risk updated to {risk*100:.1f}%", level="INFO")
        return True
    except Exception as e:
        log(f"Error setting max risk: {e}", level="ERROR")
        return False


def get_initial_balance():
    """
    Get the initial account balance for drawdown calculations

    Returns:
        float: Initial account balance
    """
    try:
        import json
        import os

        if not os.path.exists("data/initial_balance.json"):
            # If file doesn't exist, create it with current balance
            from utils_core import get_cached_balance

            current_balance = get_cached_balance() or 100

            os.makedirs("data", exist_ok=True)
            with open("data/initial_balance.json", "w") as f:
                json.dump({"initial_balance": current_balance, "set_at": datetime.now().isoformat()}, f)

            return current_balance

        # Read existing initial balance
        with open("data/initial_balance.json", "r") as f:
            data = json.load(f)
            return data.get("initial_balance", 0)
    except Exception as e:
        log(f"Error getting initial balance: {e}", level="ERROR")
        # Fallback to current balance
        try:
            from utils_core import get_cached_balance

            return get_cached_balance() or 100
        except Exception:
            return 100  # Absolute fallback value


def check_drawdown_protection(balance):
    """
    Implements automated risk reduction on significant drawdowns

    Args:
        balance (float): Current account balance

    Returns:
        dict: Status information including protection actions taken
    """
    initial_balance = get_initial_balance()
    if initial_balance == 0:
        log("Cannot calculate drawdown: initial balance is 0", level="WARNING")
        return {"status": "normal"}

    drawdown_percent = ((initial_balance - balance) / initial_balance) * 100

    # Log current drawdown state
    log(f"Current drawdown: {drawdown_percent:.2f}% (Balance: {balance:.2f}, Initial: {initial_balance:.2f})", level="DEBUG")

    if drawdown_percent >= 15:
        # Critical drawdown - pause bot operations
        from common.config_loader import set_bot_status

        set_bot_status("paused")

        message = f"⚠️ CRITICAL: {drawdown_percent:.1f}% drawdown detected. Bot paused for protection."
        log(message, level="ERROR")
        send_telegram_message(message, force=True)

        return {"status": "paused", "drawdown": drawdown_percent, "initial_balance": initial_balance, "current_balance": balance}
    elif drawdown_percent >= 8:
        # Significant drawdown - reduce risk
        current_max_risk = get_max_risk()
        new_max_risk = current_max_risk * 0.75  # Reduce by 25%
        set_max_risk(new_max_risk)

        message = f"⚠️ WARNING: {drawdown_percent:.1f}% drawdown detected. Risk reduced to {new_max_risk*100:.1f}%."
        log(message, level="WARNING")
        send_telegram_message(message, force=True)

        return {"status": "reduced_risk", "drawdown": drawdown_percent, "new_risk": new_max_risk, "initial_balance": initial_balance, "current_balance": balance}

    return {"status": "normal", "drawdown": drawdown_percent}


def calculate_position_value_limit(balance):
    """
    Calculate maximum allowed position value based on account balance

    Args:
        balance (float): Current account balance

    Returns:
        float: Maximum position value in USDC
    """
    if balance < 100:
        # Very conservative for ultra-small accounts
        return balance * 0.35  # Maximum 35% of balance per position
    elif balance < 150:
        # Conservative for small accounts
        return balance * 0.40  # Maximum 40% of balance per position
    elif balance < 300:
        # Moderate for medium accounts
        return balance * 0.45  # Maximum 45% of balance per position
    else:
        # Standard for larger accounts
        return balance * 0.50  # Maximum 50% of balance per position


def get_max_total_exposure(balance):
    """
    Calculate maximum total exposure across all positions

    Args:
        balance (float): Current account balance

    Returns:
        float: Maximum total exposure in USDC
    """
    if balance < 150:
        # Very conservative for small accounts
        return balance * 0.70  # Maximum 70% total exposure
    elif balance < 300:
        # Moderate for medium accounts
        return balance * 0.80  # Maximum 80% total exposure
    else:
        # Standard for larger accounts
        return balance * 0.90  # Maximum 90% total exposure
