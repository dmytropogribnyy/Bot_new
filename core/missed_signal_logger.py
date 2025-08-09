# missed_signal_logger.py

import json
import os

from constants import MISSED_SIGNALS_LOG_FILE
from utils_logging import log


def log_missed_signal(symbol, breakdown, reason=""):
    """
    Log missed trading signals for analysis (without score) + estimate missed TP1 profit.

    Args:
        symbol (str): Trading pair symbol
        breakdown (dict): Components breakdown
        reason (str): Reason for signal rejection
    """
    import json
    import os
    from datetime import datetime

    from common.config_loader import TAKER_FEE_RATE

    from telegram.telegram_utils import send_telegram_message
    from utils_core import extract_symbol
    from utils_logging import log

    global missed_profit_total
    if "missed_profit_total" not in globals():
        missed_profit_total = 0.0

    symbol = extract_symbol(symbol)
    timestamp = datetime.utcnow().isoformat()

    # Подсчёт силы сигнала
    primary_sum = sum(
        [
            breakdown.get("MACD", 0),
            breakdown.get("EMA_CROSS", 0),
            breakdown.get("RSI", 0),
        ]
    )
    secondary_sum = sum(
        [
            breakdown.get("Volume", 0),
            breakdown.get("PriceAction", 0),
            breakdown.get("HTF", 0),
        ]
    )

    signal_score = breakdown.get("signal_score", 0.0)
    if signal_score >= 0.85:
        send_telegram_message(f"📛 Missed strong signal {symbol} (score={signal_score:.2f})", force=True)

    log_entry = {
        "timestamp": timestamp,
        "symbol": symbol,
        "reason": reason,
        "atr_pct": round(breakdown.get("atr_percent", 0), 5),
        "volume": round(breakdown.get("volume", 0), 1),
        "rsi": round(breakdown.get("rsi", 0), 2),
        "risk_factor": round(breakdown.get("risk_factor", 0), 3),
        "entry_notional": round(breakdown.get("entry_notional", 0), 2),
        "passes_1plus1": breakdown.get("passes_1plus1", False),
        "primary_sum": primary_sum,
        "secondary_sum": secondary_sum,
        "signal_score": round(signal_score, 4),
        "components": breakdown,
    }

    # ✅ Попытка рассчитать упущенную прибыль TP1
    try:
        entry = breakdown.get("entry")
        tp1 = breakdown.get("tp1")
        qty = breakdown.get("qty")
        direction = breakdown.get("side", "buy")

        if entry and tp1 and qty:
            share_tp1 = 0.7  # можно вытянуть из конфигурации при желании
            gross = (tp1 - entry) * qty * share_tp1 if direction == "buy" else (entry - tp1) * qty * share_tp1
            commission = 2 * qty * entry * TAKER_FEE_RATE
            net_profit = round(gross - commission, 2)

            missed_profit_total += net_profit
            log(f"[MISSED PROFIT] {symbol} → ~${net_profit:.2f} missed TP1", level="WARNING")

            # Уведомление, если накопилось
            if missed_profit_total >= 1.0:
                send_telegram_message(f"📉 Упущено потенциальной прибыли: ${missed_profit_total:.2f}")
                missed_profit_total = 0.0  # сброс

            # Можно записать в лог-файл отдельный missed_profits.json — при желании
            log_entry["missed_profit"] = net_profit

    except Exception as e:
        log(f"[MISSED PROFIT] Failed to estimate for {symbol}: {e}", level="ERROR")

    # ✅ Логируем сигнал в JSON
    try:
        os.makedirs("data", exist_ok=True)
        filepath = MISSED_SIGNALS_LOG_FILE

        if os.path.exists(filepath):
            with open(filepath) as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    data = []
        else:
            data = []

        data = data[-99:] + [log_entry]

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        log(f"{symbol} Logged missed signal: {reason}", level="DEBUG")

    except Exception as e:
        log(f"Error logging missed signal: {e}", level="ERROR")


def get_recent_missed_signals(limit=10):
    """
    Get the most recent missed signals.

    Args:
        limit (int): Maximum number of signals to return

    Returns:
        list: Recent missed signals
    """
    from constants import MISSED_SIGNALS_LOG_FILE

    filepath = MISSED_SIGNALS_LOG_FILE
    if not os.path.exists(filepath):
        return []

    try:
        with open(filepath) as f:
            data = json.load(f)

        sorted_data = sorted(data, key=lambda x: x.get("timestamp", ""), reverse=True)
        return sorted_data[:limit]
    except Exception as e:
        log(f"Error reading missed signals: {e}", level="ERROR")
        return []
