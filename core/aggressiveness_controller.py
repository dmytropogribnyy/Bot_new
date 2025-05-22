# aggressiveness_controller.py — расчёт уровня агрессивности торговли

import json
import os
import threading
from datetime import datetime

from constants import AGGRESSIVENESS_FILE
from utils_logging import log

LOCK = threading.Lock()

aggressiveness_data = {
    "score": 0.5,
    "history": [],
    "updated_at": None,
}


def load_aggressiveness():
    if os.path.exists(AGGRESSIVENESS_FILE):
        try:
            with open(AGGRESSIVENESS_FILE, "r") as f:
                data = json.load(f)
                aggressiveness_data.update(data)
        except Exception as e:
            log(f"Failed to load aggressiveness: {e}", level="WARNING")


def save_aggressiveness():
    try:
        with open(AGGRESSIVENESS_FILE, "w") as f:
            json.dump(aggressiveness_data, f, indent=2)
    except Exception as e:
        log(f"Failed to save aggressiveness: {e}", level="ERROR")


def update_aggressiveness(winrate, sl_ratio, tp2_ratio, avg_pnl, balance=None):
    """
    Updates aggressiveness level based on trading statistics with account size awareness.

    Args:
        winrate: Win percentage (0.0-1.0)
        sl_ratio: Ratio of stop-loss hits
        tp2_ratio: Ratio of TP2 hits
        avg_pnl: Average profit and loss
        balance: Current account balance (for small account adaptation)
    """
    with LOCK:
        old_score = aggressiveness_data.get("score", 0.5)

        # Calculate raw score
        raw = 0.25 * winrate + 0.25 * (1 - sl_ratio) + 0.25 * tp2_ratio + 0.25 * avg_pnl

        # Apply account size adaptation if balance is provided
        if balance is not None:
            # More conservative for small accounts
            if balance < 120:
                # For micro accounts, cap maximum aggressiveness
                raw = min(raw, 0.6)
                # Use more momentum from old score (slower changes)
                new_score = 0.8 * old_score + 0.2 * raw
            elif balance < 300:
                # For small accounts, moderate aggressiveness cap
                raw = min(raw, 0.75)
                # Slightly slower adaptation
                new_score = 0.75 * old_score + 0.25 * raw
            else:
                # Normal calculation for larger accounts
                new_score = 0.7 * old_score + 0.3 * raw
        else:
            # Original calculation if no balance provided
            new_score = 0.7 * old_score + 0.3 * raw

        new_score = round(max(0.0, min(1.0, new_score)), 2)

        # Update data
        aggressiveness_data["score"] = new_score
        aggressiveness_data["updated_at"] = datetime.utcnow().isoformat()
        aggressiveness_data.setdefault("history", []).append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "winrate": winrate,
                "sl_ratio": sl_ratio,
                "tp2_ratio": tp2_ratio,
                "avg_pnl": avg_pnl,
                "balance": balance,
                "score": new_score,
            }
        )

        save_aggressiveness()
        log(f"🤖 Aggressiveness score updated: {old_score} → {new_score}" + (f" (Small Account: {balance} USDC)" if balance and balance < 300 else ""))


def get_aggressiveness_score():
    return aggressiveness_data.get("score", 0.5)


def get_aggressiveness_info():
    """
    Возвращает информацию для Telegram-команды /aggressive_status
    """
    return {
        "score": get_aggressiveness_score(),
        "updated_at": aggressiveness_data.get("updated_at"),
        "history_len": len(aggressiveness_data.get("history", [])),
    }


load_aggressiveness()
