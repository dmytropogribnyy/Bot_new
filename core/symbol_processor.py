# symbol_processor.py


def process_symbol(symbol, balance, last_trade_times, lock):
    """
    Обрабатывает один торговый символ:
    - проверяет лимиты и маржу
    - вызывает should_enter_trade(...)
    - рассчитывает TP/SL, qty
    - проверяет минимальную прибыль
    Возвращает словарь с параметрами сделки или None.
    """
    from common.config_loader import MIN_NOTIONAL_OPEN, TAKER_FEE_RATE
    from core.binance_api import convert_symbol
    from core.exchange_init import exchange
    from core.order_utils import calculate_order_quantity
    from core.position_manager import get_max_positions
    from core.risk_utils import get_adaptive_risk_percent
    from core.strategy import should_enter_trade
    from core.tp_utils import calculate_tp_levels, check_min_profit
    from core.trade_engine import get_market_regime, get_position_size, open_positions_lock
    from telegram.telegram_utils import send_telegram_message
    from utils_core import MARGIN_SAFETY_BUFFER, extract_symbol, get_min_net_profit
    from utils_logging import log

    symbol = extract_symbol(symbol)

    try:
        if any(v is None for v in (symbol, balance, last_trade_times, lock)):
            log(f"⚠️ Skipping {symbol} — invalid input parameters", level="ERROR")
            return None

        with open_positions_lock:
            positions = exchange.fetch_positions()
            if sum(float(pos.get("contracts", 0)) > 0 for pos in positions) >= get_max_positions(balance):
                log(f"⏩ Skipping {symbol} — max positions reached", level="DEBUG")
                return None
            if get_position_size(symbol) > 0:
                log(f"⏩ Skipping {symbol} — position already open", level="DEBUG")
                return None

            margin = exchange.fetch_balance()["info"]
            avail_margin = float(margin.get("totalMarginBalance", 0)) - float(margin.get("totalPositionInitialMargin", 0)) - float(margin.get("totalOpenOrderInitialMargin", 0))
            margin_with_buffer = avail_margin * MARGIN_SAFETY_BUFFER
            if margin_with_buffer <= 0:
                log(f"⚠️ Skipping {symbol} — no available margin", level="ERROR")
                send_telegram_message(f"⚠️ No available margin for {symbol}", force=True)
                return None

        result, reasons = should_enter_trade(symbol, last_trade_times, lock)
        if result is None:
            log(f"ℹ️ Signal rejected by should_enter_trade for {symbol} → {reasons}", level="DEBUG")
            return None

        direction, qty, is_reentry, breakdown = result
        if direction not in ("BUY", "SELL") or not qty:
            log(f"❌ No valid signal for {symbol} (direction={direction}, qty={qty})", level="DEBUG")
            return None

        df = exchange.fetch_ohlcv(symbol, timeframe="5m", limit=2)
        if not df or not isinstance(df, list) or len(df) < 2:
            log(f"⚠️ Skipping {symbol} — invalid OHLCV", level="ERROR")
            return None
        entry = float(df[-1][4])
        if entry <= 0:
            log(f"⚠️ Skipping {symbol} — invalid entry price {entry}", level="ERROR")
            return None

        regime = get_market_regime(symbol)
        tp1, tp2, sl_price, share_tp1, share_tp2 = calculate_tp_levels(entry, direction, regime=regime)
        if any(x is None for x in (tp1, sl_price, share_tp1)):
            log(f"⚠️ Skipping {symbol} — invalid TP/SL", level="ERROR")
            return None

        risk_percent = get_adaptive_risk_percent(balance)
        try:
            qty = calculate_order_quantity(entry, sl_price, balance, risk_percent)
            if not qty or qty <= 0:
                log(f"⚠️ Skipping {symbol} — invalid quantity {qty}", level="ERROR")
                return None
        except Exception as e:
            log(f"⚠️ Quantity calc error for {symbol}: {e}", level="ERROR")
            return None

        try:
            api_symbol = convert_symbol(symbol)
            ex_min_amount = exchange.load_markets()[api_symbol]["limits"]["amount"]["min"]
            ex_min_notional = ex_min_amount * entry
        except Exception as e:
            log(f"⚠️ Failed to fetch minNotional for {symbol}: {e}", level="WARNING")
            ex_min_notional = MIN_NOTIONAL_OPEN

        notional = qty * entry
        if notional < ex_min_notional:
            new_qty = ex_min_notional / entry
            if new_qty * entry <= margin_with_buffer:
                log(f"ℹ️ Adjusting qty to meet min_notional → {new_qty:.4f}", level="INFO")
                qty = new_qty
                notional = qty * entry
            else:
                log(f"⚠️ Skipping {symbol} — insufficient margin after notional adjust", level="WARNING")
                return None

        try:
            enough_profit, net_profit_tp1 = check_min_profit(entry, tp1, qty, share_tp1, direction, TAKER_FEE_RATE, get_min_net_profit(balance))
            if not enough_profit:
                log(f"⚠️ Skipping {symbol} — profit ~{net_profit_tp1:.2f} USDC below threshold", level="WARNING")
                return None
            if balance < 300 and net_profit_tp1 < 0.25:
                log(f"⚠️ Skipping {symbol} — micro-balance profit {net_profit_tp1:.2f} too small", level="WARNING")
                return None
        except Exception as e:
            log(f"⚠️ Profit check error for {symbol}: {e}", level="ERROR")
            return None

        log(f"{symbol} => {direction}, qty={qty:.3f}, notional={notional:.2f}, risk={risk_percent*100:.1f}%, expProfit={net_profit_tp1:.2f}", level="INFO")

        return {
            "symbol": symbol,
            "direction": direction,
            "qty": qty,
            "entry": entry,
            "tp1": tp1,
            "tp2": tp2,
            "sl": sl_price,
            "is_reentry": is_reentry,
            "breakdown": breakdown,
        }

    except Exception as e:
        import traceback

        log(f"🔥 Error in process_symbol({symbol}): {e}\n{traceback.format_exc(limit=1)}", level="ERROR")
        send_telegram_message(f"❌ process_symbol error for {symbol}: {e}", force=True)
        return None
