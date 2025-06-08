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
    result = safe_call_retry(lambda: exchange.fetch_balance()["total"].get("USDC", 0), label="fetch_balance")
    if not isinstance(result, (int, float)):
        # Если вдруг пришёл None или что-то нечисловое, возвращаем 0 (или логируем)
        log(f"[fetch_balance] Invalid result: {result}", level="ERROR")
        return 0
    return result


def fetch_ticker(symbol):
    """Получает текущую цену для символа."""
    api_symbol = convert_symbol(symbol)
    result = safe_call_retry(lambda: exchange.fetch_ticker(api_symbol), label=f"fetch_ticker {symbol}")
    if not isinstance(result, dict):
        log(f"[fetch_ticker] Invalid result for {symbol}: {type(result)}", level="ERROR")
        return None
    return result


def fetch_ohlcv(symbol, timeframe="15m", limit=100):
    """Получает OHLCV данные для символа."""
    api_symbol = convert_symbol(symbol)
    result = safe_call_retry(lambda: exchange.fetch_ohlcv(api_symbol, timeframe, limit=limit), label=f"fetch_ohlcv {symbol}")
    # Если результат не список — значит ошибка (мы ждём list of candles)
    if not isinstance(result, list):
        log(f"[fetch_ohlcv] Invalid result for {symbol}: {type(result)}", level="ERROR")
        return None
    return result


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
    result = safe_call_retry(lambda: exchange.fetch_open_orders(api_symbol), label=f"fetch_open_orders {symbol}")
    if not isinstance(result, list):
        log(f"[fetch_open_orders] Invalid result for {symbol}: {type(result)}", level="ERROR")
        return []
    return result


def fetch_positions():
    """Получает открытые позиции."""
    result = safe_call_retry(lambda: exchange.fetch_positions(), label="fetch_positions")
    if not isinstance(result, list):
        log(f"[fetch_positions] Invalid result: {type(result)}", level="ERROR")
        return []
    return result


def load_markets():
    """Загружает данные о рынках."""
    result = safe_call_retry(lambda: exchange.load_markets(), label="load_markets")
    if not isinstance(result, dict):
        log(f"[load_markets] Invalid result: {type(result)}", level="ERROR")
        return {}
    return result


def get_current_price(symbol):
    """Получает текущую цену символа."""
    from utils_core import extract_symbol

    symbol = extract_symbol(symbol)
    ticker = fetch_ticker(symbol)
    return ticker["last"] if ticker and "last" in ticker else None


def get_symbol_info(symbol):
    """Получает информацию о символе."""
    markets = load_markets()
    api_symbol = convert_symbol(symbol)
    return markets.get(api_symbol) if markets else None


def get_leverage(symbol):
    """Получает текущее плечо для символа."""
    from utils_core import extract_symbol

    symbol = extract_symbol(symbol)
    api_symbol = convert_symbol(symbol)
    symbol_id = api_symbol.replace("/", "").replace(":USDC", "") if USE_TESTNET else api_symbol.replace("/", "")

    info = safe_call_retry(lambda: exchange.fapiPrivate_get_positionrisk(), label="get_leverage")
    if not isinstance(info, list):
        log("[get_leverage] Invalid result from positionrisk call", level="ERROR")
        return None

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
    from utils_core import extract_symbol

    symbol = extract_symbol(symbol)
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
    notional = amount * price
    min_notional = market.get("limits", {}).get("cost", {}).get("min", 0)
    if notional < min_notional:
        required_amount = min_notional / price
        return False, (f"Order value ${notional:.2f} below minimum ${min_notional:.2f}. " f"Need at least {required_amount:.6f} {symbol.split('/')[0]}.")

    return True, ""


def create_safe_market_order(symbol, side, amount):
    """
    Creates a market order with validation for small deposits,
    always returning a standardized dict:
      {"success": True, "result": ...}
      {"success": False, "error": ...}
    """
    from utils_core import extract_symbol

    symbol = extract_symbol(symbol)

    # 1) Валидация ордера
    is_valid, error = validate_order_size(symbol, side, amount)
    if not is_valid:
        log(f"[create_safe_market_order] Validation failed: {error}", level="ERROR")
        return {"success": False, "error": error}

    # 2) Рассчитываем комиссию для лога (не обязательно)
    price = get_current_price(symbol)
    if price is not None:
        commission = calculate_commission(amount, price, is_maker=False)
        log(f"{symbol} {side} order — estimated commission: {commission:.6f} USDC", level="DEBUG")

    # 3) Вызываем create_market_order(...) внутри safe_call_retry
    try:
        result = create_market_order(symbol, side, amount)
        if isinstance(result, dict):
            return {"success": True, "result": result}
        else:
            log(f"[create_safe_market_order] Unexpected result type: {type(result)}", level="ERROR")
            return {"success": False, "error": "Unexpected result type from create_market_order"}
    except Exception as e:
        error_str = str(e)
        if "MIN_NOTIONAL" in error_str:
            log(f"Minimum notional error for {symbol}: {error_str}", level="ERROR")
            return {"success": False, "error": "Order size too small for exchange minimum requirements"}

        log(f"[create_safe_market_order] Exception: {error_str}", level="ERROR")
        return {"success": False, "error": error_str}


def get_open_positions():
    """
    Gets actually open positions with non-zero contracts from the exchange.
    Returns a list of position objects with non-zero size.
    """
    try:
        positions = exchange.fetch_positions()
        if not isinstance(positions, list):
            log("[get_open_positions] Invalid fetch_positions result", level="ERROR")
            return []
        return [pos for pos in positions if float(pos.get("contracts", 0)) != 0]
    except Exception as e:
        log(f"Error fetching open positions: {e}", level="ERROR")
        return []


def get_ticker_data(symbol):
    """
    Get ticker data for a symbol. Wrapper around fetch_ticker for compatibility.
    """
    return fetch_ticker(symbol)


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
