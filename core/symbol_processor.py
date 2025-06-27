def process_symbol(symbol, balance, last_trade_times, lock):
    """
    Обрабатывает торговый символ:
    - вызывает should_enter_trade(...)
    - проверяет TP/SL, min_profit, min_notional
    - возвращает параметры сделки или None
    """
    import traceback
    from collections import defaultdict

    from common.config_loader import MIN_NOTIONAL_OPEN, TAKER_FEE_RATE
    from core.binance_api import convert_symbol
    from core.exchange_init import exchange
    from core.position_manager import get_max_positions
    from core.strategy import should_enter_trade
    from core.tp_utils import calculate_tp_levels, check_min_profit
    from core.trade_engine import get_market_regime, get_position_size, open_positions_lock
    from telegram.telegram_utils import send_telegram_message
    from utils_core import MARGIN_SAFETY_BUFFER, get_min_net_profit, get_runtime_config, normalize_symbol
    from utils_logging import log

    global symbol_blocked_count
    if "symbol_blocked_count" not in globals():
        symbol_blocked_count = defaultdict(int)

    symbol = normalize_symbol(symbol)

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
        if not direction:
            log(f"❌ No direction returned for {symbol}", level="ERROR")
            return None

        direction = direction.upper()
        try:
            qty = float(qty)
        except Exception:
            log(f"❌ Invalid qty type from should_enter_trade for {symbol}: {qty}", level="ERROR")
            return None

        if direction not in ("BUY", "SELL") or qty <= 0:
            log(f"❌ Invalid signal for {symbol} (direction={direction}, qty={qty})", level="WARNING")
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
        tp1, tp2, sl_price, share_tp1, share_tp2, tp_total_qty = calculate_tp_levels(entry, direction, regime=regime)

        if tp1 is None or tp1 <= 0:
            log(f"⚠️ Skipping {symbol} — tp1={tp1} is invalid", level="WARNING")
            return None
        if any(x is None for x in (sl_price, share_tp1)):
            log(f"⚠️ Skipping {symbol} — invalid TP/SL", level="ERROR")
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
                symbol_blocked_count[symbol] += 1
                if symbol_blocked_count[symbol] >= 3:
                    send_telegram_message(f"⚠️ {symbol} заблокирован 3+ раз подряд (qty_blocked). Удаляется из списка.")
                return None

        symbol_blocked_count[symbol] = 0

        try:
            enough_profit, net_profit_tp1 = check_min_profit(entry, tp1, qty, share_tp1, direction, TAKER_FEE_RATE, get_min_net_profit(balance))
            if not enough_profit:
                log(f"⚠️ Skipping {symbol} — profit ~{net_profit_tp1:.2f} USDC below threshold", level="WARNING")
                return None

            min_profit_required = get_runtime_config().get("min_profit_threshold", 0.06)
            if net_profit_tp1 < min_profit_required:
                log(f"⚠️ Skipping {symbol} — profit {net_profit_tp1:.2f} < min {min_profit_required:.2f}", level="WARNING")
                return None

        except Exception as e:
            log(f"⚠️ Profit check error for {symbol}: {e}", level="ERROR")
            return None

        log(f"[Confirm] {symbol} TP1={tp1:.4f}, TP2={tp2:.4f}, SL={sl_price:.4f} | Notional=${notional:.2f}", level="DEBUG")
        log(f"{symbol} => {direction}, qty={qty:.3f}, notional={notional:.2f}, expProfit={net_profit_tp1:.2f}", level="INFO")
        send_telegram_message(f"🟢 VALID SIGNAL {symbol} {direction} qty={qty:.4f} @ {entry:.4f}")

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
            "signal_score": breakdown.get("signal_score", 0.0),
            "tp_prices": [tp1, tp2, tp2 * 1.5],
            "tp_total_qty": tp_total_qty,  # ✅ Добавлено
        }

    except Exception as e:
        log(f"🔥 Error in process_symbol({symbol}): {e}\n{traceback.format_exc(limit=1)}", level="ERROR")
        send_telegram_message(f"❌ process_symbol error for {symbol}: {e}", force=True)
        return None
