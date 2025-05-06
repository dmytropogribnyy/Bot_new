# binance_api.py
from common.config_loader import MAKER_FEE_RATE, TAKER_FEE_RATE, USE_TESTNET
from core.exchange_init import exchange
from utils_core import safe_call_retry
from utils_logging import log


def convert_symbol(symbol: str) -> str:
    """
    Преобразует символ в формат, ожидаемый биржей.
    BTC/USDC  → BTCUSDC (в обычном режиме)
    BTC/USDC  → BTC/USDC:USDC (только в тестнете)
    """
    if USE_TESTNET:
        if symbol.endswith("/USDC"):
            base = symbol.replace("/USDC", "")
            return f"{base}/USDC:USDC"
        elif symbol.endswith("/USDT"):
            base = symbol.replace("/USDT", "")
            return f"{base}/USDT:USDT"
    return symbol


def fetch_balance():
    """Получает баланс USDC."""
    return safe_call_retry(lambda: exchange.fetch_balance()["total"].get("USDC", 0), label="fetch_balance")


def fetch_ticker(symbol):
    """Получает текущую цену для символа."""
    api_symbol = convert_symbol(symbol)
    return safe_call_retry(lambda: exchange.fetch_ticker(api_symbol), label=f"fetch_ticker {symbol}")


def fetch_ohlcv(symbol, timeframe="15m", limit=100):
    """Получает OHLCV данные для символа."""
    api_symbol = convert_symbol(symbol)
    return safe_call_retry(lambda: exchange.fetch_ohlcv(api_symbol, timeframe, limit=limit), label=f"fetch_ohlcv {symbol}")


def create_market_order(symbol, side, amount):
    """Создает рыночный ордер."""
    api_symbol = convert_symbol(symbol)
    return safe_call_retry(
        lambda: exchange.create_market_buy_order(api_symbol, amount) if side == "buy" else exchange.create_market_sell_order(api_symbol, amount),
        label=f"create_market_order {symbol} {side}",
    )


def cancel_order(order_id, symbol):
    """Отменяет ордер по ID."""
    api_symbol = convert_symbol(symbol)
    return safe_call_retry(lambda: exchange.cancel_order(order_id, api_symbol), label=f"cancel_order {symbol}")


def fetch_open_orders(symbol):
    """Получает открытые ордера для символа."""
    api_symbol = convert_symbol(symbol)
    return safe_call_retry(lambda: exchange.fetch_open_orders(api_symbol), label=f"fetch_open_orders {symbol}")


def fetch_positions():
    """Получает открытые позиции."""
    return safe_call_retry(lambda: exchange.fetch_positions(), label="fetch_positions")


def load_markets():
    """Загружает данные о рынках."""
    return safe_call_retry(lambda: exchange.load_markets(), label="load_markets")


def get_current_price(symbol):
    """Получает текущую цену символа."""
    ticker = fetch_ticker(symbol)
    return ticker["last"] if ticker else None


def get_symbol_info(symbol):
    """Получает информацию о символе."""
    markets = load_markets()
    api_symbol = convert_symbol(symbol)
    return markets.get(api_symbol) if markets else None


def get_leverage(symbol):
    """Получает текущее плечо для символа."""
    api_symbol = convert_symbol(symbol)
    symbol_id = api_symbol.replace("/", "").replace(":USDC", "") if USE_TESTNET else api_symbol.replace("/", "")

    info = safe_call_retry(lambda: exchange.fapiPrivate_get_positionrisk(), label="get_leverage")
    for pos in info or []:
        if pos.get("symbol") == symbol_id:
            return float(pos.get("leverage", 0))
    return None


def calculate_commission(order_size, price, is_maker=False):
    """
    Calculates commission for a trade.
    """
    if order_size is None or price is None:
        log(f"Cannot calculate commission: order_size={order_size}, price={price}", level="WARNING")
        return 0

    rate = MAKER_FEE_RATE if is_maker else TAKER_FEE_RATE
    return order_size * price * rate


def validate_order_size(symbol, side, amount, price=None):
    """
    Validates if an order meets minimum requirements.
    """
    if amount is None:
        return False, "Amount cannot be None"

    if price is None:
        price = get_current_price(symbol)
        if not price:
            return False, "Could not fetch current price"

    # Get symbol info for limits
    market = get_symbol_info(symbol)
    if not market:
        return False, f"Symbol info not found for {symbol}"

    # Check minimum amount
    min_amount = market.get("limits", {}).get("amount", {}).get("min", 0)
    if amount < min_amount:
        return False, f"Amount {amount} below minimum {min_amount}"

    # Check notional value - with validation
    if amount is not None and price is not None:
        notional = amount * price
        min_notional = market.get("limits", {}).get("cost", {}).get("min", 0)

        # Special handling for small deposits - more detailed error
        if notional < min_notional:
            required_amount = min_notional / price
            return False, f"Order value ${notional:.2f} below minimum ${min_notional:.2f}. Need at least {required_amount:.6f} {symbol.split('/')[0]}."

    return True, ""


def create_safe_market_order(symbol, side, amount):
    """
    Creates a market order with validation for small deposits.
    """
    # Validate order before sending
    is_valid, error = validate_order_size(symbol, side, amount)
    if not is_valid:
        log(f"Order validation failed for {symbol}: {error}", level="ERROR")
        return {"success": False, "error": error}

    # Calculate commission for logging
    price = get_current_price(symbol)
    if price is not None:
        commission = calculate_commission(amount, price, is_maker=False)
        log(f"Estimated commission for {symbol} {side} order: {commission:.6f} USDC", level="INFO")
    else:
        log(f"Cannot calculate commission for {symbol}: price is None", level="WARNING")

    # Execute order
    try:
        result = create_market_order(symbol, side, amount)
        return {"success": True, "result": result}
    except Exception as e:
        error_str = str(e)

        # Enhanced error messages for small deposits
        if "MIN_NOTIONAL" in error_str:
            log(f"Minimum notional error for {symbol}: Order too small", level="ERROR")
            return {"success": False, "error": "Order size too small for exchange minimum requirements"}

        return {"success": False, "error": error_str}


def handle_rate_limits(func):
    """Декоратор для обработки лимитов API с повторными попытками."""

    def wrapper(*args, **kwargs):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_str = str(e).lower()
                if ("rate limit" in error_str or "too many requests" in error_str) and attempt < max_retries - 1:
                    delay = 1 * (2**attempt)  # Экспоненциальная задержка: 1, 2, 4 секунды
                    log(f"Достигнут лимит API, повторная попытка через {delay}с (попытка {attempt+1}/{max_retries})", level="WARNING")
                    import time

                    time.sleep(delay)
                else:
                    raise

    return wrapper
