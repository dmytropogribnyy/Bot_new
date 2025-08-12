import os

import pandas as pd
from common.config_loader import CONFIG_FILE, EXPORT_PATH

from telegram.telegram_utils import escape_markdown_v2, send_telegram_message
from utils_core import get_cached_balance, get_runtime_config
from core.unified_logger import UnifiedLogger

_ULOG = UnifiedLogger()


def log(message: str, level: str = "INFO") -> None:
    _ULOG.log_event("TP_OPT", level, message)


def backup_config(path: str = "data/runtime_config.json") -> None:
    try:
        import shutil
        from datetime import datetime, timezone

        if not os.path.exists(path):
            log(f"Config file not found for backup: {path}", level="WARNING")
            return
        os.makedirs("data/backups", exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M")
        dst = os.path.join("data/backups", f"runtime_config_{ts}.json")
        shutil.copy(path, dst)
        log(f"Backed up config to {dst}", level="INFO")
    except Exception as e:
        log(f"Backup failed: {e}", level="ERROR")


CONFIG_PATH = CONFIG_FILE


def evaluate_best_config(days=7):
    """
    Анализирует сделки за 'days' дней и при необходимости
    обновляет step_tp_levels в runtime_config.json.
    """
    from common.config_loader import RUNTIME_CONFIG_PATH

    from tp_optimizer import _update_config_tp
    from utils_core import load_json_file

    if not os.path.exists(EXPORT_PATH):
        send_telegram_message("❌ No trade history found for optimization.", force=True)
        return

    try:
        df = pd.read_csv(EXPORT_PATH, parse_dates=["Date"])
        # NEW: Handle invalid dates
        invalid_dates = df[df["Date"].isna() | df["Date"].astype(str).str.contains("NaT", na=False)]
        if not invalid_dates.empty:
            log(f"[TP Optimizer] Invalid dates found in {len(invalid_dates)} rows — skipping them", level="WARNING")
            for idx, row in invalid_dates.iterrows():
                log(f"[Invalid Date] Row {idx}: Date='{row['Date']}'", level="DEBUG")
            df = df.dropna(subset=["Date"])  # Drop NaT/NaN dates
            df = df[~df["Date"].astype(str).str.contains("NaT", na=False)]  # Extra filter for "NaT" strings

        df = df[df["Date"] >= pd.Timestamp.now().normalize() - pd.Timedelta(days=days)]

        if df.empty:
            send_telegram_message("ℹ️ No recent trades for TP analysis.", force=True)
            return

        balance = get_cached_balance()
        config = get_runtime_config()  # Загружаем runtime config
        # ✅ Теперь конфигурируемо: дефолты как в твоём коде, но из JSON
        tp_min_trades = (
            config.get("tp_min_trades_initial", 10) if balance < 300 else config.get("tp_min_trades_full", 20)
        )
        update_threshold = (
            config.get("tp_update_threshold_initial", 0.1)
            if balance < 300
            else config.get("tp_update_threshold_full", 0.2)
        )

        total = len(df)
        if total < tp_min_trades:
            send_telegram_message(
                f"ℹ️ Not enough trades for TP optimization (need {tp_min_trades}, have {total})", force=True
            )
            return

        # ✅ Boolean hits
        tp1_hits = df[df["TP1 Hit"]]
        tp2_hits = df[df["TP2 Hit"]]
        sl_hits = df[df["SL Hit"]]

        avg_pnl = df["Net PnL (%)"].mean()
        tp1_winrate = round(len(tp1_hits) / total * 100, 1)
        tp2_winrate = round(len(tp2_hits) / total * 100, 1)
        sl_rate = round(len(sl_hits) / total * 100, 1)

        msg = (
            f"📊 *TP/SL Performance ({days}d)*\n"
            f"Balance: ${balance:.2f}\n"
            f"Total Trades: {total}\n"
            f"• TP1 hit: {len(tp1_hits)} ({tp1_winrate}%)\n"
            f"• TP2 hit: {len(tp2_hits)} ({tp2_winrate}%)\n"
            f"• SL hit: {len(sl_hits)} ({sl_rate}%)\n"
            f"• Avg Net PnL: {avg_pnl:.2f}%"
        )
        send_telegram_message(escape_markdown_v2(msg), force=True)

        # 📥 Получаем текущие TP уровни из runtime_config.json
        config = load_json_file(RUNTIME_CONFIG_PATH)
        current_tp1 = config.get("step_tp_levels", [0.07])[0]
        current_tp2 = config.get("step_tp_levels", [0.07, 0.12])[1]

        # 📈 Новые TP уровни на основе winrate
        new_tp1 = 0.007 + (tp1_winrate - 60) * 0.0002
        new_tp2 = 0.014 + (tp2_winrate - 40) * 0.0003

        if balance < 300:
            new_tp1 = max(0.005, min(new_tp1, 0.015))
            new_tp2 = max(0.008, min(new_tp2, 0.025))
        else:
            new_tp1 = max(0.004, min(new_tp1, 0.02))
            new_tp2 = max(0.007, min(new_tp2, 0.035))

        diff_tp1 = abs(new_tp1 - current_tp1) / max(current_tp1, 0.0001)
        diff_tp2 = abs(new_tp2 - current_tp2) / max(current_tp2, 0.0001)

        if diff_tp1 > update_threshold or diff_tp2 > update_threshold:
            backup_config()
            _update_config_tp(new_tp1, new_tp2)

            note = (
                f"✅ *TP levels auto-updated*\n"
                f"• Old: TP1 = {current_tp1:.4f}, TP2 = {current_tp2:.4f}\n"
                f"• New: TP1 = {new_tp1:.4f}, TP2 = {new_tp2:.4f}\n"
                f"• Threshold: {int(update_threshold * 100)}%\n"
                f"• Balance: ${balance:.2f}"
            )
            send_telegram_message(escape_markdown_v2(note), force=True)
        else:
            send_telegram_message("ℹ️ TP levels stable — no update needed.", force=True)

    except Exception as e:
        send_telegram_message(f"❌ TP Optimizer Error: {e}", force=True)


def _update_config_tp(tp1, tp2):
    from common.config_loader import RUNTIME_CONFIG_PATH

    from utils_core import load_json_file, save_json_file

    config = load_json_file(RUNTIME_CONFIG_PATH)

    # Преобразуем в step_tp_levels на базе новых tp1 и tp2
    config["step_tp_levels"] = [round(tp1, 4), round(tp2, 4), round(tp2 * 1.8, 4)]
    config["step_tp_sizes"] = [0.3, 0.3, 0.3]  # не трогаем

    save_json_file(RUNTIME_CONFIG_PATH, config)

    log(f"[TP Optimizer] Updated TP levels → step_tp_levels={config['step_tp_levels']}", level="INFO")


def run_tp_optimizer():
    """
    Главная точка входа: вызывает анализ TP1/TP2.
    """
    evaluate_best_config()
