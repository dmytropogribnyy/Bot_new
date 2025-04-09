from core.exchange_init import exchange
from utils_core import safe_call_retry


def fetch_balance():
    return safe_call_retry(
        lambda: exchange.fetch_balance()["total"].get("USDC", 0), label="fetch_balance"
    )


def fetch_ticker(symbol):
    return safe_call_retry(lambda: exchange.fetch_ticker(symbol), label=f"fetch_ticker {symbol}")


def fetch_ohlcv(symbol, timeframe="1m", limit=100):
    return safe_call_retry(
        lambda: exchange.fetch_ohlcv(symbol, timeframe, limit=limit), label=f"fetch_ohlcv {symbol}"
    )


def create_market_order(symbol, side, amount):
    return safe_call_retry(
        lambda: exchange.create_market_buy_order(symbol, amount)
        if side == "buy"
        else exchange.create_market_sell_order(symbol, amount),
        label=f"create_market_order {symbol} {side}",
    )


def cancel_order(order_id, symbol):
    return safe_call_retry(
        lambda: exchange.cancel_order(order_id, symbol), label=f"cancel_order {symbol}"
    )


def fetch_open_orders(symbol):
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
    return markets.get(symbol) if markets else None


def get_leverage(symbol):
    info = safe_call_retry(lambda: exchange.fapiPrivate_get_positionrisk(), label="get_leverage")
    symbol_id = symbol.replace("/", "")
    for pos in info or []:
        if pos.get("symbol") == symbol_id:
            return float(pos.get("leverage", 0))
    return None
