# aggressiveness_controller.py — расчёт уровня агрессивности торговли

import json
import os
import threading
from datetime import datetime

from utils_logging import log

AGGRESSIVENESS_FILE = "data/aggressiveness.json"
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


def update_aggressiveness(winrate, sl_ratio, tp2_ratio, avg_pnl):
    """
    Обновляет уровень агрессивности на основе статистики торговли.
    """
    with LOCK:
        old_score = aggressiveness_data.get("score", 0.5)

        # Расчёт нового значения с EMA-сглаживанием
        raw = 0.25 * winrate + 0.25 * (1 - sl_ratio) + 0.25 * tp2_ratio + 0.25 * avg_pnl
        new_score = 0.7 * old_score + 0.3 * raw
        new_score = round(max(0.0, min(1.0, new_score)), 2)

        aggressiveness_data["score"] = new_score
        aggressiveness_data["updated_at"] = datetime.utcnow().isoformat()
        aggressiveness_data.setdefault("history", []).append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "winrate": winrate,
                "sl_ratio": sl_ratio,
                "tp2_ratio": tp2_ratio,
                "avg_pnl": avg_pnl,
                "score": new_score,
            }
        )

        save_aggressiveness()
        log(f"🤖 Aggressiveness score updated: {old_score} → {new_score}")


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
