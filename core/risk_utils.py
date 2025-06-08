# risk_utils.py
from datetime import datetime

from common.config_loader import SYMBOLS_ACTIVE
from core.binance_api import fetch_open_orders
from core.exchange_init import exchange
from telegram.telegram_utils import send_telegram_message
from utils_logging import log

"""
Risk management utilities for BinanceBot
Implements adaptive risk allocation, position limits, and drawdown protection
"""


def get_adaptive_risk_percent(balance, atr_percent=None, volume_usdc=None, win_streak=0):
    """
    Adaptive risk allocation, reading max_risk from get_max_risk() and also
    applying runtime_config["risk_multiplier"] if present.

    Args:
        balance (float): Current account balance in USDC
        atr_percent (float, optional): ATR ratio (e.g. 0.35)
        volume_usdc (float, optional): 24h average volume in USDC
        win_streak (int, optional): Current consecutive winning trades

    Returns:
        float: Risk percentage in [0, max_risk], e.g. ~0.02..0.03
    """
    # 1) Базовый риск по размеру баланса
    if balance < 120:
        base_risk = 0.020  # 2.0% for micro tier
    elif balance < 300:
        base_risk = 0.023  # 2.3% for small tier
    else:
        base_risk = 0.028  # 2.8% for larger accounts

    # 2) asset_quality_bonus (по vol & ATR)
    asset_quality_bonus = 0.0
    if atr_percent is not None:
        if atr_percent > 0.4:
            asset_quality_bonus += 0.008
        elif atr_percent > 0.3:
            asset_quality_bonus += 0.005

    if volume_usdc is not None:
        if volume_usdc > 100000:
            asset_quality_bonus += 0.006
        elif volume_usdc > 50000:
            asset_quality_bonus += 0.004

    # 3) Win streak bonus
    win_streak_bonus = min(win_streak * 0.002, 0.006)  # up to +0.6%

    # 4) Кап из risk_settings.json
    max_risk = get_max_risk()  # вместо жёсткого 0.03

    # 5) Складываем всё вместе
    raw_risk = base_risk + asset_quality_bonus + win_streak_bonus
    final_risk = min(raw_risk, max_risk)

    # 6) Учитываем runtime_config["risk_multiplier"]
    from utils_core import get_runtime_config

    config = get_runtime_config()
    risk_mult = config.get("risk_multiplier", 1.0)

    final_risk *= risk_mult

    # 7) Логируем всё детально
    log(
        f"[AdaptiveRisk] balance={balance:.1f} | base={base_risk:.3f} "
        f"asset_bonus={asset_quality_bonus:.3f} streak_bonus={win_streak_bonus:.3f} "
        f"raw_risk={raw_risk:.3f} max_risk={max_risk:.3f} mult={risk_mult:.2f} "
        f"=> final_risk={final_risk:.3f}",
        level="DEBUG",
    )

    return final_risk


def get_max_positions(balance):
    """
    Return maximum allowed simultaneous positions based on account size
    """
    if balance < 120:
        return 2  # Micro tier
    elif balance < 300:
        return 3  # Small tier
    else:
        return 4  # Standard tier


def get_max_risk():
    """
    Get the current maximum risk value from local settings file or default 0.03
    """
    try:
        import json
        import os

        if not os.path.exists("data/risk_settings.json"):
            return 0.03

        with open("data/risk_settings.json", "r") as f:
            data = json.load(f)
            return data.get("max_risk", 0.03)
    except Exception as e:
        log(f"Error reading max risk: {e}", level="ERROR")
        return 0.03


def check_capital_utilization(balance, new_notional, threshold=0.8):
    if balance <= 0:
        return True

    total_open_notional = 0

    for symbol in SYMBOLS_ACTIVE:
        try:
            orders = fetch_open_orders(symbol)
            for order in orders:
                price = float(order.get("price", 0))
                amount = float(order.get("amount", 0))
                total_open_notional += price * amount
        except Exception:
            continue

    total_after_trade = total_open_notional + new_notional
    utilization = total_after_trade / balance

    return utilization <= threshold


def set_max_risk(risk):
    """
    Set the current maximum risk value in [0.01..0.05]
    """
    try:
        import json
        import os
        from datetime import datetime

        risk = max(0.01, min(0.05, risk))
        os.makedirs("data", exist_ok=True)

        with open("data/risk_settings.json", "w") as f:
            json.dump({"max_risk": risk, "updated_at": datetime.now().isoformat()}, f)

        log(f"Maximum risk updated to {risk*100:.1f}%", level="INFO")
        return True
    except Exception as e:
        log(f"Error setting max risk: {e}", level="ERROR")
        return False


def get_initial_balance():
    """
    Get initial account balance from local file or fallback to current.
    """
    try:
        import json
        import os

        if not os.path.exists("data/initial_balance.json"):
            from utils_core import get_cached_balance

            current_balance = get_cached_balance() or 100
            os.makedirs("data", exist_ok=True)
            with open("data/initial_balance.json", "w") as f:
                json.dump({"initial_balance": current_balance, "set_at": datetime.now().isoformat()}, f)
            return current_balance

        with open("data/initial_balance.json", "r") as f:
            data = json.load(f)
            return data.get("initial_balance", 0)
    except Exception as e:
        log(f"Error getting initial balance: {e}", level="ERROR")
        try:
            from utils_core import get_cached_balance

            return get_cached_balance() or 100
        except Exception:
            return 100


def check_drawdown_protection(balance):
    """
    Implements simple drawdown-based risk reduction or pause.
    """
    initial_balance = get_initial_balance()
    if initial_balance == 0:
        log("Cannot calculate drawdown: initial balance is 0", level="WARNING")
        return {"status": "normal"}

    drawdown_percent = ((initial_balance - balance) / initial_balance) * 100
    log(f"Current drawdown: {drawdown_percent:.2f}% (Balance: {balance:.2f}, Initial: {initial_balance:.2f})", level="DEBUG")

    if drawdown_percent >= 15:
        from common.config_loader import set_bot_status

        set_bot_status("paused")

        message = f"⚠️ CRITICAL: {drawdown_percent:.1f}% drawdown. Bot paused."
        log(message, level="ERROR")
        send_telegram_message(message, force=True)
        return {
            "status": "paused",
            "drawdown": drawdown_percent,
            "initial_balance": initial_balance,
            "current_balance": balance,
        }
    elif drawdown_percent >= 8:
        current_max_risk = get_max_risk()
        new_max_risk = current_max_risk * 0.75
        set_max_risk(new_max_risk)

        message = f"⚠️ WARNING: {drawdown_percent:.1f}% drawdown. Risk reduced to {new_max_risk*100:.1f}%."
        log(message, level="WARNING")
        send_telegram_message(message, force=True)
        return {
            "status": "reduced_risk",
            "drawdown": drawdown_percent,
            "new_risk": new_max_risk,
            "initial_balance": initial_balance,
            "current_balance": balance,
        }

    return {"status": "normal", "drawdown": drawdown_percent}


def calculate_position_value_limit(balance):
    """
    Calculate maximum allowed position value based on account balance
    """
    if balance < 120:
        return balance * 0.35
    elif balance < 300:
        return balance * 0.40
    else:
        return balance * 0.50


def get_max_total_exposure(balance):
    """
    Calculate maximum total exposure across all positions
    """
    if balance < 300:
        return balance * 0.70
    else:
        return balance * 0.90


def calculate_current_risk():
    """
    Calculate total notional exposure / balance * 100
    """
    try:
        from utils_core import get_cached_balance

        bal = get_cached_balance()
        if not bal or bal == 0:
            return 0.0

        positions = exchange.fetch_positions()
        total_notional = 0.0
        for pos in positions:
            if float(pos.get("contracts", 0)) > 0:
                contracts = float(pos.get("contracts", 0))
                entry_price = float(pos.get("entryPrice", 0))
                total_notional += contracts * entry_price

        return (total_notional / bal) * 100
    except Exception as e:
        log(f"Error calculating current risk: {e}", level="ERROR")
        return 0.0
