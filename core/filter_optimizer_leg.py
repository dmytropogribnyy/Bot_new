# filter_optimizer.py
import json
from pathlib import Path

from utils_logging import log

DEBUG_SUMMARY_PATH = Path("data/debug_monitoring_summary.json")
RUNTIME_CONFIG_PATH = Path("config/runtime_config.json")

# Можно оставить «дефолтные» ступени для ориентира
DEFAULT_TIERS = [{"atr": 0.006, "volume": 600}, {"atr": 0.005, "volume": 500}, {"atr": 0.004, "volume": 400}, {"atr": 0.003, "volume": 300}]


def load_debug_summary():
    """Загружает итог мониторинга (debug_monitoring_summary.json)."""
    if not DEBUG_SUMMARY_PATH.exists():
        log("[FilterOptimizer] No debug summary file found", level="WARNING")
        return None
    try:
        with DEBUG_SUMMARY_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log(f"[FilterOptimizer] Error loading summary: {e}", level="ERROR")
        return None


def update_runtime_config(new_tiers):
    """Обновляет FILTER_TIERS в runtime_config.json."""
    if not RUNTIME_CONFIG_PATH.exists():
        config = {}
    else:
        with RUNTIME_CONFIG_PATH.open("r", encoding="utf-8") as f:
            config = json.load(f)

    config["FILTER_TIERS"] = new_tiers  # сохраняем новые ступени

    with RUNTIME_CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    log("[FilterOptimizer] Updated FILTER_TIERS in runtime_config.json", level="INFO")


def optimize_filter_tiers():
    """
    Анализирует debug_monitoring_summary.json и адаптирует FILTER_TIERS:
    - Если почти всё отфильтровано (или вообще 0 прошли) → ослабляем.
    - Если почти всё прошло (80%+) → ужесточаем.
    - Иначе оставляем без изменений.
    """
    data = load_debug_summary()
    if not data:
        return

    total = data.get("total_symbols", 0)
    filtered = data.get("filtered", 0)
    passed = data.get("passed", 0)

    if total < 1:
        log("[FilterOptimizer] total_symbols < 1, skipping optimization", level="WARNING")
        return

    ratio_filtered = filtered / total
    ratio_passed = passed / total

    # Если отсеяно слишком много (или вообще 0 прошли) → ослабляем
    if passed == 0 or ratio_filtered > 0.9:
        new_tiers = [{"atr": 0.005, "volume": 500}, {"atr": 0.004, "volume": 400}, {"atr": 0.003, "volume": 300}, {"atr": 0.002, "volume": 200}]
        log(f"[FilterOptimizer] Too many filtered ({filtered}/{total}), relaxing tiers", level="INFO")
        update_runtime_config(new_tiers)

    # Если рынок «слишком активный» (80%+ прошли) → ужесточаем
    elif ratio_passed > 0.8:
        new_tiers = [{"atr": 0.007, "volume": 700}, {"atr": 0.006, "volume": 600}, {"atr": 0.005, "volume": 500}, {"atr": 0.004, "volume": 400}]
        log(f"[FilterOptimizer] Most pairs passed ({passed}/{total}), tightening tiers", level="INFO")
        update_runtime_config(new_tiers)

    else:
        log("[FilterOptimizer] Filter tiers remain unchanged", level="INFO")


if __name__ == "__main__":
    optimize_filter_tiers()
