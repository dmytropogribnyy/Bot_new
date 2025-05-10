import json
import os

from utils_core import get_runtime_config
from utils_logging import log

FILTER_ADAPTATION_FILE = "data/filter_adaptation.json"
DEFAULT_RELAX_FACTOR = 0.3


def load_json_file(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        log(f"[FilterAdapt] Failed to load {path}: {e}", level="ERROR")
        return {}


def save_json_file(path, data):
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        log(f"[FilterAdapt] Saved data to {path}", level="DEBUG")
    except Exception as e:
        log(f"[FilterAdapt] Failed to save {path}: {e}", level="ERROR")
        raise


def get_adaptive_relax_factor(symbol):
    try:
        runtime_relax = get_runtime_config().get("relax_factor", DEFAULT_RELAX_FACTOR)

        if not os.path.exists(FILTER_ADAPTATION_FILE):
            log(f"[FilterAdapt] File not found, using runtime relax_factor: {runtime_relax}", level="DEBUG")
            return runtime_relax

        data = load_json_file(FILTER_ADAPTATION_FILE)
        if symbol in data:
            symbol_relax = data[symbol].get("relax_factor", runtime_relax)
            log(f"[FilterAdapt] Using symbol-specific relax_factor for {symbol}: {symbol_relax}", level="DEBUG")
            return symbol_relax

        log(f"[FilterAdapt] No specific config for {symbol}, using runtime: {runtime_relax}", level="DEBUG")
        return runtime_relax

    except Exception as e:
        log(f"[FilterAdapt] Error retrieving relax_factor for {symbol}: {e}", level="ERROR")
        return DEFAULT_RELAX_FACTOR
