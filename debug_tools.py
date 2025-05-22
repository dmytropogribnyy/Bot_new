import json
import os
from collections import defaultdict
from datetime import datetime

from common.config_loader import DRY_RUN, ENABLE_FULL_DEBUG_MONITORING, get_config
from constants import MISSED_SIGNALS_LOG_FILE
from core.component_tracker import log_component_data
from core.dynamic_filters import get_dynamic_filter_thresholds, should_filter_pair
from core.fail_stats_tracker import get_symbol_risk_factor
from core.missed_signal_logger import log_missed_signal
from core.score_evaluator import calculate_score
from core.strategy import fetch_data
from missed_tracker import flush_best_missed_opportunities
from pair_selector import fetch_all_symbols
from telegram.telegram_utils import register_command, send_telegram_message
from utils_logging import log


def run_full_diagnostic_monitoring():
    log("[Debug] Starting full diagnostic monitoring", level="INFO")
    symbols = fetch_all_symbols()
    summary = {
        "timestamp": datetime.utcnow().isoformat(),
        "total_symbols": len(symbols),
        "passed": 0,
        "filtered": 0,
        "errors": 0,
        "filter_reasons": defaultdict(int),
        "error_symbols": [],
        "passed_symbols": [],
        "near_signals": [],
        "detailed": [],
    }

    for symbol in symbols:
        try:
            df = fetch_data(symbol)
            if df is None or len(df) < 20:
                log(f"[Debug] {symbol} skipped: no data", level="WARNING")
                summary["errors"] += 1
                summary["error_symbols"].append(symbol)
                continue

            price = df["close"].iloc[-1]
            if price is None or price == 0:
                log(f"[Debug] {symbol} skipped: invalid price", level="ERROR")
                summary["errors"] += 1
                summary["error_symbols"].append(symbol)
                continue

            atr = df["atr"].iloc[-1]
            volume = df["volume"].iloc[-1] * price
            atr_percent = atr / price

            thresholds = get_dynamic_filter_thresholds(symbol)
            is_filtered, info = should_filter_pair(symbol, atr_percent, volume, thresholds=thresholds)

            score = 0
            breakdown = {}

            symbol_entry = {
                "symbol": symbol,
                "score": score,
                "breakdown": breakdown,
                "atr_percent": round(atr_percent * 100, 2),
                "volume": round(volume, 2),
                "thresholds": thresholds,
                "filtered": False,
                "reason": None,
            }

            if is_filtered:
                reason = info.get("reason", "unknown")
                log(f"[Debug] {symbol} filtered: {reason}", level="INFO")
                log_missed_signal(symbol, 0, {"atr": atr_percent, "volume": volume}, reason=f"filter_{reason}")
                summary["filtered"] += 1
                summary["filter_reasons"][reason] += 1

                symbol_entry["filtered"] = True
                symbol_entry["reason"] = f"filter_{reason}"
                summary["detailed"].append(symbol_entry)
                continue

            risk, _ = get_symbol_risk_factor(symbol)
            if risk <= 0.5:
                log(f"[Debug] {symbol} blocked by risk_factor={risk}", level="INFO")
                log_missed_signal(symbol, 0, {"risk_factor": risk}, reason="high_risk")
                summary["filtered"] += 1
                summary["filter_reasons"]["high_risk"] += 1

                symbol_entry["filtered"] = True
                symbol_entry["reason"] = "high_risk"
                summary["detailed"].append(symbol_entry)
                continue

            score, breakdown = calculate_score(df, symbol, 0, 0)
            log_component_data(symbol, breakdown)

            symbol_entry["score"] = score
            symbol_entry["breakdown"] = breakdown

            if 1.5 <= score < 2.5:
                summary["near_signals"].append(symbol)

            log(f"[Debug] {symbol} passed. Score={score:.2f}", level="INFO")
            summary["passed"] += 1
            summary["passed_symbols"].append(symbol)
            summary["detailed"].append(symbol_entry)

        except Exception as e:
            log(f"[Debug] Error processing {symbol}: {e}", level="ERROR")
            summary["errors"] += 1
            summary["error_symbols"].append(symbol)

    # === analyze missed_signals.json ===
    missed_file = MISSED_SIGNALS_LOG_FILE
    if os.path.exists(missed_file):
        try:
            with open(missed_file, "r") as f:
                missed_data = json.load(f)
        except Exception:
            log("[Debug] Failed to load missed_signals.json", level="WARNING")
            missed_data = []

        combo_stats = defaultdict(int)
        reasons = defaultdict(int)

        for row in missed_data:
            reasons[row.get("reason", "unknown")] += 1
            breakdown = row.get("breakdown", {})
            keys = tuple(sorted(k for k, v in breakdown.items() if v > 0))
            combo_stats[keys] += 1

        summary["missed_analysis"] = {
            "top_reasons": dict(sorted(reasons.items(), key=lambda x: x[1], reverse=True)[:3]),
            "top_combos": [{"signals": list(combo), "count": count} for combo, count in sorted(combo_stats.items(), key=lambda x: x[1], reverse=True)[:5]],
        }

        log("[Debug] Missed signal analysis complete", level="INFO")

    # === save JSON summary ===
    os.makedirs("data", exist_ok=True)
    path = os.path.join("data", "debug_monitoring_summary.json")
    with open(path, "w") as f:
        json.dump(summary, f, indent=2)
    log(f"[Debug] Summary saved to {path}", level="INFO")

    # === optional extra logic ===
    if not DRY_RUN:
        flush_best_missed_opportunities()

    if get_config("TELEGRAM_TOKEN", "") and get_config("TELEGRAM_CHAT_ID", ""):
        reasons = summary["filter_reasons"]
        top_reasons = sorted(reasons.items(), key=lambda x: x[1], reverse=True)[:3]
        reasons_text = "\n".join(f"• {r}: {c}" for r, c in top_reasons)
        passed_str = ", ".join(summary["passed_symbols"][:20]) + (" ..." if len(summary["passed_symbols"]) > 20 else "")
        near_str = ", ".join(summary["near_signals"][:5]) if summary["near_signals"] else "None"

        msg = (
            f"🔍 *Monitoring Audit Completed*\n"
            f"Total Checked: {summary['total_symbols']}\n"
            f"✅ Passed: {summary['passed']}\n"
            f"❌ Filtered: {summary['filtered']}\n"
            f"⚠️ Errors: {summary['errors']}\n\n"
            f"*Top Filter Reasons:*\n{reasons_text}\n\n"
            f"*Near-Signals (score ≥ 1.5):*\n{near_str}\n\n"
            f"*Sample Passed Symbols:*\n{passed_str}"
        )

        if "missed_analysis" in summary:
            missed_block = ""
            missed_block += "\n\n*Top Missed Reasons:*\n"
            missed_block += "\n".join(f"• {r}: {c}" for r, c in summary["missed_analysis"]["top_reasons"].items())
            missed_block += "\n\n*Common Signal Combos:*\n"
            for combo in summary["missed_analysis"]["top_combos"]:
                missed_block += f"• {', '.join(combo['signals'])}: {combo['count']}\n"
            msg += missed_block

        try:
            send_telegram_message(msg, markdown=True)
        except Exception as e:
            log(f"[Debug] Telegram send error: {e}", level="ERROR")


@register_command("/audit")
def handle_audit_command(update, context):
    send_telegram_message("🔍 Running full monitoring audit...", force=True)
    run_full_diagnostic_monitoring()
    send_telegram_message("✅ Monitoring audit completed", force=True)


if ENABLE_FULL_DEBUG_MONITORING:
    run_full_diagnostic_monitoring()
