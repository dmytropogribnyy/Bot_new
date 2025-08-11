# binance_api.py
import time

from common.config_loader import MAKER_FEE_RATE, TAKER_FEE_RATE, USE_TESTNET

from core.legacy.exchange_init import exchange
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
    if not isinstance(result, int | float):
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
    result = safe_call_retry(
        lambda: exchange.fetch_ohlcv(api_symbol, timeframe, limit=limit), label=f"fetch_ohlcv {symbol}"
    )
    # Если результат не список — значит ошибка (мы ждём list of candles)
    if not isinstance(result, list):
        log(f"[fetch_ohlcv] Invalid result for {symbol}: {type(result)}", level="ERROR")
        return None
    return result


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
        return False, (
            f"Order value ${notional:.2f} below minimum ${min_notional:.2f}. "
            f"Need at least {required_amount:.6f} {symbol.split('/')[0]}."
        )

    # ✅ Успешная валидация — логируем для отладки
    log(
        f"[validate_order_size] ✅ {symbol} {side}: amount={amount}, price={price}, "
        f"notional={notional:.4f}, min_amount={min_amount}, min_notional={min_notional}",
        level="DEBUG",
    )

    return True, ""


def create_safe_market_order(symbol, side, amount):
    """
    Создает безопасный market-ордер с логами и fallback на лимитный ордер при отказе.
    Возвращает:
        {
            "success": True/False,
            "result": raw Binance object,
            "filled_qty": float,
            "avg_price": float,
            "status": "market_success" | "post_fetch_success" | "submitted_fallback_limit"
        }
    """
    import time

    from core.legacy.binance_api import (
        calculate_commission,
        convert_symbol,
        get_current_price,
        round_step_size,  # ✅ добавлен
        validate_order_size,
    )
    from core.legacy.exchange_init import exchange
    from telegram.telegram_utils import send_telegram_message
    from utils_core import normalize_symbol
    from utils_logging import log

    symbol = normalize_symbol(symbol)
    api_symbol = convert_symbol(symbol)

    if not amount or amount <= 0:
        log(f"[MarketOrder] ❌ Skipped: qty is zero or negative for {symbol} → qty={amount}", level="ERROR")
        send_telegram_message(
            f"❌ *Order Failed:* `{symbol}`\nReason: `qty_zero_or_invalid`\nQty: `{amount}`", force=True
        )
        return {"success": False, "error": "qty_zero_or_invalid"}

    if not exchange.markets or api_symbol not in exchange.markets:
        try:
            exchange.load_markets()
            log(f"[MarketOrder] Reloaded markets for {api_symbol}", level="DEBUG")
        except Exception as e:
            log(f"[MarketOrder] Failed to reload markets: {e}", level="ERROR")

    market_info = exchange.markets.get(api_symbol, {})
    limits = market_info.get("limits", {}).get("amount", {})
    cost_limits = market_info.get("limits", {}).get("cost", {})
    precision = market_info.get("precision", {}).get("amount", "N/A")

    price = get_current_price(symbol)
    notional = round((amount * price), 4) if price else 0

    # ✅ округляем количество через round_step_size
    amount = round_step_size(symbol, amount)

    log(
        f"[MarketOrder] DEBUG {symbol} | qty={amount}, step={precision}, min_qty={limits.get('min')}, min_notional={cost_limits.get('min')}",
        level="DEBUG",
    )

    is_valid, error = validate_order_size(symbol, side, amount)

    if not is_valid:
        error = error or "validation_failed"
        log(f"[MarketOrder] ❌ Validation failed: {error} | notional={notional}", level="ERROR")
        send_telegram_message(f"❌ *Order Failed:* `{symbol}`\nReason: `{error}`\nQty: `{amount}`", force=True)
        return {"success": False, "error": error}

    fee = calculate_commission(amount, price, is_maker=False) if price else 0.0
    log(f"[MarketOrder] ✅ Validation passed → notional={notional}, fee={fee:.6f}", level="DEBUG")

    try:
        params = {"newOrderRespType": "RESULT"}
        order = (
            exchange.create_market_buy_order(api_symbol, amount, params=params)
            if side == "buy"
            else exchange.create_market_sell_order(api_symbol, amount, params=params)
        )
        log(f"[BINANCE] Market response: {order}", level="DEBUG")

        order_id = order.get("id")
        filled_qty = float(order.get("filled", 0) or 0)
        avg_price = float(order.get("average", 0) or 0)

        if filled_qty > 0 and avg_price > 0:
            return {
                "success": True,
                "result": order,
                "filled_qty": filled_qty,
                "avg_price": avg_price,
                "status": "market_success",
            }

        # retry через fetch_order
        if order_id:
            time.sleep(2.0)
            try:
                post_order = exchange.fetch_order(order_id, api_symbol)
                filled_qty = float(post_order.get("filled", 0) or 0)
                avg_price = float(post_order.get("average", 0) or 0)
                if filled_qty > 0:
                    return {
                        "success": True,
                        "result": post_order,
                        "filled_qty": filled_qty,
                        "avg_price": avg_price,
                        "status": "post_fetch_success",
                    }
            except Exception as e:
                log(f"[MarketOrder] ⚠️ Post-fetch failed for {symbol}: {e}", level="WARNING")

        # fallback на лимитный
        limit_price = round(price * (1.0005 if side == "buy" else 0.9995), 6)
        try:
            fallback = exchange.create_order(
                api_symbol,
                type="limit",
                side=side,
                amount=amount,
                price=limit_price,
                params={"postOnly": True},
            )
            send_telegram_message(
                f"📥 *Fallback Limit Order Placed*\n{symbol} → `{side.upper()}`\nQty: `{amount}` @ `{limit_price}`",
                force=True,
            )
            return {
                "success": True,
                "result": fallback,
                "filled_qty": 0.0,
                "avg_price": limit_price,
                "status": "submitted_fallback_limit",
            }
        except Exception as fb_err:
            log(f"[Fallback] ❌ Fallback limit order failed for {symbol}: {fb_err}", level="ERROR")
            send_telegram_message(f"❌ Fallback failed for `{symbol}` → {fb_err}", force=True)
            return {"success": False, "error": str(fb_err)}

    except Exception as e:
        log(f"[MarketOrder] ❌ Unexpected error: {e}", level="ERROR")
        send_telegram_message(f"❌ *Order Failed:* `{symbol}`\nReason: `{e}`", force=True)
        return {"success": False, "error": str(e)}


def get_open_positions():
    """
    Возвращает список только активных позиций (с ненулевым объёмом positionAmt).
    """
    from utils_logging import log

    try:
        positions = fetch_positions()
        if not isinstance(positions, list):
            log(f"[get_open_positions] Invalid result: {type(positions)}", level="ERROR")
            return []
        active = [p for p in positions if float(p.get("positionAmt", 0)) != 0]
        log(f"[get_open_positions] Found {len(active)} active positions", level="DEBUG")
        return active
    except Exception as e:
        log(f"[get_open_positions] Error: {e}", level="ERROR")
        return []


def get_open_positions_count():
    """
    Возвращает количество активных позиций (где positionAmt ≠ 0).
    """
    from core.legacy.exchange_init import exchange
    from core.legacy.risk_utils import get_max_positions
    from utils_core import safe_call_retry
    from utils_logging import log

    try:
        positions = safe_call_retry(exchange.fetch_positions)
        open_positions = [p for p in positions if float(p.get("positionAmt", 0)) != 0]
        return len(open_positions)
    except Exception as e:
        log(f"[get_open_positions_count] Error: {e}", level="ERROR")
        return get_max_positions()  # fail-safe fallback


def get_ticker_data(symbol):
    """
    Get ticker data for a symbol. Wrapper around fetch_ticker for compatibility.
    """
    return fetch_ticker(symbol)


def round_step_size(symbol, qty):
    """
    Округляет qty согласно step_size, защищён от decimal/float ошибок
    """
    from utils_core import safe_float_conversion
    from utils_logging import log

    try:
        qty_f = safe_float_conversion(qty)
        rounded = exchange.amount_to_precision(symbol, qty_f)

        if isinstance(rounded, str):
            rounded = rounded.strip().replace(",", "")
            return float(rounded)
        elif hasattr(rounded, "__float__"):
            return float(rounded)
        else:
            return float(str(rounded))

    except Exception as e:
        log(f"[step_size] Decimal error for {symbol}, qty={qty}: {e}", level="ERROR")
        # fallback: округление вручную по 0.001
        step_size = 0.001
        fallback_qty = qty_f - (qty_f % step_size)
        return round(fallback_qty, 6)


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
                    delay = 1 * (2**attempt)  # 1, 2, 4 сек
                    log(
                        f"⏳ Rate limit hit, retrying in {delay}s (attempt {attempt + 1}/{max_retries})",
                        level="WARNING",
                    )
                    time.sleep(delay)
                else:
                    log(f"[RateLimit] ❌ Failed after {attempt + 1} attempts: {e}", level="ERROR")
                    raise

    return wrapper
