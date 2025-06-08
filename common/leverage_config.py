# common/leverage_config.py
from common.config_loader import SYMBOLS_ACTIVE
from utils_core import safe_call_retry
from utils_logging import log


def set_leverage_for_symbols():
    """Устанавливает плечо для активных символов."""
    from core.exchange_init import exchange

    for symbol in SYMBOLS_ACTIVE:
        leverage = LEVERAGE_MAP.get(symbol, 5)
        safe_call_retry(exchange.set_leverage, leverage, symbol, tries=3, delay=1, label=f"set_leverage {symbol}")
    log("Leverage set for all symbols", level="INFO")


LEVERAGE_MAP = {
    "BTCUSDT": 5,
    "ETHUSDT": 5,
    "BTCUSDC": 5,
    "ETHUSDC": 5,
    "DOGEUSDC": 12,
    "XRPUSDC": 12,
    "ADAUSDC": 10,
    "SOLUSDC": 6,
    "BNBUSDC": 5,
    "LINKUSDC": 8,
    "ARBUSDC": 6,
    "SUIUSDC": 6,
    "MATICUSDC": 10,
    "DOTUSDC": 8,
}
