# core/risk_adjuster.py

from common.config_loader import get_cached_balance, trade_stats
from telegram.telegram_utils import send_telegram_message
from utils_core import update_runtime_config
from utils_logging import log


def auto_adjust_risk():
    """
    Автоматическая адаптация risk_multiplier в runtime_config
    на основе winrate, streak и баланса.
    """
    try:
        balance = get_cached_balance() or 0.0
        total = trade_stats.get("total", 0)
        wins = trade_stats.get("wins", 0)
        streak_win = trade_stats.get("streak_win", 0)
        streak_loss = trade_stats.get("streak_loss", 0)

        if total < 10:
            log("[AutoRisk] Not enough trades yet (total < 10). Skipping update.", level="INFO")
            return

        winrate = (wins / total) * 100
        base_risk = 0.01  # 1% базовый риск
        new_risk = base_risk

        # 🔼 Повышаем риск при хорошей серии
        if winrate > 60 and streak_win >= 3 and balance > 300:
            new_risk = base_risk * 1.5
        # 🔽 Снижаем при серии лоссов или маленьком балансе
        elif streak_loss >= 3 or balance < 80:
            new_risk = base_risk * 0.5

        # Ограничения
        new_risk = max(0.003, min(new_risk, 0.03))

        update_runtime_config({"risk_multiplier": round(new_risk, 4)})

        msg = f"🤖 AutoRisk → {new_risk*100:.2f}%\n" f"(total={total}, wins={wins}, w%={winrate:.1f}, " f"streak_win={streak_win}, streak_loss={streak_loss}, balance={balance:.2f})"
        log(f"[AutoRisk] {msg}", level="INFO")
        send_telegram_message(msg, force=True, parse_mode="")

    except Exception as e:
        log(f"[AutoRisk] Error: {e}", level="ERROR")
        send_telegram_message(f"❌ AutoRisk error: {e}", force=True)
