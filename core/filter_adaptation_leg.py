import os

from constants import FILTER_ADAPTATION_FILE
from utils_core import get_runtime_config, load_json_file
from utils_logging import log

DEFAULT_RELAX_FACTOR = 0.3


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
