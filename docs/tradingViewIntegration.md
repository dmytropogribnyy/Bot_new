def log_missed_signal(symbol, breakdown, reason=""):
"""
Логирует пропущенный сигнал в missed_signals.json + Telegram при высоком score
"""
import os
import json
from datetime import datetime

    from common.config_loader import TAKER_FEE_RATE
    from telegram.telegram_utils import send_telegram_message
    from utils_core import extract_symbol
    from utils_logging import log

    missed_profit_total = 0.0  # глобально или через state

    symbol = extract_symbol(symbol)
    timestamp = datetime.utcnow().isoformat()

    # Подсчёт силы сигнала
    primary_sum = sum([
        breakdown.get("MACD", 0),
        breakdown.get("EMA_CROSS", 0),
        breakdown.get("RSI", 0),
    ])
    secondary_sum = sum([
        breakdown.get("Volume", 0),
        breakdown.get("PriceAction", 0),
        breakdown.get("HTF", 0),
    ])

    signal_score = breakdown.get("signal_score", 0.0)

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
        "signal_score": round(signal_score, 3),
        "components": breakdown,
    }

    # Telegram при сильном, но пропущенном сигнале
    if signal_score >= 0.85:
        send_telegram_message(f"📉 Missed strong signal {symbol} (score={signal_score})", force=True)

    os.makedirs("data", exist_ok=True)
    filepath = "data/missed_signals.json"

    try:
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
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
