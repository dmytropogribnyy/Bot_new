import statistics
from pathlib import Path

from constants import TP_PERFORMANCE_FILE
from utils_core import get_cached_balance, get_runtime_config, update_runtime_config
from utils_logging import log

VOLATILITY_METRICS = ["atr", "adx", "bb_width"]
HTF_THRESHOLD = 0.10
HTF_MIN_TRADES = 30


def get_tp_file_path():
    """Convert TP_PERFORMANCE_FILE string to a Path object."""
    return Path(TP_PERFORMANCE_FILE)


def calculate_winrate(results: list[str]) -> float:
    if not results:
        return 0.0
    total = len(results)
    wins = sum(1 for r in results if r.upper() in ("TP1", "TP2"))
    return round(wins / total, 4) if total > 0 else 0.0


def analyze_htf_and_volatility():
    if not get_tp_file_path().exists():
        log("[HTF/Volatility] tp_performance.csv not found", level="WARNING")
        return

    rows = get_tp_file_path().read_text().splitlines()
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
    htf_flags = extract_col("HTF Confirmed")

    if not results or not htf_flags:
        return

    true_results = [r for r, h in zip(results, htf_flags) if h.lower() == "true"]
    false_results = [r for r, h in zip(results, htf_flags) if h.lower() == "false"]

    true_winrate = calculate_winrate(true_results)
    false_winrate = calculate_winrate(false_results)

    htf_enabled = len(true_results) >= HTF_MIN_TRADES and len(false_results) >= HTF_MIN_TRADES and false_winrate > 0 and (true_winrate - false_winrate) > HTF_THRESHOLD

    htf_confidence = min(1.0, max(0.0, (true_winrate - false_winrate) / 0.20))

    log(f"[HTF Feedback] Winrate True={true_winrate:.2%} | False={false_winrate:.2%} → USE_HTF={htf_enabled}, Confidence={htf_confidence:.2f}")

    # === Weighted Volatility ===
    weights = {"atr": 0.5, "adx": 0.3, "bb_width": 0.2}
    weighted_volatility = 0
    weight_sum = 0

    for metric, weight in weights.items():
        vals = extract_col(metric)
        floats = [float(v) for v in vals if v and v.replace(".", "", 1).isdigit()]
        if floats:
            weighted_volatility += statistics.mean(floats) * weight
            weight_sum += weight

    avg_volatility = round(weighted_volatility / weight_sum, 4) if weight_sum > 0 else 0.0
    log(f"[Volatility Feedback] Weighted Proxy={avg_volatility}")

    new_config = {
        "USE_HTF_CONFIRMATION": htf_enabled,
        "HTF_CONFIDENCE": round(htf_confidence, 2),
        "volatility_sensitivity": avg_volatility,
    }

    update_runtime_config(new_config)


def analyze_tp2_winrate():
    """
    Analyze TP2 winrate and set appropriate risk multiplier
    """
    if not get_tp_file_path().exists():
        log("[TP2 Analysis] tp_performance.csv not found", level="WARNING")
        return

    rows = get_tp_file_path().read_text().splitlines()
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

    # Count TP2 hits and total trades
    tp2_hits = sum(1 for r in results if r.upper() == "TP2")
    total_trades = len(results)

    if total_trades < 10:
        log(f"[TP2 Analysis] Not enough trades for reliable analysis ({total_trades})", level="INFO")
        return

    tp2_winrate = tp2_hits / total_trades if total_trades > 0 else 0

    # Calculate risk multiplier based on TP2 winrate
    # Higher TP2 winrate allows for higher risk
    if tp2_winrate > 0.20:
        risk_multiplier = 1.3  # 30% higher risk for excellent TP2 performance
    elif tp2_winrate > 0.15:
        risk_multiplier = 1.2  # 20% higher risk for good TP2 performance
    elif tp2_winrate > 0.10:
        risk_multiplier = 1.1  # 10% higher risk for decent TP2 performance
    elif tp2_winrate < 0.05:
        risk_multiplier = 0.9  # 10% lower risk for poor TP2 performance
    else:
        risk_multiplier = 1.0  # Default - no adjustment

    log(f"[TP2 Analysis] TP2 winrate: {tp2_winrate:.2%} → Risk multiplier: {risk_multiplier:.2f}")

    # Update runtime config
    update_runtime_config({"risk_multiplier": round(risk_multiplier, 2)})


def adjust_max_concurrent_positions():
    """
    Dynamically adjust maximum number of concurrent positions based on:
    1. TP2 winrate (higher winrate allows more concurrent positions)
    2. Account balance (larger accounts can handle more positions)
    3. Strategy aggressiveness (more aggressive strategies can use more positions)
    """
    from tp_optimizer import analyze_tp_performance

    balance = get_cached_balance()
    config = get_runtime_config()
    aggression = config.get("strategy_aggressiveness", 1.0)
    tp_stats = analyze_tp_performance()
    winrate_tp2 = tp_stats.get("tp2_winrate", 0.0)
    trade_count = tp_stats.get("tp2_count", 0)

    # 🔒 Minimum 30 trades for scaling
    if trade_count < 30:
        return

    # 💡 Base level from winrate
    if winrate_tp2 >= 0.7:
        base = 12
    elif winrate_tp2 >= 0.6:
        base = 9
    elif winrate_tp2 >= 0.5:
        base = 6
    else:
        base = 4

    # ⚖️ Balance + aggression modifications
    if balance > 200:
        base += 2
    if aggression > 1.2:
        base += 2

    new_limit = max(3, min(base, 20))
    update_runtime_config({"max_concurrent_positions": new_limit})

    log(f"[Position Scaling] TP2 winrate: {winrate_tp2:.2%}, Balance: {balance:.2f}, Aggression: {aggression:.2f} → Max positions: {new_limit}", level="INFO")


def adjust_wick_sensitivity():
    """
    Adapt wick sensitivity based on the spread between TP1 and TP2 winrates.
    Higher spread suggests being less sensitive to wicks.
    """
    from tp_optimizer import analyze_tp_performance

    stats = analyze_tp_performance()
    tp2_winrate = stats.get("tp2_winrate", 0.0)
    tp1_winrate = stats.get("tp1_winrate", 0.0)

    # Analyze TP1 to TP2 ratio spread
    spread = abs(tp2_winrate - tp1_winrate)
    base = 0.3

    if spread >= 0.25:
        new_wick = 0.15  # Strong spread - be less sensitive to wicks
    elif spread >= 0.15:
        new_wick = 0.25
    else:
        new_wick = base  # Moderate approach

    update_runtime_config({"wick_sensitivity": round(new_wick, 3)})
    log(f"[Wick Sensitivity] TP1-TP2 Spread: {spread:.2f} → Sensitivity: {new_wick:.3f}", level="INFO")


def toggle_htf_filter():
    """
    Enable or disable HTF confirmation based on comparative performance.
    """
    from tp_optimizer import analyze_tp_performance

    stats = analyze_tp_performance()
    win_htf = stats.get("htf_winrate", 0)
    win_non_htf = stats.get("non_htf_winrate", 0)
    total_htf = stats.get("htf_count", 0)
    total_non_htf = stats.get("non_htf_count", 0)

    if total_htf < 20 or total_non_htf < 20:
        log(f"[HTF Toggle] Insufficient data: HTF={total_htf} trades, Non-HTF={total_non_htf} trades", level="DEBUG")
        return  # Not enough data

    current_setting = get_runtime_config().get("USE_HTF_CONFIRMATION", True)
    new_setting = current_setting

    if win_htf > win_non_htf + 0.1:
        new_setting = True
        log(f"[HTF Toggle] HTF winrate superior by {(win_htf-win_non_htf):.2f} → Enabling HTF filter", level="INFO")
    elif win_non_htf > win_htf + 0.1:
        new_setting = False
        log(f"[HTF Toggle] Non-HTF winrate superior by {(win_non_htf-win_htf):.2f} → Disabling HTF filter", level="INFO")

    if new_setting != current_setting:
        update_runtime_config({"USE_HTF_CONFIRMATION": new_setting})


def adjust_relax_factor():
    """
    Adapt filter relaxation factor based on market volatility and overall performance.
    High volatility -> stricter filters (lower relax)
    Low volatility -> relaxed filters
    """
    from tp_optimizer import analyze_tp_performance
    from utils_core import get_market_volatility_index

    vol_index = get_market_volatility_index()
    stats = analyze_tp_performance()
    winrate = stats.get("total_winrate", 0.0)

    # Base level based on market conditions
    if vol_index > 1.5:
        relax = 0.2  # Active market - stricter
    elif vol_index < 0.8:
        relax = 0.4  # Quiet market - relax filters
    else:
        relax = 0.3

    # Adjustment based on performance
    if winrate > 0.65:
        relax += 0.05  # Good performance - can be less strict

    relax = round(min(max(relax, 0.15), 0.5), 3)  # Limit between 0.15 and 0.5

    update_runtime_config({"relax_factor": relax})
    log(f"[Relax Factor] Market volatility: {vol_index:.2f}, Winrate: {winrate:.2f} → Relax factor: {relax:.3f}", level="INFO")


def analyze_and_adapt_strategy():
    """
    Full strategy adaptation cycle that adjusts various parameters based on
    recent trading performance metrics.
    """
    log("🧠 Starting full strategy adaptation", level="INFO")
    try:
        analyze_htf_and_volatility()
        analyze_tp2_winrate()
        adjust_max_concurrent_positions()
        adjust_wick_sensitivity()
        toggle_htf_filter()
        adjust_relax_factor()
        log("✅ Strategy adaptation cycle completed", level="INFO")
    except Exception as e:
        log(f"⚠️ Error during strategy adaptation: {e}", level="ERROR")


def initialize_runtime_adaptive_config():
    """
    Initialize runtime configuration with adaptive parameters based on balance.
    Called at bot startup to ensure all parameters are set.
    """
    balance = get_cached_balance()

    # Get reasonable defaults based on balance
    if balance < 120:
        max_positions = 3
    elif balance < 200:
        max_positions = 5
    else:
        max_positions = 8

    # Set initial default values if they don't exist
    current_config = get_runtime_config()

    defaults = {
        "max_concurrent_positions": max_positions,
        "strategy_aggressiveness": 1.0,
        "risk_multiplier": 1.0,
        "USE_HTF_CONFIRMATION": True,
        "HTF_CONFIDENCE": 0.5,
        "wick_sensitivity": 0.3,
        "relax_factor": 0.3,
    }

    # Only update values that don't exist
    update_needed = False
    for key, value in defaults.items():
        if key not in current_config:
            update_needed = True

    if update_needed:
        missing_values = {k: v for k, v in defaults.items() if k not in current_config}
        update_runtime_config(missing_values)
        log(f"Initialized missing runtime config values: {missing_values}", level="INFO")


def adjust_score_relax_boost():
    """
    Адаптивно увеличивает или уменьшает score_relax_boost в зависимости от количества сделок за последний час.
    Позволяет стратегии смягчать требования при низкой активности.
    """
    from datetime import datetime, timedelta

    import pandas as pd

    from common.config_loader import EXPORT_PATH
    from utils_core import get_runtime_config, update_runtime_config
    from utils_logging import log

    try:
        df = pd.read_csv(EXPORT_PATH, parse_dates=["Date"])
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)
        three_hours_ago = now - timedelta(hours=3)

        trades_1h = df[df["Date"] >= one_hour_ago]
        trades_3h = df[df["Date"] >= three_hours_ago]

        trade_count_1h = len(trades_1h)
        trade_count_3h = len(trades_3h)

        runtime_config = get_runtime_config()
        current_boost = runtime_config.get("score_relax_boost", 1.0)

        # Низкая активность
        if trade_count_1h < 3:
            new_boost = min(1.3, current_boost + 0.1)
            log(f"[ScoreAdjust] Low activity: {trade_count_1h} trades/hour → boost {current_boost:.2f} → {new_boost:.2f}")
            update_runtime_config({"score_relax_boost": new_boost})

            if trade_count_3h < 1:
                emergency_boost = min(1.5, new_boost + 0.2)
                log(f"[ScoreAdjust] 🚨 No trades in 3h! Emergency boost {new_boost:.2f} → {emergency_boost:.2f}", level="WARNING")
                update_runtime_config({"score_relax_boost": emergency_boost})

        # Восстановление активности
        elif trade_count_1h >= 5 and current_boost > 1.0:
            restored_boost = max(1.0, current_boost - 0.1)
            log(f"[ScoreAdjust] Activity normalized ({trade_count_1h} trades/hour). Reducing boost {current_boost:.2f} → {restored_boost:.2f}")
            update_runtime_config({"score_relax_boost": restored_boost})

    except Exception as e:
        log(f"[ScoreAdjust] Error: {e}", level="ERROR")
