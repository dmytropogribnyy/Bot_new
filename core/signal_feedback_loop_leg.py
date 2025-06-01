# signal_feedback_loop.py

from pathlib import Path

from constants import TP_PERFORMANCE_FILE
from utils_core import (
    get_cached_balance,
    get_runtime_config,
    update_runtime_config,
)
from utils_logging import log


def get_tp_file_path():
    """Convert TP_PERFORMANCE_FILE string to a Path object."""
    return Path(TP_PERFORMANCE_FILE)


def calculate_winrate(results: list[str]) -> float:
    """Подсчёт винрейта (TP1/TP2) среди списка результатов сделок."""
    if not results:
        return 0.0
    total = len(results)
    wins = sum(1 for r in results if r.upper() in ("TP1", "TP2"))
    return round(wins / total, 4) if total > 0 else 0.0


# =========================
# 1) TP2 Winrate Analysis
# =========================


def analyze_tp2_winrate():
    """
    Анализ winrate по TP2 и установка risk_multiplier.
    """
    tp_path = get_tp_file_path()
    if not tp_path.exists():
        log("[TP2 Analysis] tp_performance.csv not found", level="WARNING")
        return

    rows = tp_path.read_text().splitlines()
    if not rows or len(rows) < 2:
        return

    headers = rows[0].split(",")
    data = [r.split(",") for r in rows[1:] if len(r.split(",")) == len(headers)]

    def extract_col(col):
        try:
            idx = headers.index(col)
            return [row[idx] for row in data]
        except ValueError:
            return []

    results = extract_col("Result")

    tp2_hits = sum(1 for r in results if r.upper() == "TP2")
    total_trades = len(results)

    if total_trades < 10:
        log(f"[TP2 Analysis] Not enough trades for reliable analysis ({total_trades})", level="INFO")
        return

    tp2_winrate = tp2_hits / total_trades if total_trades > 0 else 0

    # Чем выше tp2_winrate, тем выше risk_multiplier
    if tp2_winrate > 0.20:
        risk_multiplier = 1.3
    elif tp2_winrate > 0.15:
        risk_multiplier = 1.2
    elif tp2_winrate > 0.10:
        risk_multiplier = 1.1
    elif tp2_winrate < 0.05:
        risk_multiplier = 0.9
    else:
        risk_multiplier = 1.0

    log(f"[TP2 Analysis] TP2 winrate: {tp2_winrate:.2%} → Risk multiplier: {risk_multiplier:.2f}")
    update_runtime_config({"risk_multiplier": round(risk_multiplier, 2)})


# =========================
# 2) Max Positions
# =========================


def adjust_max_concurrent_positions():
    """
    Динамически меняет max_concurrent_positions
    на основе TP2 winrate, баланса и агрессивности.
    """
    from tp_optimizer import analyze_tp_performance

    balance = get_cached_balance()
    config = get_runtime_config()
    aggression = config.get("strategy_aggressiveness", 1.0)
    tp_stats = analyze_tp_performance()
    winrate_tp2 = tp_stats.get("tp2_winrate", 0.0)
    trade_count = tp_stats.get("tp2_count", 0)

    if trade_count < 30:
        return

    # База от winrate
    if winrate_tp2 >= 0.7:
        base = 12
    elif winrate_tp2 >= 0.6:
        base = 9
    elif winrate_tp2 >= 0.5:
        base = 6
    else:
        base = 4

    # Корректируем на баланс и агрессию
    if balance > 200:
        base += 2
    if aggression > 1.2:
        base += 2

    new_limit = max(3, min(base, 20))
    update_runtime_config({"max_concurrent_positions": new_limit})

    log(f"[Position Scaling] TP2 winrate: {winrate_tp2:.2%}, Balance: {balance:.2f}, Aggression: {aggression:.2f} → Max positions: {new_limit}", level="INFO")


# =========================
# 3) Wick Sensitivity
# =========================


def adjust_wick_sensitivity():
    """
    Адаптируем wick_sensitivity на основе разницы (spread) TP1/TP2 винрейтов.
    """
    from tp_optimizer import analyze_tp_performance

    stats = analyze_tp_performance()
    tp2_winrate = stats.get("tp2_winrate", 0.0)
    tp1_winrate = stats.get("tp1_winrate", 0.0)

    spread = abs(tp2_winrate - tp1_winrate)
    base = 0.3

    if spread >= 0.25:
        new_wick = 0.15
    elif spread >= 0.15:
        new_wick = 0.25
    else:
        new_wick = base

    update_runtime_config({"wick_sensitivity": round(new_wick, 3)})
    log(f"[Wick Sensitivity] TP1-TP2 Spread: {spread:.2f} → Sensitivity: {new_wick:.3f}", level="INFO")


# =========================
# 4) analyze_signal_blockers
# =========================


def analyze_signal_blockers(debug_summary_path="data/debug_monitoring_summary.json", config_path="data/runtime_config.json", min_block_threshold=4):
    """
    Анализ причин пропуска сигналов (из debug_monitoring_summary.json)
    и при необходимости адаптация фильтров.
    Убраны все ссылки на score/HTF.
    """
    import json
    from datetime import datetime
    from pathlib import Path

    debug_path = Path(debug_summary_path)
    configp = Path(config_path)
    history_path = Path("data/parameter_history.json")

    if not debug_path.exists() or not configp.exists():
        return {"error": "Required file not found."}

    with debug_path.open("r", encoding="utf-8") as f:
        debug_data = json.load(f)

    top_reasons = debug_data.get("missed_analysis", {}).get("top_reasons", {})
    if not top_reasons:
        log(f"[SignalFeedback] No changes, blockers: {top_reasons}", level="DEBUG")
        return {"message": "No blockers or reasons found in summary."}

    with configp.open("r", encoding="utf-8") as f:
        config = json.load(f)

    changes = {}

    # Ослабляем ATR-фильтр, если часто filter_low_volatility
    if top_reasons.get("filter_low_volatility", 0) >= min_block_threshold:
        new_tiers = []
        for tier in config.get("FILTER_TIERS", []):
            new_atr = max(tier["atr"] * 0.7, 0.0015)
            new_tiers.append({"atr": new_atr, "volume": tier["volume"]})
        config["FILTER_TIERS"] = new_tiers
        changes["FILTER_TIERS"] = "reduced due to frequent filter_low_volatility"

    # Можем ослабить volume-фильтр, если часто missing_volume
    if top_reasons.get("missing_volume", 0) >= min_block_threshold:
        updated_tiers = []
        for tier in config.get("FILTER_TIERS", []):
            new_vol = max(tier["volume"] * 0.8, 200)
            updated_tiers.append({"atr": tier["atr"], "volume": new_vol})
        config["FILTER_TIERS"] = updated_tiers
        changes["FILTER_TIERS_volume"] = "relaxed due to frequent missing_volume"

    # Если часто missing_1plus1, чуть снижаем rsi_threshold
    if top_reasons.get("missing_1plus1", 0) >= min_block_threshold:
        rsi_thr = config.get("rsi_threshold", 50)
        new_rsi_thr = max(rsi_thr - 5, 30)
        config["rsi_threshold"] = new_rsi_thr
        changes["rsi_threshold"] = f"decreased from {rsi_thr} to {new_rsi_thr}"

    if not changes:
        log(f"[SignalFeedback] No changes applied, blockers: {top_reasons}", level="DEBUG")
        return {"message": "No changes applied"}

    # Сохраняем обновлённый конфиг
    with configp.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    # Логируем изменения в parameter_history.json
    if history_path.exists():
        with history_path.open("r", encoding="utf-8") as f:
            history = json.load(f)
    else:
        history = []

    timestamp = datetime.now().isoformat()
    history.append({"timestamp": timestamp, "source": "auto_blocker_analysis", "changes": changes})

    with history_path.open("w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

    log(f"[SignalFeedback] Applied blocker-based config changes: {changes}", level="INFO")
    # Можно обновить last_adaptation_timestamp (опционально)
    update_runtime_config({"last_adaptation_timestamp": timestamp})

    return {"timestamp": timestamp, "applied_changes": changes}


# =========================
# 5) Основная точка адаптации
# =========================


def analyze_and_adapt_strategy():
    """
    Full strategy adaptation cycle, вызываем нужные анализы.
    Убрали старые HTF / relax_factor / score.
    """
    log("🧠 Starting full strategy adaptation", level="INFO")
    try:
        # 1) TP2 risk
        analyze_tp2_winrate()
        # 2) max positions
        adjust_max_concurrent_positions()
        # 3) wick sensitivity
        adjust_wick_sensitivity()
        # 4) signal blockers
        analyze_signal_blockers()

        log("✅ Strategy adaptation cycle completed", level="INFO")
    except Exception as e:
        log(f"⚠️ Error during strategy adaptation: {e}", level="ERROR")


# =========================
# 6) Инициализация
# =========================


def initialize_runtime_adaptive_config():
    """
    Задаём базовые значения config при старте бота.
    Без HTF, relax_factor, score и т.д.
    """
    balance = get_cached_balance()

    if balance < 120:
        max_positions = 3
    elif balance < 200:
        max_positions = 5
    else:
        max_positions = 8

    current_config = get_runtime_config()

    defaults = {
        "max_concurrent_positions": max_positions,
        "strategy_aggressiveness": 1.0,
        "risk_multiplier": 1.0,
        "wick_sensitivity": 0.3,
        "rsi_threshold": 50,
        "rel_volume_threshold": 0.5,
        "SL_PERCENT": 0.015,
        # Флаг для отметки времени последней адаптации (при желании)
        "last_adaptation_timestamp": None,
    }

    update_needed = False
    for key, value in defaults.items():
        if key not in current_config:
            update_needed = True

    if update_needed:
        missing_values = {k: v for k, v in defaults.items() if k not in current_config}
        update_runtime_config(missing_values)
        log(f"Initialized missing runtime config values: {missing_values}", level="INFO")
