# binance_api.py
from common.config_loader import USE_TESTNET
from core.exchange_init import exchange
from utils_core import safe_call_retry
from utils_logging import log


def convert_symbol(symbol: str) -> str:
    if USE_TESTNET:
        if symbol.endswith("USDC"):
            base = symbol.replace("/USDC", "")
            converted = f"{base}/USDC:USDC"
        elif symbol.endswith("USDT"):
            base = symbol.replace("/USDT", "")
            converted = f"{base}/USDT:USDT"
        else:
            log(f"Invalid symbol format for Testnet: {symbol}", level="ERROR")
            return symbol
        log(f"Converted symbol: {symbol} -> {converted}", level="DEBUG")
        return converted
    return symbol


# Остальные функции без изменений
def fetch_balance():
    return safe_call_retry(
        lambda: exchange.fetch_balance()["total"].get("USDC", 0), label="fetch_balance"
    )


def fetch_ticker(symbol):
    symbol = convert_symbol(symbol)
    return safe_call_retry(lambda: exchange.fetch_ticker(symbol), label=f"fetch_ticker {symbol}")


def fetch_ohlcv(symbol, timeframe="1m", limit=100):
    symbol = convert_symbol(symbol)
    return safe_call_retry(
        lambda: exchange.fetch_ohlcv(symbol, timeframe, limit=limit), label=f"fetch_ohlcv {symbol}"
    )


def create_market_order(symbol, side, amount):
    symbol = convert_symbol(symbol)
    return safe_call_retry(
        lambda: exchange.create_market_buy_order(symbol, amount)
        if side == "buy"
        else exchange.create_market_sell_order(symbol, amount),
        label=f"create_market_order {symbol} {side}",
    )


def cancel_order(order_id, symbol):
    symbol = convert_symbol(symbol)
    return safe_call_retry(
        lambda: exchange.cancel_order(order_id, symbol), label=f"cancel_order {symbol}"
    )


def fetch_open_orders(symbol):
    symbol = convert_symbol(symbol)
    return safe_call_retry(
        lambda: exchange.fetch_open_orders(symbol), label=f"fetch_open_orders {symbol}"
    )


def fetch_positions():
    return safe_call_retry(lambda: exchange.fetch_positions(), label="fetch_positions")


def load_markets():
    return safe_call_retry(lambda: exchange.load_markets(), label="load_markets")


def get_current_price(symbol):
    ticker = fetch_ticker(symbol)
    return ticker["last"] if ticker else None


def get_symbol_info(symbol):
    markets = load_markets()
    symbol = convert_symbol(symbol)
    return markets.get(symbol) if markets else None


def get_leverage(symbol):
    symbol = convert_symbol(symbol)
    symbol_id = (
        symbol.replace("/", "").replace(":USDC", "") if USE_TESTNET else symbol.replace("/", "")
    )
    info = safe_call_retry(lambda: exchange.fapiPrivate_get_positionrisk(), label="get_leverage")
    for pos in info or []:
        if pos.get("symbol") == symbol_id:
            return float(pos.get("leverage", 0))
    return None
