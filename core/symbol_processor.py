from symbol_priority_manager import determine_strategy_mode

from common.config_loader import (
    LEVERAGE_MAP,
    MARGIN_SAFETY_BUFFER,
    MIN_NOTIONAL_OPEN,
    PRIORITY_SMALL_BALANCE_PAIRS,
    TAKER_FEE_RATE,
)
from core.binance_api import convert_symbol  # Added import for symbol conversion
from core.exchange_init import exchange
from core.order_utils import calculate_order_quantity
from core.score_evaluator import get_required_risk_reward_ratio, get_risk_percent_by_score
from core.strategy import fetch_data, fetch_data_multiframe, fetch_data_optimized, should_enter_trade
from core.tp_utils import calculate_tp_levels
from core.trade_engine import (
    get_market_regime,
    get_position_size,
    open_positions_lock,
)
from telegram.telegram_utils import send_telegram_message
from utils_core import calculate_risk_reward_ratio, check_min_profit, get_max_positions, get_min_net_profit, get_runtime_config
from utils_logging import log


def process_symbol(symbol, balance, last_trade_times, lock):
    """
    Process trading symbol with comprehensive validation for small deposit trading.
    Enhanced error handling and optimization for small accounts.
    """
    try:
        # Validate input parameters
        if any(v is None for v in [symbol, balance, last_trade_times, lock]):
            log(
                f"⚠️ Skipping {symbol} — invalid input parameters (symbol={symbol}, balance={balance})",
                level="ERROR",
            )
            return None

        # Verify if symbol should be prioritized for small deposits
        if balance < 300 and symbol not in PRIORITY_SMALL_BALANCE_PAIRS:
            # Optional: Lower priority for non-priority pairs on small accounts
            log(f"⏩ Skipping {symbol} — not in priority list for small accounts", level="DEBUG")
            return None

        with open_positions_lock:
            positions = exchange.fetch_positions()
            active_positions = sum(1 for pos in positions if float(pos.get("contracts", 0)) != 0)

            # Use adaptive position limit
            max_positions = get_max_positions(balance)

            if active_positions >= max_positions:
                log(
                    f"⏩ Skipping {symbol} — max open positions ({max_positions}) reached (current: {active_positions})",
                    level="DEBUG",
                )
                return None

            if get_position_size(symbol) > 0:
                log(f"⏩ Skipping {symbol} — already in position", level="DEBUG")
                return None

            # Check available margin
            balance_info = exchange.fetch_balance()
            margin_info = balance_info["info"]
            total_margin_balance = float(margin_info.get("totalMarginBalance", 0))
            position_initial_margin = float(margin_info.get("totalPositionInitialMargin", 0))
            open_order_initial_margin = float(margin_info.get("totalOpenOrderInitialMargin", 0))
            available_margin = total_margin_balance - position_initial_margin - open_order_initial_margin

            # Apply safety buffer for margin
            margin_with_buffer = available_margin * MARGIN_SAFETY_BUFFER

            if margin_with_buffer <= 0:
                log(
                    f"⚠️ Skipping {symbol} — no available margin (total: {total_margin_balance:.2f}, positions: {position_initial_margin:.2f}, orders: {open_order_initial_margin:.2f})",
                    level="ERROR",
                )
                send_telegram_message(f"⚠️ No available margin for {symbol}", force=True, parse_mode="")
                return None

                # === Fetch market data based on strategy mode ===
            config = get_runtime_config()
            use_multitf = config.get("USE_MULTITF_LOGIC", False)
            mode = determine_strategy_mode(symbol, balance)

            if mode == "scalp":
                df = fetch_data_optimized(symbol)
                log(f"[ScalpingMode] Using optimized data for {symbol}", level="DEBUG")
            elif use_multitf:
                df = fetch_data_multiframe(symbol)
                log(f"[MultiTF] Using fetch_data_multiframe() for {symbol}", level="DEBUG")
            else:
                df = fetch_data(symbol)
                log(f"[StandardMode] Using fetch_data() for {symbol}", level="DEBUG")

            if df is None:
                log(f"⚠️ Skipping {symbol} — fetch_data returned None", level="WARNING")
                send_telegram_message(f"⚠️ Failed to fetch data for {symbol}", force=True, parse_mode="")
                return None

            # Get trading signal
            result = should_enter_trade(symbol, df, exchange, last_trade_times, lock)
            if result is None:
                log(f"❌ No signal for {symbol}", level="DEBUG")
                return None

            direction, score, is_reentry = result

            # Verify direction is valid
            if direction not in ["buy", "sell"]:
                log(f"⚠️ Skipping {symbol} — invalid direction: {direction}", level="ERROR")
                return None

            # Get entry price
            try:
                entry = float(df["close"].iloc[-1])
                if entry <= 0:
                    log(f"⚠️ Skipping {symbol} — invalid entry price: {entry}", level="ERROR")
                    return None
            except (IndexError, ValueError, TypeError) as e:
                log(f"⚠️ Skipping {symbol} — error getting entry price: {e}", level="ERROR")
                return None

            # Determine market regime
            regime = get_market_regime(symbol)

            # Calculate TP/SL using ATR
            try:
                tp1_price, tp2_price, sl_price, tp1_share, tp2_share = calculate_tp_levels(entry, direction, regime, score, df)

                # Add explicit validation for return values
                log(f"DEBUG: TP/SL values for {symbol}: tp1={tp1_price}, tp2={tp2_price}, sl={sl_price}, tp1_share={tp1_share}, tp2_share={tp2_share}", level="DEBUG")

                # Validate TP/SL
                if any(v is None for v in [tp1_price, sl_price, tp1_share]):
                    log(
                        f"⚠️ Skipping {symbol} — invalid TP/SL values (tp1={tp1_price}, sl={sl_price}, tp1_share={tp1_share})",
                        level="ERROR",
                    )
                    return None
            except Exception as e:
                log(f"⚠️ Skipping {symbol} — error calculating TP/SL levels: {e}", level="ERROR")
                return None

            # Use adaptive risk percentage based on signal strength and account size
            risk_percent = get_risk_percent_by_score(balance, score)

            try:
                qty = calculate_order_quantity(entry, sl_price, balance, risk_percent)

                # Validate quantity
                if qty is None or qty <= 0:
                    log(f"⚠️ Skipping {symbol} — invalid quantity: {qty}", level="ERROR")
                    return None
            except Exception as e:
                log(f"⚠️ Skipping {symbol} — error calculating order quantity: {e}", level="ERROR")
                return None

            # Check risk/reward ratio
            try:
                required_rr_ratio = get_required_risk_reward_ratio(score)
                actual_rr_ratio = calculate_risk_reward_ratio(entry, tp1_price, sl_price, direction)

                # For small accounts, slightly lower the R/R requirement for high-score signals
                if balance < 300 and score >= 4.0:
                    required_rr_ratio *= 0.9
                    log(f"📊 Adjusted R/R requirement for small account: {required_rr_ratio:.2f}", level="DEBUG")

                if actual_rr_ratio < required_rr_ratio:
                    log(
                        f"⚠️ Skipping {symbol} — insufficient risk/reward ratio: {actual_rr_ratio:.2f} < {required_rr_ratio:.2f}",
                        level="WARNING",
                    )
                    return None
            except Exception as e:
                log(f"⚠️ Skipping {symbol} — error calculating risk/reward ratio: {e}", level="ERROR")
                return None

            # Normalize symbol format for LEVERAGE_MAP
            normalized_symbol = symbol.split(":")[0].replace("/", "") if ":" in symbol else symbol.replace("/", "")

            # Get leverage from map
            leverage = LEVERAGE_MAP.get(normalized_symbol, 5)

            # Validate required_margin calculation inputs
            if qty is None or entry is None or leverage is None or leverage == 0:
                log(f"⚠️ Skipping {symbol} — invalid values for margin calculation: qty={qty}, entry={entry}, leverage={leverage}", level="ERROR")
                return None

            try:
                required_margin = qty * entry / leverage

                # Check margin sufficiency with buffer
                if required_margin > margin_with_buffer:
                    log(
                        f"⚠️ Skipping {symbol} — insufficient margin (required: {required_margin:.2f}, available: {margin_with_buffer:.2f})",
                        level="WARNING",
                    )
                    send_telegram_message(f"⚠️ Insufficient margin for {symbol}", force=True, parse_mode="")
                    return None
            except Exception as e:
                log(f"⚠️ Skipping {symbol} — error calculating required margin: {e}", level="ERROR")
                return None

            # Check notional value with validation
            if qty is None or entry is None:
                log(f"⚠️ Skipping {symbol} — invalid values for notional calculation: qty={qty}, entry={entry}", level="ERROR")
                return None

            try:
                notional = qty * entry

                # Get minimum notional from exchange or config
                try:
                    markets = exchange.load_markets()
                    api_symbol = convert_symbol(symbol)  # Convert symbol format for exchange API
                    min_notional = (
                        markets[api_symbol]["limits"]["amount"]["min"] * entry
                        if api_symbol in markets and "limits" in markets[api_symbol] and "amount" in markets[api_symbol]["limits"] and "min" in markets[api_symbol]["limits"]["amount"]
                        else MIN_NOTIONAL_OPEN
                    )
                except Exception as e:
                    # Fallback to config value if exchange data isn't available
                    log(f"⚠️ Error getting market limits for {symbol}: {e}. Using default MIN_NOTIONAL_OPEN.", level="WARNING")
                    min_notional = MIN_NOTIONAL_OPEN

                # Try to adjust quantity if notional is too small
                if notional < min_notional:
                    # Validate calculation inputs
                    if entry is None or entry == 0:
                        log(f"⚠️ Skipping {symbol} — invalid entry price for adjusted quantity calculation: {entry}", level="ERROR")
                        return None

                    # Attempt to adjust for small deposits
                    adjusted_qty = min_notional / entry

                    # Validate adjusted values
                    if adjusted_qty is None or entry is None or leverage is None or leverage == 0:
                        log(f"⚠️ Skipping {symbol} — invalid values for adjusted margin calculation", level="ERROR")
                        return None

                    adjusted_notional = adjusted_qty * entry
                    adjusted_margin = adjusted_qty * entry / leverage

                    # Check if adjusted margin is within limits
                    if adjusted_margin <= margin_with_buffer:
                        log(
                            f"ℹ️ Adjusting qty for {symbol} from {qty:.6f} to {adjusted_qty:.6f} to meet minimum notional {min_notional:.2f}",
                            level="INFO",
                        )
                        qty = adjusted_qty
                        notional = adjusted_notional
                    else:
                        log(
                            f"⚠️ Notional too low for {symbol} — notional: {notional:.2f}, required: {min_notional:.2f}, skipping",
                            level="WARNING",
                        )
                        send_telegram_message(f"⚠️ Notional too low for {symbol}", force=True, parse_mode="")
                        return None
            except Exception as e:
                log(f"⚠️ Skipping {symbol} — error handling notional calculations: {e}", level="ERROR")
                return None

            # Calculate expected profit with commissions
            try:
                profit_check, expected_profit_tp1 = check_min_profit(entry, tp1_price, qty, tp1_share, direction, TAKER_FEE_RATE, get_min_net_profit(balance))

                # Skip trades with insufficient profit
                if not profit_check:
                    log(
                        f"⚠️ Skipping {symbol} — expected profit {expected_profit_tp1:.2f} USDC below minimum requirement",
                        level="WARNING",
                    )
                    return None

                # For small accounts, additional validation of expected profit
                if balance < 300 and expected_profit_tp1 < 0.25:
                    log(
                        f"⚠️ Skipping {symbol} — expected profit {expected_profit_tp1:.2f} USDC too small for account balance {balance:.2f}",
                        level="WARNING",
                    )
                    return None
            except Exception as e:
                log(f"⚠️ Skipping {symbol} — error calculating expected profit: {e}", level="ERROR")
                return None

            # Detailed logging for small deposit traders
            log(
                f"{symbol} 🔍 Calculated qty: {qty:.3f}, entry: {entry:.2f}, notional: {notional:.2f}, "
                f"expected profit: {expected_profit_tp1:.2f} USDC, R/R: {actual_rr_ratio:.2f}, Risk: {risk_percent*100:.2f}%",
                level="INFO" if balance < 300 else "DEBUG",
            )

            # If this is a small account and a priority pair, send Telegram notification for visibility
            if balance < 300 and symbol in PRIORITY_SMALL_BALANCE_PAIRS:
                send_telegram_message(f"📊 Valid signal for {symbol} (priority pair) - Score: {score:.1f}, Expected profit: ${expected_profit_tp1:.2f}", force=True, parse_mode="")

            return {
                "symbol": symbol,
                "direction": direction,
                "qty": qty,
                "entry": entry,
                "tp1": tp1_price,
                "tp2": tp2_price,
                "sl": sl_price,
                "score": score,
                "is_reentry": is_reentry,
            }
    except Exception as e:
        log(f"🔥 Error in process_symbol for {symbol}: {e}", level="ERROR")
        send_telegram_message(f"❌ Error in process_symbol for {symbol}: {e}", force=True, parse_mode="")
        return None
