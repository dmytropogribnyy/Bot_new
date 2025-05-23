# symbol_processor.py

from common.config_loader import (
    MARGIN_SAFETY_BUFFER,
    MIN_NOTIONAL_OPEN,
    PRIORITY_SMALL_BALANCE_PAIRS,
    TAKER_FEE_RATE,
)
from core.binance_api import convert_symbol
from core.exchange_init import exchange
from core.order_utils import calculate_order_quantity
from core.score_evaluator import get_required_risk_reward_ratio, get_risk_percent_by_score
from core.strategy import fetch_data_multiframe, should_enter_trade
from core.tp_utils import calculate_tp_levels
from core.trade_engine import (
    get_market_regime,
    get_position_size,
    open_positions_lock,
)
from telegram.telegram_utils import send_telegram_message
from utils_core import (
    calculate_risk_reward_ratio,
    check_min_profit,
    get_max_positions,
    get_min_net_profit,
)
from utils_logging import log


def process_symbol(symbol, balance, last_trade_times, lock):
    """
    Обрабатывает один торговый символ: проверяет лимиты позиций,
    доступную маржу, загружает данные через fetch_data_multiframe,
    и в случае валидного сигнала вызывает should_enter_trade(...).
    Возвращает словарь с планом сделки или None, если вход отменён.
    """

    try:
        # Быстрая проверка входных данных
        if any(v is None for v in (symbol, balance, last_trade_times, lock)):
            log(
                f"⚠️ Skipping {symbol} — invalid input parameters (symbol={symbol}, balance={balance})",
                level="ERROR",
            )
            return None

        # На маленьком депозите (<300 USDC) разрешаем только приоритетные пары
        if balance < 300 and symbol not in PRIORITY_SMALL_BALANCE_PAIRS:
            log(f"⏩ Skipping {symbol} — not a priority pair for small accounts", level="DEBUG")
            return None

        # Блокируем доступ к позициям
        with open_positions_lock:
            positions = exchange.fetch_positions()
            active_positions = sum(1 for pos in positions if float(pos.get("contracts", 0)) != 0)
            max_positions = get_max_positions(balance)

            # Если лимит позиций уже исчерпан — выходим
            if active_positions >= max_positions:
                log(
                    f"⏩ Skipping {symbol} — max open positions ({max_positions}) reached " f"(current: {active_positions})",
                    level="DEBUG",
                )
                return None

            # Если по символу уже есть открытая позиция — пропускаем
            if get_position_size(symbol) > 0:
                log(f"⏩ Skipping {symbol} — already have a position", level="DEBUG")
                return None

            # Проверка доступной маржи (с учётом буфера)
            balance_info = exchange.fetch_balance()
            margin_info = balance_info["info"]
            total_margin_balance = float(margin_info.get("totalMarginBalance", 0))
            pos_margin = float(margin_info.get("totalPositionInitialMargin", 0))
            order_margin = float(margin_info.get("totalOpenOrderInitialMargin", 0))
            available_margin = total_margin_balance - pos_margin - order_margin
            margin_with_buffer = available_margin * MARGIN_SAFETY_BUFFER

            if margin_with_buffer <= 0:
                log(
                    f"⚠️ Skipping {symbol} — no available margin " f"(total: {total_margin_balance:.2f}, positions: {pos_margin:.2f}, orders: {order_margin:.2f})",
                    level="ERROR",
                )
                send_telegram_message(f"⚠️ No available margin for {symbol}", force=True)
                return None

        # === Загружаем данные мультифреймом ===
        df = fetch_data_multiframe(symbol)
        if df is None:
            log(f"⚠️ Skipping {symbol} — fetch_data_multiframe returned None", level="WARNING")
            send_telegram_message(f"⚠️ Failed to fetch data for {symbol}", force=True)
            return None

        # === Пытаемся получить сигнал
        result = should_enter_trade(symbol, df, exchange, last_trade_times, lock)
        if not result:
            log(f"❌ No valid signal for {symbol}", level="DEBUG")
            return None

        # result обычно (direction, score, is_reentry), либо None
        direction, score, is_reentry = result

        if direction not in ("buy", "sell"):
            log(f"⚠️ Skipping {symbol} — invalid direction: {direction}", level="ERROR")
            return None

        # Пробуем взять текущую цену входа
        try:
            entry = float(df["close"].iloc[-1])
            if entry <= 0:
                log(f"⚠️ Skipping {symbol} — invalid entry price {entry:.4f}", level="ERROR")
                return None
        except (IndexError, ValueError, TypeError) as e:
            log(f"⚠️ Skipping {symbol} — error reading entry price: {e}", level="ERROR")
            return None

        # Определяем рыночный режим (trend, flat, breakout...)
        regime = get_market_regime(symbol)

        # Считаем TP/SL
        try:
            tp1, tp2, sl_price, share_tp1, share_tp2 = calculate_tp_levels(entry, direction, regime, score, df)
            if any(x is None for x in (tp1, sl_price, share_tp1)):
                log(
                    f"⚠️ Skipping {symbol} — invalid TP/SL (tp1={tp1}, sl={sl_price}, share_tp1={share_tp1})",
                    level="ERROR",
                )
                return None
            log(
                f"DEBUG: {symbol} => TP1={tp1:.4f}, TP2={tp2}, SL={sl_price:.4f}, " f"TP1share={share_tp1}, TP2share={share_tp2}",
                level="DEBUG",
            )
        except Exception as e:
            log(f"⚠️ Skipping {symbol} — error in calculate_tp_levels: {e}", level="ERROR")
            return None

        # Адаптивный риск по score
        risk_percent = get_risk_percent_by_score(balance, score)
        # Рассчитываем qty
        try:
            qty = calculate_order_quantity(entry, sl_price, balance, risk_percent)
            if not qty or qty <= 0:
                log(f"⚠️ Skipping {symbol} — invalid quantity: {qty}", level="ERROR")
                return None
        except Exception as e:
            log(f"⚠️ Skipping {symbol} — error calculating quantity: {e}", level="ERROR")
            return None

        # Проверка Risk/Reward
        try:
            needed_rr = get_required_risk_reward_ratio(score)
            actual_rr = calculate_risk_reward_ratio(entry, tp1, sl_price, direction)

            # Для маленьких депо + сильных сигналов снижаем R/R
            if balance < 300 and score >= 4.0:
                needed_rr *= 0.9
                log(f"📊 Lowering R/R => {needed_rr:.2f}", level="DEBUG")

            if actual_rr < needed_rr:
                log(
                    f"⚠️ Skipping {symbol} => R/R={actual_rr:.2f} < needed {needed_rr:.2f}",
                    level="WARNING",
                )
                return None
        except Exception as e:
            log(f"⚠️ Error evaluating R/R for {symbol}: {e}", level="ERROR")
            return None

        # Смотрим минимальный торговый лот биржи
        try:
            api_symbol = convert_symbol(symbol)
            markets = exchange.load_markets()
            if api_symbol in markets and "limits" in markets[api_symbol] and "amount" in markets[api_symbol]["limits"] and "min" in markets[api_symbol]["limits"]["amount"]:
                ex_min_amount = markets[api_symbol]["limits"]["amount"]["min"]
                ex_min_notional = ex_min_amount * entry
            else:
                ex_min_notional = MIN_NOTIONAL_OPEN
        except Exception as e:
            log(f"⚠️ Using fallback MIN_NOTIONAL_OPEN for {symbol}, error: {e}", level="WARNING")
            ex_min_notional = MIN_NOTIONAL_OPEN

        # Проверяем/докручиваем notional
        notional = qty * entry
        if notional < ex_min_notional:
            new_qty = ex_min_notional / entry
            # Проверим буфер маржи
            new_notional = new_qty * entry
            if new_notional <= margin_with_buffer:
                log(
                    f"ℹ️ Adjusting qty for {symbol} from {qty:.4f} to {new_qty:.4f} to meet min_notional {ex_min_notional:.2f}",
                    level="INFO",
                )
                qty = new_qty
                notional = new_notional
            else:
                log(f"⚠️ Still insufficient margin after adjusting notional for {symbol}", level="WARNING")
                return None

        # Короткая проверка прибыли
        try:
            enough_profit, expected_profit_tp1 = check_min_profit(entry, tp1, qty, share_tp1, direction, TAKER_FEE_RATE, get_min_net_profit(balance))
            if not enough_profit:
                log(
                    f"⚠️ Skipping {symbol} => expected profit ~ {expected_profit_tp1:.2f} USDC below threshold",
                    level="WARNING",
                )
                return None

            if balance < 300 and expected_profit_tp1 < 0.25:
                log(f"⚠️ Skipping {symbol} => expected profit {expected_profit_tp1:.2f} too small", level="WARNING")
                return None
        except Exception as e:
            log(f"⚠️ Profit check error for {symbol}: {e}", level="ERROR")
            return None

        log(
            f"{symbol} => direction={direction}, qty={qty:.4f}, notional={notional:.2f}, " f"score={score:.2f}, expProfit={expected_profit_tp1:.2f} USDC",
            level="INFO" if balance < 300 else "DEBUG",
        )

        # Приоритетная пара + маленький депозит => Telegram
        if balance < 300 and symbol in PRIORITY_SMALL_BALANCE_PAIRS:
            send_telegram_message(
                f"✅ [Small Account] Valid trade for {symbol}\nScore={score:.2f}, Profit≈{expected_profit_tp1:.2f}",
                force=True,
            )

        # Возвращаем готовый план сделки
        return {
            "symbol": symbol,
            "direction": direction,
            "qty": qty,
            "entry": entry,
            "tp1": tp1,
            "tp2": tp2,
            "sl": sl_price,
            "score": score,
            "is_reentry": is_reentry,
        }

    except Exception as e:
        log(f"🔥 Error in process_symbol({symbol}): {e}", level="ERROR")
        send_telegram_message(f"❌ process_symbol error for {symbol}: {e}", force=True)
        return None
