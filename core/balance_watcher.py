from common.config_loader import trade_stats, trade_stats_lock

from core.notifier import notify_deposit, notify_low_balance, notify_milestone, notify_withdrawal
from utils_logging import log


def check_balance_change(current_balance, last_balance):
    """
    Enhanced balance change detection with small deposit optimizations.
    """
    if last_balance == 0:
        with trade_stats_lock:
            trade_stats["initial_balance"] = current_balance
            # Track start date for ROI calculations
            from datetime import datetime

            trade_stats["start_date"] = datetime.now().isoformat()
        log(f"Initial balance set: {current_balance} USDC", level="INFO")
        return current_balance

    # Calculate both absolute and percentage changes
    delta = round(current_balance - last_balance, 2)
    delta_pct = (delta / last_balance * 100) if last_balance > 0 else 0

    # Adaptive threshold based on account size - smaller accounts get smaller thresholds
    threshold = 0.5 if last_balance >= 100 else 0.25
    threshold_pct = 0.5  # 0.5% threshold

    # Detect changes based on either absolute or percentage threshold
    if abs(delta) < threshold and abs(delta_pct) < threshold_pct:
        # Small balance check - alert if balance falls below critical thresholds
        if current_balance < 50 and last_balance >= 50:
            log(f"⚠️ CRITICAL: Balance below 50 USDC ({current_balance:.2f} USDC)", level="WARNING")
            notify_low_balance(current_balance, 50)
        elif current_balance < 100 and last_balance >= 100:
            log(f"⚠️ Warning: Balance below 100 USDC ({current_balance:.2f} USDC)", level="WARNING")
            notify_low_balance(current_balance, 100)

        return current_balance

    if delta > 0:
        with trade_stats_lock:
            trade_stats["deposits_today"] += delta
            trade_stats["deposits_week"] += delta
        notify_deposit(delta)
    elif delta < 0:
        with trade_stats_lock:
            trade_stats["withdrawals"] += abs(delta)
        notify_withdrawal(abs(delta))

    # Calculate and track account growth
    with trade_stats_lock:
        initial = trade_stats.get("initial_balance", last_balance)
        if initial > 0:
            growth_pct = (current_balance / initial - 1) * 100
            trade_stats["growth_pct"] = round(growth_pct, 2)

            # Check growth milestones
            milestone_reached = False
            for milestone in [120, 300, 500, 1000]:  # Updated milestones to match new tier structure
                if current_balance >= milestone and last_balance < milestone:
                    milestone_reached = True
                    notify_milestone(milestone, growth_pct)

            if growth_pct >= 100 and trade_stats.get("growth_pct", 0) < 100:
                notify_milestone("2x", growth_pct)
                milestone_reached = True

            if milestone_reached:
                log(f"🎉 Account growth: {growth_pct:.2f}% from initial {initial:.2f} USDC", level="INFO")

    return current_balance
