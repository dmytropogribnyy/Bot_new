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
    """Получает открытые позиции через Binance Futures endpoint напрямую."""
    try:
        result = safe_call_retry(lambda: exchange.fapiPrivate_get_positionrisk(), label="fetch_positions")
        if not isinstance(result, list):
            log(f"[fetch_positions] Invalid result: {type(result)}", level="ERROR")
            return []
        return result
    except Exception as e:
        log(f"[fetch_positions] Error via fapiPrivate_get_positionrisk: {e}", level="ERROR")
        return []


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

    market = get_symbol_info(symbol)
    if not market:
        return False, f"Symbol info not found for {symbol}"

    min_amount = market.get("limits", {}).get("amount", {}).get("min", 0)
    if amount < min_amount:
        return False, f"Amount {amount} below minimum {min_amount}"

    notional = amount * price
    min_notional = market.get("limits", {}).get("cost", {}).get("min", 0)
    if notional < min_notional:
        required_amount = min_notional / price
        return False, (f"Order value ${notional:.2f} below minimum ${min_notional:.2f}. " f"Need at least {required_amount:.6f} {symbol.split('/')[0]}.")

    # ✅ Успешная валидация — логируем для отладки
    log(f"[validate_order_size] ✅ {symbol} {side}: amount={amount}, price={price}, " f"notional={notional:.4f}, min_amount={min_amount}, min_notional={min_notional}", level="DEBUG")

    return True, ""


def create_safe_market_order(symbol, side, amount):
    """
    Creates a market order with validation for small deposits,
    always returning a standardized dict:
      {
        "success": True,
        "result": ...,          # raw order response
        "filled_qty": ...,      # float, parsed from executedQty
        "avg_price": ...,       # float, parsed from avgPrice
        "status": ...,          # e.g., 'filled', 'partially_filled'
      }
      {"success": False, "error": ...}
    """
    import time

    from common.config_loader import DRY_RUN
    from core.binance_api import calculate_commission, create_market_order, get_current_price, validate_order_size
    from core.exchange_init import exchange
    from utils_core import normalize_symbol
    from utils_logging import log

    symbol = normalize_symbol(symbol)

    # 🔍 Лог лимитов биржи перед ордером
    try:
        market = exchange.markets[symbol]
        limits = market.get("limits", {}).get("amount", {})
        min_qty = limits.get("min")
        step_size = market.get("precision", {}).get("amount")
        log(f"[MarketOrder] Limits for {symbol}: min_qty={min_qty}, step_size={step_size}", level="DEBUG")

        margin_info = exchange.fetch_balance()["info"]
        avail_margin = float(margin_info.get("totalMarginBalance", 0)) - float(margin_info.get("totalPositionInitialMargin", 0)) - float(margin_info.get("totalOpenOrderInitialMargin", 0))
        log(f"[MarketOrder] Available margin: {avail_margin:.4f}", level="DEBUG")
    except Exception as e:
        log(f"[MarketOrder] ⚠️ Could not fetch margin/limits for {symbol}: {e}", level="WARNING")

    # 1) Валидация
    is_valid, error = validate_order_size(symbol, side, amount)
    if not is_valid:
        price = get_current_price(symbol)
        log(f"[MarketOrder] ❌ Validation failed for {symbol}: {error} (qty={amount}, price={price})", level="ERROR")
        return {"success": False, "error": error}
    else:
        price = get_current_price(symbol)
        notional = amount * price if price else 0
        log(f"[MarketOrder] {symbol} validation ok: amount={amount}, price={price}, notional={notional}", level="DEBUG")

    # 2) Комиссия
    if price:
        commission = calculate_commission(amount, price, is_maker=False)
        log(f"[MarketOrder] {symbol} {side} qty={amount:.4f} — estimated fee ≈ {commission:.6f} USDC", level="DEBUG")

    # 3) Исполнение
    try:
        result = create_market_order(symbol, side, amount)
        log(f"[MarketOrder] Binance raw result: {result}", level="DEBUG")

        if not isinstance(result, dict):
            msg = f"[MarketOrder] ❌ Unexpected result type: {type(result)} for {symbol}"
            log(msg, level="ERROR")
            return {"success": False, "error": msg}

        filled_qty = float(result.get("executedQty", 0))
        avg_price = float(result.get("avgPrice", 0))
        status = result.get("status", "unknown")

        # 🟡 Fallback: если 0 filled — повтор
        if filled_qty == 0 and not DRY_RUN:
            log(f"[MarketOrder] ⚠️ 0 filled — retrying after 1.5s for {symbol}", level="WARNING")
            time.sleep(1.5)
            result_retry = create_market_order(symbol, side, amount)
            log(f"[MarketOrder] Retry result: {result_retry}", level="DEBUG")

            if isinstance(result_retry, dict):
                filled_qty = float(result_retry.get("executedQty", 0))
                avg_price = float(result_retry.get("avgPrice", 0))
                status = result_retry.get("status", "unknown")
                result = result_retry

        # ❗ Финальная защита от "пустых" ордеров
        if filled_qty == 0 or avg_price == 0:
            log(f"[MarketOrder] ❌ Zero filled_qty or avg_price for {symbol} — treating as failure", level="ERROR")
            return {"success": False, "error": "No volume filled (0 qty or 0 price)"}

        # ✅ Успешно
        log(f"[MarketOrder] ✅ {symbol} {side} — filled={filled_qty}, avg_price={avg_price}, status={status}", level="INFO")

        return {
            "success": True,
            "result": result,
            "filled_qty": filled_qty,
            "avg_price": avg_price,
            "status": status,
        }

    except Exception as e:
        error_str = str(e)
        if "MIN_NOTIONAL" in error_str or "minNotional" in error_str:
            log(f"[MarketOrder] ❌ Notional too low for {symbol}: {error_str}", level="ERROR")
            return {"success": False, "error": "Order size too small for exchange minimum"}
        if "insufficient" in error_str.lower() or "margin" in error_str.lower():
            log(f"[MarketOrder] ❌ Margin error for {symbol}: {error_str}", level="ERROR")
            return {"success": False, "error": "Margin is insufficient"}

        log(f"[MarketOrder] ❌ Exception during order for {symbol}: {error_str}", level="ERROR")
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

        open_positions = []
        for pos in positions:
            size = pos.get("contracts") or pos.get("positionAmt") or pos.get("amount") or 0
            try:
                size = float(size)
            except (TypeError, ValueError):
                size = 0
            if size != 0:
                open_positions.append(pos)

        log(f"[get_open_positions] Found {len(open_positions)} open positions", level="DEBUG")
        return open_positions

    except Exception as e:
        log(f"[get_open_positions] Error: {e}", level="ERROR")
        return []


def get_ticker_data(symbol):
    """
    Get ticker data for a symbol. Wrapper around fetch_ticker for compatibility.
    """
    return fetch_ticker(symbol)


def round_step_size(symbol, qty):
    """
    Округляет qty до допустимого step_size символа Binance.
    """
    market = get_symbol_info(symbol)
    step_size = market.get("precision", {}).get("amount", 0.001)

    if not step_size or step_size <= 0:
        step_size = 0.001  # fallback

    rounded_qty = qty - (qty % step_size)
    return round(rounded_qty, 8)


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
