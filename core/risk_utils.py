# risk_utils.py

from datetime import datetime
from pathlib import Path

from core.exchange_init import exchange
from utils_core import load_json_file, save_json_file
from utils_logging import log

RUNTIME_CONFIG_FILE = Path("data/runtime_config.json")

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
    Возвращает лимит одновременных позиций:
    - если config указывает max_concurrent_positions → это максимум
    - но реальный лимит также ограничен разумным порогом по балансу
    """
    from utils_core import get_runtime_config
    from utils_logging import log

    try:
        config = get_runtime_config()
        max_configured = config.get("max_concurrent_positions", 12)
    except Exception as e:
        log(f"[Risk] Failed to load runtime_config: {e}", level="WARNING")
        max_configured = 12

    # 💡 Баланс-адаптивный лимит:
    if balance < 120:
        limit = 2
    elif balance < 200:
        limit = 3
    elif balance < 300:
        limit = 5
    elif balance < 400:
        limit = 6
    else:
        limit = 8  # default cap

    # Не превышаем лимит из config (если он ниже)
    final_limit = min(limit, max_configured)

    log(f"[Risk] Max positions: {final_limit} (balance={balance:.2f}, config={max_configured})", level="DEBUG")
    return final_limit


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


def check_capital_utilization(symbol, qty, entry_price, threshold=0.8):
    """
    Проверяет, не превышает ли суммарная капитализация открытых ордеров `threshold` от баланса.
    Учитывает активные позиции из trade_manager + текущую заявку.
    """
    from core.trade_engine import trade_manager
    from utils_core import get_cached_balance
    from utils_logging import log

    balance = get_cached_balance()
    if balance <= 0:
        log(f"[Risk] Balance is zero or invalid: {balance}", level="ERROR")
        return False

    total_commitment = 0.0
    try:
        for sym in trade_manager._trades.values():
            sym_qty = sym.get("qty", 0)
            sym_price = sym.get("entry", 0)
            total_commitment += float(sym_qty) * float(sym_price)
    except Exception as e:
        log(f"[Risk] Error calculating capital utilization: {e}", level="ERROR")
        return False

    current_notional = qty * entry_price
    total_commitment += current_notional

    utilization = total_commitment / balance

    log(f"[Risk] Capital utilization after adding {symbol}: {utilization:.2%} of balance ({total_commitment:.2f} / {balance:.2f})", level="DEBUG")

    if utilization > threshold:
        log(f"[Risk] Capital utilization exceeds threshold: {utilization:.2%} > {threshold:.0%}", level="WARNING")
        return False

    return True


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


def check_drawdown_protection(current_balance):
    """
    Проверяет уровень просадки от начального баланса.
    """
    try:
        initial_balance = get_initial_balance()
        if initial_balance <= 0:
            log("[Drawdown] Initial balance is zero — skipping drawdown check.", level="WARNING")
            return {"status": "ok"}

        drawdown_percent = 100 * (initial_balance - current_balance) / initial_balance
        log(f"[Drawdown] Current drawdown: {drawdown_percent:.2f}%", level="DEBUG")

        if drawdown_percent >= 15.0:
            log("[Drawdown] Critical drawdown reached (≥15%) — pausing trading.", level="WARNING")
            return {"status": "paused"}

        elif drawdown_percent >= 8.0:
            cfg = load_json_file(RUNTIME_CONFIG_FILE)
            current_risk = cfg.get("max_risk", 0.015)
            reduced_risk = round(current_risk * 0.5, 5)
            cfg["max_risk"] = reduced_risk
            save_json_file(RUNTIME_CONFIG_FILE, cfg)
            log(f"[Drawdown] Moderate drawdown (≥8%) — reduced risk from {current_risk:.5f} to {reduced_risk:.5f}", level="WARNING")
            return {"status": "reduced_risk"}

        return {"status": "ok"}

    except Exception as e:
        log(f"[Drawdown] Error checking drawdown: {e}", level="ERROR")
        return {"status": "ok"}


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
