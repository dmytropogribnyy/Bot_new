import json
from pathlib import Path

# Словарь: путь → содержимое по умолчанию
FILES_AND_DEFAULTS = {
    "data/active_trades.json": "{}",
    "data/hang_trades.json": "{}",
    "data/cached_missed.json": "[]",
    "data/missed_signals.json": "[]",
    "data/missed_opportunities.json": "{}",
    "data/component_tracker_log.json": json.dumps({"symbols": {}, "components": {}, "candlestick_rejections": 0}, indent=2),
    "data/fetch_debug.json": "{}",
    "data/filter_tuning_log.json": "[]",
    "data/entry_log.csv": ("timestamp,symbol,direction,entry_price,notional,type,mode,status,account_balance,commission,expected_profit,priority_pair,account_category,exit_reason\n"),
    "data/tp_sl_debug.csv": "timestamp,symbol,level,qty,price,status,reason\n",
    "data/debug_monitoring_summary.json": "{}",
}


def clear_files():
    print("🔄 Cleaning selected data files before run...\n")
    for path_str, default_content in FILES_AND_DEFAULTS.items():
        path = Path(path_str)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(default_content, encoding="utf-8")
            print(f"✅ Cleared: {path}")
        except Exception as e:
            print(f"❌ Failed to clear {path}: {e}")
    print("\n✅ Cleanup complete.\n")


if __name__ == "__main__":
    clear_files()
