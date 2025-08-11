# core/scalping_mode.py
# Currently unused, but kept for possible future logic
# (switching timeframes: 3m vs 15m).

from common.config_loader import GLOBAL_SCALPING_TEST, get_priority_small_balance_pairs


def determine_strategy_mode(symbol, balance):
    """
    Decide whether to use 'scalp' or 'standard' mode based on balance and priority pairs.
    """
    if GLOBAL_SCALPING_TEST or balance < 300:
        return "scalp"

    if balance < 500 and symbol in get_priority_small_balance_pairs():
        return "scalp"

    # Допустим, у вас есть список “особо волатильных” монет
    if symbol in ["DOGE/USDC", "XRP/USDC", "SUI/USDC", "ARB/USDC"]:
        return "scalp"

    # Иначе стандарт
    return "standard"
