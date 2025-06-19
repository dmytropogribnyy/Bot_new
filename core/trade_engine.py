# trade_engine.py

import json
import threading
import time
from threading import Lock

import pandas as pd
import ta

from common.config_loader import (
    AUTO_CLOSE_PROFIT_THRESHOLD,
    BONUS_PROFIT_THRESHOLD,
    DRY_RUN,
    MICRO_PROFIT_ENABLED,
    MICRO_PROFIT_THRESHOLD,
    MICRO_TRADE_SIZE_THRESHOLD,
    MICRO_TRADE_TIMEOUT_MINUTES,
)
from core.binance_api import fetch_ohlcv
from core.exchange_init import exchange
from telegram.telegram_utils import send_telegram_message
from utils_core import get_cached_balance, initialize_cache, load_state, normalize_symbol, safe_call_retry
from utils_logging import log

_active_trades_save_lock = Lock()


###############################################################################
#                     TRADE INFO MANAGER (GLOBAL STORAGE)                     #
###############################################################################


class TradeInfoManager:
    def __init__(self):
        self._trades = {}
        self._lock = threading.Lock()

    def add_trade(self, symbol, trade_data):
        symbol = normalize_symbol(symbol)
        with self._lock:
            self._trades[symbol] = trade_data

    def get_trade(self, symbol):
        symbol = normalize_symbol(symbol)
        with self._lock:
            return self._trades.get(symbol)

    def update_trade(self, symbol, key, value):
        symbol = normalize_symbol(symbol)
        with self._lock:
            if symbol in self._trades:
                self._trades[symbol][key] = value

    def remove_trade(self, symbol):
        symbol = normalize_symbol(symbol)
        with self._lock:
            return self._trades.pop(symbol, None)

    def get_last_closed_time(self, symbol):
        symbol = normalize_symbol(symbol)
        with self._lock:
            return self._trades.get(symbol, {}).get("last_closed_time", None)

    def set_last_closed_time(self, symbol, timestamp):
        symbol = normalize_symbol(symbol)
        with self._lock:
            if symbol not in self._trades:
                self._trades[symbol] = {}
            self._trades[symbol]["last_closed_time"] = timestamp

    def count_active_positions(self):
        with self._lock:
            return len(self._trades)

    def get_all_trades(self):
        with self._lock:
            return dict(self._trades)

    def has_trade(self, symbol):
        symbol = normalize_symbol(symbol)
        with self._lock:
            return symbol in self._trades

    def clear_all(self):
        with self._lock:
            self._trades.clear()


###############################################################################
#                             GLOBAL VARIABLES                                #
###############################################################################

trade_manager = TradeInfoManager()
monitored_stops = {}
monitored_stops_lock = threading.Lock()

open_positions_count = 0
dry_run_positions_count = 0
open_positions_lock = threading.Lock()

logged_trades = set()
logged_trades_lock = Lock()


###############################################################################
#                               CORE METHODS                                  #
###############################################################################


def close_trade_and_cancel_orders(binance_client, symbol, side, quantity, reduce_only=True):
    """
    Close a position with a market order and cancel all related orders.
    """
    try:
        close_side = "SELL" if side.upper() == "BUY" else "BUY"

        # Cancel open orders
        try:
            binance_client.futures_cancel_all_open_orders(symbol=symbol.replace("/", ""))
            log(f"✅ Canceled all open orders for {symbol}.", level="INFO")
        except Exception as e:
            log(f"❌ Error canceling orders for {symbol}: {str(e)}", level="WARNING")

        # Then close the position
        binance_client.futures_create_order(
            symbol=symbol.replace("/", ""),
            side=close_side,
            type="MARKET",
            quantity=quantity,
            reduceOnly=reduce_only,
        )
        log(f"✅ Closed position {symbol} — {quantity} units by MARKET.", level="INFO")

    except Exception as e:
        log(f"❌ Error while closing {symbol}: {str(e)}", level="ERROR")


def safe_close_trade(binance_client, symbol, trade_data, reason="manual"):
    """
    Safely close a trade by cancelling all orders and closing the position.
    Проверяет, была ли позиция действительно закрыта.
    """
    symbol = normalize_symbol(symbol)

    try:
        if not trade_data or "side" not in trade_data or "quantity" not in trade_data:
            log(f"[SafeClose] ⚠️ Incomplete trade data for {symbol}: {trade_data}", level="ERROR")
            return

        side = trade_data["side"]
        quantity = trade_data["quantity"]
        entry_price = trade_data.get("entry", 0)

        ticker = safe_call_retry(exchange.fetch_ticker, symbol)
        exit_price = ticker["last"] if ticker else None

        log(f"[SafeClose] Executing market close: {symbol}, qty={quantity}, side={side}", level="INFO")

        close_trade_and_cancel_orders(
            binance_client=binance_client,
            symbol=symbol,
            side=side,
            quantity=quantity,
        )

        time.sleep(1.5)
        remaining = get_position_size(symbol)
        if remaining > 0:
            log(f"[SafeClose] ⚠️ Position still open for {symbol} after close attempt! Qty={remaining}", level="WARNING")
        else:
            log(f"[SafeClose] ✅ Position confirmed closed for {symbol}", level="DEBUG")

        if exit_price:
            if side.lower() == "buy":
                final_pnl = (exit_price - entry_price) * quantity
            else:
                final_pnl = (entry_price - exit_price) * quantity

            log(f"[SafeClose] {symbol} closed with PnL = {final_pnl:.2f} USDC", level="INFO")
            record_trade_result(symbol, side, entry_price, exit_price, reason)

        trade_manager.remove_trade(symbol)
        log(f"✅ Safe close complete for {symbol} (reason: {reason})", level="INFO")

    except Exception as e:
        log(f"❌ Error during safe close for {symbol}: {str(e)}", level="ERROR")


def calculate_risk_amount(balance, symbol=None, atr_percent=None, volume_usdc=None):
    """
    Расчёт risk_amount с учётом:
    - base_risk_pct из runtime_config
    - risk_multiplier
    - risk_factor (для symbol)
    - adaptive effective_sl = max(SL_PERCENT, atr_percent * 1.5)

    Возвращает:
        risk_amount (в USDC), effective_sl (в %)
    """
    from core.fail_stats_tracker import get_symbol_risk_factor
    from utils_core import get_runtime_config
    from utils_logging import log

    cfg = get_runtime_config()

    base_risk_pct = cfg.get("base_risk_pct", 0.0075)  # по умолчанию 0.75%
    risk_multiplier = cfg.get("risk_multiplier", 1.0)
    sl_percent = cfg.get("SL_PERCENT", 0.01)

    # === Эффективный стоп-лосс: учитывает ATR
    effective_sl = sl_percent
    if atr_percent:
        effective_sl = max(sl_percent, atr_percent * 1.5)

    # === Учитываем риск-фактор (если symbol указан)
    risk_factor = 1.0
    if symbol:
        rf, _ = get_symbol_risk_factor(symbol)
        risk_factor = rf
        log(f"[Risk] Risk factor for {symbol}: {risk_factor:.2f}", level="DEBUG")

    # === Расчёт итогового риска
    risk_amount = balance * base_risk_pct * risk_multiplier * risk_factor

    log(f"[Risk] balance={balance:.2f}, base_pct={base_risk_pct:.4f}, multiplier={risk_multiplier}, factor={risk_factor:.2f} → risk=${risk_amount:.2f}, SL={effective_sl:.4f}", level="DEBUG")

    return risk_amount, effective_sl


def calculate_position_size(symbol, entry_price, balance, leverage, runtime_config=None):
    """
    Рассчитывает размер позиции с учётом:
    - риск-процента
    - max_margin_percent на сделку
    - max_capital_utilization_pct на все сделки
    - минимального нотионала
    Возвращает (qty, risk_amount)
    """
    from common.config_loader import MIN_NOTIONAL_OPEN
    from core.binance_api import round_step_size
    from utils_core import get_runtime_config, get_total_position_value
    from utils_logging import log

    if runtime_config is None:
        runtime_config = get_runtime_config()

    base_risk_pct = runtime_config.get("base_risk_pct", 0.01)
    max_capital_utilization_pct = runtime_config.get("max_capital_utilization_pct", 0.5)
    max_margin_percent = runtime_config.get("max_margin_percent", 0.5)
    min_notional_open = runtime_config.get("MIN_NOTIONAL_OPEN", MIN_NOTIONAL_OPEN)

    risk_amount = balance * base_risk_pct
    max_trade_value = balance * max_margin_percent

    if entry_price <= 0:
        log(f"[ERROR] Invalid entry price {entry_price} for {symbol}", level="ERROR")
        return 0.0, 0.0

    # Расчет позиции
    qty = (risk_amount * leverage) / entry_price
    notional = qty * entry_price

    if notional > max_trade_value:
        qty = max_trade_value / entry_price
        log(f"[CAP LIMIT] {symbol}: reduced qty to fit max_margin_percent ({max_margin_percent * 100:.1f}%)", level="WARNING")
        notional = qty * entry_price

    # Проверка капитализации
    total_used = get_total_position_value()
    projected_total = total_used + notional
    max_total = balance * max_capital_utilization_pct

    if projected_total > max_total:
        log(f"[BLOCKED] {symbol}: capital usage {projected_total:.2f} > {max_total:.2f} (limit {max_capital_utilization_pct*100:.0f}%)", level="WARNING")
        return 0.0, 0.0

    # Минимальный нотионал
    if notional < min_notional_open:
        log(f"[SKIPPED] {symbol}: notional {notional:.2f} < MIN_NOTIONAL_OPEN {min_notional_open}", level="WARNING")
        return 0.0, 0.0

    # Округление
    qty = round_step_size(symbol, qty)
    log(f"[QTY OK] {symbol} → qty={qty:.6f}, notional={qty * entry_price:.2f}, risk={risk_amount:.2f}", level="DEBUG")

    return qty, risk_amount


def get_position_size(symbol):
    """
    Возвращает объём открытой позиции (в контрактах) для заданного symbol.
    Проверяет contracts / positionAmt / amount. Возвращает abs(amount).
    """
    from utils_core import get_cached_positions, normalize_symbol
    from utils_logging import log

    try:
        positions = get_cached_positions()
        symbol_norm = normalize_symbol(symbol)
        log(f"[get_position_size] Looking for {symbol_norm} in {len(positions)} positions", level="DEBUG")

        for pos in positions:
            pos_symbol = normalize_symbol(pos.get("symbol", ""))
            if pos_symbol != symbol_norm:
                continue

            raw_value = pos.get("contracts") or pos.get("positionAmt") or pos.get("amount")
            try:
                amount = float(raw_value)
                abs_amount = abs(amount)
                if abs_amount > 0:
                    log(f"[get_position_size] {symbol} → {abs_amount} contracts", level="DEBUG")
                    return abs_amount
                else:
                    log(f"[get_position_size] {symbol} → zero position: {amount}", level="DEBUG")
            except (TypeError, ValueError) as e:
                log(f"[get_position_size] Invalid numeric value for {symbol}: {raw_value} ({e})", level="ERROR")

        log(f"[get_position_size] {symbol} → not found in active positions", level="DEBUG")

    except Exception as e:
        log(f"[get_position_size] Error while fetching size for {symbol}: {e}", level="ERROR")

    return 0


def get_market_regime(symbol):
    """
    Enhanced market regime detection with breakout support.
    Возвращает: "breakout", "trend", "flat", или "neutral"
    """
    import numpy as np

    from utils_logging import log

    # === Настройки порогов
    BREAKOUT_DETECTION = True
    ADX_TREND_THRESHOLD = 20
    ADX_FLAT_THRESHOLD = 12

    try:
        ohlcv = fetch_ohlcv(symbol, timeframe="15m", limit=50)

        # Проверка данных
        if not isinstance(ohlcv, list) or len(ohlcv) < 28:
            log(f"{symbol} ⚠️ Insufficient or invalid OHLCV data => neutral", level="WARNING")
            return "neutral"

        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        closes = [c[4] for c in ohlcv]
        df = pd.DataFrame({"high": highs, "low": lows, "close": closes})

        # === ADX
        adx_series = ta.trend.ADXIndicator(df["high"], df["low"], df["close"], window=14).adx()
        if adx_series.isna().all():
            log(f"{symbol} ⚠️ ADX calc returned all NaN => neutral", level="WARNING")
            return "neutral"

        adx = adx_series.iloc[-1]
        if np.isnan(adx) or adx < 1 or adx > 100:
            log(f"{symbol} ⚠️ ADX invalid value ({adx}) => neutral", level="WARNING")
            return "neutral"

        # === Bollinger Band Width (BBW)
        bb = ta.volatility.BollingerBands(df["close"], window=20)
        bb_width = (bb.bollinger_hband().iloc[-1] - bb.bollinger_lband().iloc[-1]) / df["close"].iloc[-1]
        if np.isnan(bb_width) or bb_width <= 0:
            log(f"{symbol} ⚠️ BBW invalid or too low ({bb_width}) => neutral", level="WARNING")
            return "neutral"

        log(f"{symbol} 🔍 Market regime: ADX={adx:.2f}, BBW={bb_width:.4f}", level="DEBUG")

        # === Детект режимов
        if BREAKOUT_DETECTION and bb_width > 0.05 and adx > 20:
            log(f"{symbol} 🔍 Breakout!", level="INFO")
            return "breakout"
        elif adx > ADX_TREND_THRESHOLD:
            return "trend"
        elif adx < ADX_FLAT_THRESHOLD:
            return "flat"
        else:
            return "neutral"

    except Exception as e:
        log(f"[ERROR] Market regime for {symbol}: {e}", level="ERROR")
        return "neutral"


###############################################################################
#                                ENTER TRADE                                  #
###############################################################################
def save_active_trades():
    """
    Унифицированная запись текущего состояния сделок trade_manager._trades
    в файл data/active_trades.json с блокировкой от гонки потоков.
    """
    from core.trade_engine import trade_manager  # или передавать trade_manager в аргументах

    with _active_trades_save_lock:
        try:
            with open("data/active_trades.json", "w", encoding="utf-8") as f:
                json.dump(dict(trade_manager._trades), f, indent=2, default=str)
            log("[Save] active_trades.json updated", level="DEBUG")
        except Exception as e:
            log(f"[ERROR] Failed to save active_trades.json: {e}", level="ERROR")


def enter_trade(symbol, side, is_reentry=False, breakdown=None, pair_type="unknown"):
    """
    Финальная версия метода входа в сделку (v3.2 FIXED):
    - Проверяет лимиты, торговые часы, сигналы
    - Вызывает market order → проверяет filled_qty
    - Генерирует TP/SL уровни ДО log_entry(...) и TP-установки
    - Передаёт tp_prices, tp1, tp2, sl и доли в trade_data
    """
    import numpy as np

    from common.config_loader import DRY_RUN, MAX_OPEN_ORDERS, MIN_NOTIONAL_OPEN, SHORT_TERM_MODE, get_priority_small_balance_pairs
    from common.leverage_config import get_leverage_for_symbol
    from core.binance_api import convert_symbol, create_safe_market_order
    from core.component_tracker import log_component_data
    from core.entry_logger import log_entry
    from core.fail_stats_tracker import get_symbol_risk_factor
    from core.position_manager import check_entry_allowed
    from core.runtime_stats import update_trade_count
    from core.signal_utils import passes_1plus1
    from core.strategy import fetch_data_multiframe
    from core.tp_utils import calculate_tp_levels, place_take_profit_and_stop_loss_orders
    from core.trade_engine import dry_run_positions_count, get_position_size, open_positions_count, open_positions_lock, save_active_trades, trade_manager
    from telegram.telegram_utils import send_telegram_message
    from utils_core import extract_symbol, get_cached_balance, get_runtime_config, is_optimal_trading_hour, load_state, safe_call_retry
    from utils_logging import log, now

    symbol = extract_symbol(symbol)
    api_symbol = convert_symbol(symbol)
    opened_position = False

    try:
        exchange.load_markets()
    except Exception as e:
        log(f"[Enter Trade] Failed to load markets: {e}", level="ERROR")
        return False

    if breakdown:
        log(f"[Breakdown] {symbol} entry breakdown: {breakdown}", level="DEBUG")
        if not passes_1plus1(breakdown):
            log(f"❌ Signal rejected by passes_1plus1() for {symbol}", level="WARNING")
            send_telegram_message(f"🧱 Skipping {symbol}: failed passes_1plus1 check", force=True)
            return False
        log_component_data(symbol, breakdown, is_successful=True)

    state = load_state()
    if state.get("stopping"):
        log("⛔ Cannot enter trade: bot is stopping.", level="WARNING")
        return False

    if SHORT_TERM_MODE and not is_optimal_trading_hour():
        balance = get_cached_balance()
        if balance < 120 and symbol in get_priority_small_balance_pairs():
            log(f"[Override] {symbol} priority pair allowed during non-optimal hours", level="INFO")
        else:
            log(f"⏰ {symbol} skipped: non-optimal hours", level="INFO")
            send_telegram_message(f"⏰ Skipping {symbol}: non-optimal trading hours", force=True)
            return False

    balance = get_cached_balance()
    can_enter, reason = check_entry_allowed(balance)
    if not can_enter:
        log(f"[Limit] Entry denied for {symbol}: {reason}", level="INFO")
        send_telegram_message(f"⛔️ Skipping {symbol} — {reason.replace('_', ' ')}", force=True)
        return False

    try:
        ticker = safe_call_retry(exchange.fetch_ticker, api_symbol, label=f"enter_trade {symbol}")
        if not ticker:
            log(f"[ERROR] Failed to fetch ticker for {symbol}", level="ERROR")
            send_telegram_message(f"⚠️ Failed to fetch ticker for {symbol}", force=True)
            return False

        entry_price = ticker["last"]
        start_time = now()

        if is_reentry and get_position_size(symbol) > 0:
            log(f"Skipping re-entry for {symbol}: position already open", level="WARNING")
            send_telegram_message(f"🔁 Skipping re-entry: already in position {symbol}", force=True)
            return False

        rf, _ = get_symbol_risk_factor(symbol)
        min_rf = get_runtime_config().get("min_risk_factor", 0.9)
        log(f"[Risk] {symbol}: risk_factor={rf:.2f} vs min_rf={min_rf}", level="DEBUG")
        if rf < min_rf:
            log(f"[Skip] {symbol}: risk_factor {rf:.2f} < min_risk_factor {min_rf}", level="INFO")
            send_telegram_message(f"⚠️ Skipping {symbol}: risk factor too low ({rf:.2f} < {min_rf})", force=True)
            return False

        atr_percent = ticker.get("atr_percent", None)
        risk_amount, effective_sl = calculate_risk_amount(balance, symbol=symbol, atr_percent=atr_percent)
        if effective_sl <= 0:
            log(f"[Risk] Invalid effective SL for {symbol}", level="ERROR")
            return False

        leverage = get_leverage_for_symbol(symbol)
        qty, _ = calculate_position_size(symbol, entry_price, balance, leverage)

        if not isinstance(qty, (float, int)) or qty <= 0:
            log(f"[Risk] Invalid position size for {symbol}: {qty}", level="ERROR")
            return False

        precision = exchange.markets[api_symbol]["precision"]["amount"]
        min_qty = exchange.markets[api_symbol]["limits"]["amount"]["min"]
        qty = round(qty, precision)
        if qty < min_qty or qty <= 0:
            qty = min_qty

        notional = qty * entry_price
        if notional < MIN_NOTIONAL_OPEN:
            log(f"[Notional] {symbol} too small: ${notional:.2f}", level="WARNING")
            send_telegram_message(f"⚠️ Skipping {symbol}: notional too small (${notional:.2f})", force=True)
            return False

        if len(exchange.fetch_open_orders(api_symbol)) >= MAX_OPEN_ORDERS:
            log(f"[Orders] Too many open orders for {symbol}", level="WARNING")
            return False

        df = fetch_data_multiframe(symbol)
        if df is None or len(df) < 5:
            log(f"[Data] Failed to fetch data for {symbol} before TP calc", level="ERROR")
            return False

        tp1, tp2, sl_price, share1, share2 = calculate_tp_levels(entry_price, side, df=df)
        if any(x is None or (isinstance(x, float) and np.isnan(x)) for x in (tp1, sl_price, share1)):
            log(f"[TPCheck] ❌ Invalid TP/SL for {symbol} — aborting entry", level="WARNING")
            send_telegram_message(f"⚠️ Aborting entry {symbol}: invalid TP/SL", force=True)
            return False

        if tp1 <= 0:
            log(f"[TPCheck] ❌ tp1={tp1:.5f} is invalid for {symbol}", level="WARNING")
            send_telegram_message(f"⚠️ Aborting entry {symbol}: tp1={tp1:.5f} invalid", force=True)
            return False

        tp_prices = [tp1, tp2, tp2 * 1.5]

        log(f"[Enter Trade] Creating market order for {symbol}: qty={qty:.4f}", level="INFO")
        result = create_safe_market_order(api_symbol, side.lower(), qty)
        log(f"[Binance] Market order response for {symbol}: {result}", level="DEBUG")

        if not result["success"]:
            log(f"[Enter Trade] Market order failed: {result['error']}", level="ERROR")
            send_telegram_message(f"❌ Failed to open trade {symbol}: {result['error']}", force=True)
            return False

        filled_qty = result.get("filled_qty", 0)
        if filled_qty == 0:
            log(f"[Enter Trade] ❌ 0 filled qty for {symbol} — aborting.", level="WARNING")
            send_telegram_message(f"⚠️ 0 filled qty for {symbol}. Trade will not be recorded.", force=True)
            return False

        opened_position = True
        with open_positions_lock:
            if DRY_RUN:
                dry_run_positions_count += 1
            else:
                open_positions_count += 1

        update_trade_count()

        try:
            success = place_take_profit_and_stop_loss_orders(api_symbol, side, entry_price, qty, tp_prices, sl_price)
            if not success:
                log(f"[TP/SL] TP/SL were not placed for {symbol}", level="WARNING")
        except Exception as e:
            log(f"[TP/SL] Error placing TP/SL: {e}", level="ERROR")
            send_telegram_message(f"⚠️ TP/SL placement failed for {symbol}: {e}", force=True)

        trade_data = {
            "symbol": symbol,
            "side": side,
            "entry": round(entry_price, 4),
            "qty": qty,
            "tp1_hit": False,
            "tp2_hit": False,
            "sl_hit": False,
            "soft_exit_hit": False,
            "start_time": start_time,
            "commission": 0.0,
            "net_profit_tp1": 0.0,
            "market_regime": "unknown",
            "breakdown": breakdown or {},
            "pair_type": pair_type,
            "sl_price": sl_price,
            "tp_prices": tp_prices,
            "tp1": tp1,
            "tp2": tp2,
            "tp1_share": share1,
            "tp2_share": share2,
            "tp3_share": 0.0,
        }

        trade_manager.add_trade(symbol, trade_data)
        save_active_trades()
        log_entry(trade_data, status="SUCCESS")

        log(f"[Enter Trade] ✅ ENTERED {symbol} qty={qty:.4f} @ {entry_price:.4f}", level="INFO")
        send_telegram_message(f"🚀 ENTER {symbol} {side.upper()} qty={qty:.4f} @ {entry_price:.4f}", force=True)
        return True

    except Exception as e:
        log(f"[Enter Trade] Unexpected error: {str(e)}", level="ERROR")
        send_telegram_message(f"❌ Unexpected error in trade {symbol}: {str(e)}", force=True)
        return False

    finally:
        if opened_position:
            with open_positions_lock:
                if DRY_RUN:
                    dry_run_positions_count -= 1
                else:
                    open_positions_count -= 1


def track_stop_loss(symbol, side, entry_price, qty, opened_at):
    from utils_logging import log

    with monitored_stops_lock:
        monitored_stops[symbol] = {
            "side": side,
            "entry": entry_price,
            "qty": qty,
            "opened_at": opened_at,
        }

    log(f"[SL-Track] Monitoring SL for {symbol} → {side} qty={qty} @ {entry_price}, opened_at={opened_at}", level="DEBUG")


###############################################################################
#                               AUX METHODS                                   #
###############################################################################


def run_break_even(symbol, side, entry_price, tp_percent, check_interval=5):
    """
    Optional. If you want break-even logic, keep it here.
    """
    pass  # (omitted for brevity if not used)


def run_adaptive_trailing_stop(symbol, side, entry_price, check_interval=5, pair_type="fixed"):
    """
    Optional trailing stop logic.
    """
    pass  # (omitted for brevity if not used)


def run_soft_exit(symbol, side, entry_price, tp1_percent, qty, check_interval=5):
    """
    Optional partial exit logic.
    """
    pass  # (omitted for brevity if not used)


###############################################################################
#                     RECORDING TRADE RESULTS / CLOSING                       #
###############################################################################


def record_trade_result(symbol, side, entry_price, exit_price, result_type):
    """
    Финальная фиксация сделки:
    - Вычисляет PnL, комиссию, чистую прибыль
    - Логирует в tp_performance.csv
    - Обновляет статистику компонентов и SL-стрик
    - Уведомляет в Telegram
    - Удаляет позицию из активных
    - Возвращает dict с итогами
    """
    import math
    import time
    import traceback

    import pandas as pd

    from core.component_tracker import log_component_data
    from core.exchange_init import exchange
    from core.runtime_state import (
        get_loss_streak,
        increment_loss_streak,
        pause_symbol,
        reset_loss_streak,
    )
    from core.trade_engine import (
        DRY_RUN,
        dry_run_positions_count,
        logged_trades,
        logged_trades_lock,
        open_positions_count,
        open_positions_lock,
        trade_manager,
    )
    from telegram.telegram_utils import send_telegram_message
    from tp_logger import log_trade_result as low_level_csv_writer
    from utils_core import (
        get_min_net_profit,
        normalize_symbol,
        save_active_trades,
        update_runtime_config,
    )
    from utils_logging import log

    symbol = normalize_symbol(symbol)
    caller_info = traceback.format_stack()[-2]
    log(f"[DEBUG] record_trade_result for {symbol}, {result_type}, caller: {caller_info}", level="DEBUG")

    trade_key = f"{symbol}_{result_type}_{entry_price}_{round(exit_price, 4)}"
    with logged_trades_lock:
        if trade_key in logged_trades:
            log(f"[DEBUG] Skipping duplicate logging {symbol}, {result_type}", level="DEBUG")
            return
        logged_trades.add(trade_key)

    with open_positions_lock:
        if DRY_RUN:
            dry_run_positions_count -= 1
        else:
            open_positions_count -= 1

    trade = trade_manager.get_trade(symbol)
    if not trade:
        log(f"⚠️ No trade info for {symbol} — cannot record result", level="WARNING")
        return
    if trade.get("closed_logged"):
        log(f"[DEBUG] {symbol} already recorded — skipping", level="DEBUG")
        return
    trade["closed_logged"] = True

    # Определение причины выхода
    exit_reason = (
        "post_hold"
        if trade.get("post_hold_hit")
        else "soft_exit"
        if trade.get("soft_exit_hit")
        else "tp2"
        if trade.get("tp2_hit")
        else "tp1"
        if trade.get("tp1_hit")
        else "sl"
        if trade.get("sl_hit") or result_type == "sl"
        else "flat"
        if result_type == "manual" and abs(exit_price - entry_price) / entry_price < 0.002
        else "manual"
        if result_type == "manual"
        else "unknown"
    )

    final_result_type = (
        "soft_exit"
        if trade.get("soft_exit_hit") and result_type in ["manual", "stop"]
        else "post_hold"
        if trade.get("post_hold_hit")
        else "trailing_tp"
        if trade.get("trailing_tp_active") and not trade.get("tp1_hit") and not trade.get("tp2_hit")
        else result_type
    )

    # Расчёт
    duration = int((time.time() - trade["start_time"].timestamp()) / 60)
    pnl = ((exit_price - entry_price) / entry_price) * 100
    if side.lower() == "sell":
        pnl *= -1

    qty = float(trade.get("qty", 0.0))
    commission = float(trade.get("commission", 0.0))
    atr = float(trade.get("atr", 0.0))
    pair_type = trade.get("pair_type", "unknown")
    breakdown = trade.get("breakdown", {})

    if qty <= 0:
        log(f"[Record] ⚠️ Zero qty for {symbol}, skipping record", level="ERROR")
        return

    absolute_profit = (exit_price - entry_price) * qty if side.lower() == "buy" else (entry_price - exit_price) * qty
    net_absolute_profit = absolute_profit - commission
    try:
        net_pnl_percent = (net_absolute_profit / abs(entry_price * qty)) * 100
    except ZeroDivisionError:
        net_pnl_percent = 0.0

    net_absolute_profit = 0.0 if math.isnan(net_absolute_profit) else net_absolute_profit
    net_pnl_percent = 0.0 if math.isnan(net_pnl_percent) else net_pnl_percent

    if net_absolute_profit < 0 < absolute_profit:
        log(f"[Anomaly] {symbol} → Profit eaten by commission: gross={absolute_profit:.2f}, commission={commission:.2f}", level="WARNING")

    log(f"[PnL] {symbol} entry={entry_price}, exit={exit_price}, qty={qty}, gross={absolute_profit:.2f}, net={net_absolute_profit:.2f}, fee={commission:.2f}", level="DEBUG")
    log(f"[FinalResult] {symbol} exit={exit_reason}, final={final_result_type}, pnl={pnl:.2f}%", level="INFO")

    is_successful = (exit_reason.startswith("tp") or final_result_type == "trailing_tp") and net_absolute_profit > 0
    log_component_data(symbol, breakdown, is_successful=is_successful)

    # CSV лог
    try:
        low_level_csv_writer(
            symbol=symbol,
            direction=side.upper(),
            entry_price=entry_price,
            exit_price=exit_price,
            qty=qty,
            tp1_hit=trade.get("tp1_hit", False),
            tp2_hit=trade.get("tp2_hit", False),
            sl_hit=trade.get("sl_hit", False),
            pnl_percent=round(pnl, 2),
            duration_minutes=duration,
            result_type=final_result_type,
            exit_reason=exit_reason,
            atr=atr,
            pair_type=pair_type,
            commission=commission,
            net_pnl=round(net_pnl_percent, 2),
            absolute_profit=round(net_absolute_profit, 2),
            entry_time=trade["start_time"].strftime("%Y-%m-%d %H:%M:%S"),
            exit_time=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
    except Exception as e:
        log(f"[ERROR] Failed to log trade to CSV: {e}", level="ERROR")

    # Адаптация min_profit_threshold
    if is_successful:
        prev = get_min_net_profit()
        if prev < 0.30:
            new_val = round(min(0.30, prev + 0.10), 2)
            update_runtime_config({"min_profit_threshold": new_val})
            log(f"[ProfitAdapt] min_profit_threshold updated to {new_val}", level="INFO")
    elif result_type == "sl" and net_absolute_profit < 0:
        update_runtime_config({"min_profit_threshold": 0.10})
        log("[ProfitAdapt] Reset min_profit_threshold to 0.10 after SL", level="WARNING")

    # SL-стрик
    if result_type == "sl" or trade.get("sl_hit"):
        increment_loss_streak(symbol)
        streak = get_loss_streak(symbol)
        log(f"[LossStreak] {symbol} SL count = {streak}", level="WARNING")
        if streak >= 3:
            pause_symbol(symbol, minutes=15)
            reset_loss_streak(symbol)
    else:
        reset_loss_streak(symbol)

    if exit_reason == "flat":
        send_telegram_message(f"⚠️ *Flat Close*: {symbol} @ {exit_price:.4f} — too close to entry", force=True)

    icon = "🟢" if final_result_type in ["tp", "tp1", "tp2", "trailing_tp"] else "🔴" if final_result_type == "sl" else "⚪"
    msg = (
        f"{icon} *Trade Closed* [{final_result_type.upper()} / {exit_reason.upper()}]\n"
        f"• {symbol} — {side.upper()}\n"
        f"• Entry: {round(entry_price, 4)} → Exit: {round(exit_price, 4)}\n"
        f"• PnL: {round(pnl, 2)}% | Gross: ${round(absolute_profit, 2)} | Net: ${round(net_absolute_profit, 2)}\n"
        f"• Held: {duration} min | Time: {pd.Timestamp.now().strftime('%H:%M:%S')}"
    )
    send_telegram_message(msg, force=True)

    try:
        exchange.cancel_all_orders(symbol)
        log(f"[Cleanup] Cancelled all remaining orders for {symbol}", level="INFO")
    except Exception as e:
        log(f"[Cleanup] Failed to cancel orders for {symbol}: {e}", level="WARNING")

    trade_manager.remove_trade(symbol)
    log(f"[Cleanup] Removed {symbol} from active trades", level="DEBUG")
    save_active_trades()
    log(f"[Save] active_trades.json updated after closing {symbol}", level="DEBUG")

    return {
        "symbol": symbol,
        "exit_reason": exit_reason,
        "result_type": final_result_type,
        "net_usd": round(net_absolute_profit, 2),
        "pnl_percent": round(pnl, 2),
        "duration_min": duration,
    }


def close_dry_trade(symbol):
    """
    Закрываем DRY-run сделку сразу, если нужно принудительно.
    """
    if DRY_RUN:
        trade = trade_manager.get_trade(symbol)
        if trade:
            ticker = safe_call_retry(exchange.fetch_ticker, symbol, label=f"fetch_ticker {symbol}")
            if not ticker:
                return
            exit_price = ticker["last"]
            record_trade_result(symbol, trade["side"], trade["entry"], exit_price, "manual")
            log(f"[DRY] Closed {symbol} at {exit_price}", level="INFO")
            send_telegram_message(f"DRY RUN: Closed {symbol} at {exit_price}", force=True)
            trade_manager.set_last_closed_time(symbol, time.time())


def close_real_trade(symbol):
    """
    Принудительно закрываем реальную сделку.
    Сначала отменяем ордера, затем маркет-закрытие, затем логирование через record_trade_result(...).
    """
    symbol = normalize_symbol(symbol)

    state = load_state()
    trade = trade_manager.get_trade(symbol)

    if not trade:
        if not state.get("stopping") and not state.get("shutdown"):
            log(f"[SmartSwitch] No active trade for {symbol}", level="WARNING")
        return

    try:
        # 🔁 Безопасная авто-очистка всех ордеров
        try:
            exchange.cancel_all_orders(symbol)
            log(f"[Cleanup] Cancelled all open orders for {symbol}", level="INFO")
        except Exception as e:
            log(f"[Cleanup] Failed to cancel all orders for {symbol}: {e}", level="WARNING")

        # 🔍 Проверка позиции
        positions = exchange.fetch_positions()
        position = next((p for p in positions if p["symbol"] == symbol and float(p.get("contracts", 0)) > 0), None)

        if position:
            side = trade["side"]
            qty = float(position["contracts"])
            ticker = safe_call_retry(exchange.fetch_ticker, symbol, label=f"fetch_ticker {symbol}")
            exit_price = ticker["last"] if ticker else trade["entry"]

            if not DRY_RUN:
                if side.lower() == "buy":
                    safe_call_retry(exchange.create_market_sell_order, symbol, qty, label=f"close_sell {symbol}")
                else:
                    safe_call_retry(exchange.create_market_buy_order, symbol, qty, label=f"close_buy {symbol}")

            log(f"[SmartSwitch] Closed {symbol} at {exit_price}, qty={qty}", level="INFO")

            # 🧾 Логирование результата
            record_trade_result(symbol, side, trade["entry"], exit_price, result_type="manual")

        else:
            log(f"[SmartSwitch] No open position for {symbol} on exchange", level="WARNING")

        # 🧹 Очистка
        trade_manager.remove_trade(symbol)
        trade_manager.set_last_closed_time(symbol, time.time())
        log(f"[Cleanup] Removed {symbol} from trade manager", level="DEBUG")
        initialize_cache()

    except Exception as e:
        log(f"[SmartSwitch] Error closing real trade {symbol}: {e}", level="ERROR")
        send_telegram_message(f"❌ Failed to close trade {symbol}: {str(e)}", force=True)


def open_real_trade(symbol, direction, qty, entry_price):
    """
    Упрощённая версия входа без сложных расчётов (если нужно).
    """
    try:
        side = "buy" if direction.lower() == "buy" else "sell"
        order = exchange.create_market_order(symbol, side, qty)
        log(f"[Open Trade] Opened {direction} for {symbol}: qty={qty}, entry={entry_price}", level="INFO")
        initialize_cache()
        return order
    except Exception as e:
        log(f"[Open Trade] Failed for {symbol}: {e}", level="ERROR")
        raise


###############################################################################
#                            AUTO PROFIT METHODS                              #
###############################################################################


def run_auto_profit_exit(symbol, side, entry_price, check_interval=5):
    """
    Автопрофит:
    1) Сразу extract_symbol(symbol), чтобы ключ совпал в trade_manager.
    2) Ждём, пока поля 'tp1_price'/'sl_price' появятся в trade_manager
       (даже если там 0.0)
    3) Дальше обычная логика: если profit >= AUTO_CLOSE_PROFIT_THRESHOLD, закрываем сделку.
    """
    import time

    # Приводим символ к формату "ABC/USDC:USDC"
    symbol = normalize_symbol(symbol)

    # Ждём 2 секунды, пока 'tp1_price' и 'sl_price' не пропишутся в trade_manager
    wait_timeout = 2.0
    t0 = time.time()
    while True:
        trade = trade_manager.get_trade(symbol)
        # ВАЖНО: проверяем не .get("tp1_price"), а наличие ключа, т.к. tp1_price может быть == 0.0
        if trade and ("tp1_price" in trade) and ("sl_price" in trade):
            break
        if (time.time() - t0) >= wait_timeout:
            log(f"[Auto-Profit] {symbol} tp1/sl not set after {wait_timeout:.1f}s — aborting auto-profit", level="WARNING")
            return
        time.sleep(0.1)

    log(f"[Auto-Profit] Starting profit check for {symbol}", level="DEBUG")

    while True:
        try:
            trade = trade_manager.get_trade(symbol)
            if not trade:
                log(f"[Auto-Profit] No trade in manager for {symbol}, stopping thread", level="INFO")
                break

            # Если уже tp1_hit — пусть TP2 или SL решают дальнейшее
            if trade.get("tp1_hit"):
                log(f"[Auto-Profit] TP1 for {symbol} hit; letting TP2 handle", level="INFO")
                break

            # Пример лимит по времени: 60 мин
            trade_start = trade.get("start_time")
            if trade_start:
                elapsed = (time.time() - trade_start.timestamp()) / 60
                if elapsed >= 60:
                    log(f"[Auto-Profit] 60-min limit for {symbol} => stopping auto-profit", level="INFO")
                    break

            # Проверяем, не закрыта ли позиция вручную
            pos_size = get_position_size(symbol)
            if pos_size <= 0:
                log(f"[Auto-Profit] {symbol} position closed (manual?), stopping thread", level="INFO")
                break

            # Получаем текущую цену
            ticker = safe_call_retry(exchange.fetch_ticker, symbol)
            if not ticker:
                break
            current_price = ticker["last"]

            # Подсчёт % прибыли
            side_lower = side.lower()
            if side_lower == "buy":
                profit_pct = ((current_price - entry_price) / entry_price) * 100
            else:
                profit_pct = ((entry_price - current_price) / entry_price) * 100

            log(f"[Auto-Profit] {symbol} current profit: {profit_pct:.2f}%", level="DEBUG")

            # Если достигли BONUS_PROFIT_THRESHOLD => закрываем
            if profit_pct >= BONUS_PROFIT_THRESHOLD:
                log(f"[Auto-Profit] 🎉 BONUS PROFIT => Closing {symbol} at +{profit_pct:.2f}%", level="INFO")
                safe_close_trade(exchange, symbol, trade, reason="bonus_profit")
                record_trade_result(symbol, side, entry_price, current_price, "tp")
                send_telegram_message(f"🎉 *Bonus Profit!* {symbol} closed at +{profit_pct:.2f}%!")
                break

            # Если достигли обычного порога
            elif profit_pct >= AUTO_CLOSE_PROFIT_THRESHOLD:
                log(f"[Auto-Profit] ✅ Auto-closing {symbol} at +{profit_pct:.2f}%", level="INFO")
                safe_close_trade(exchange, symbol, trade, reason="auto_profit")
                record_trade_result(symbol, side, entry_price, current_price, "tp")
                send_telegram_message(f"✅ *Auto-closed* {symbol} at +{profit_pct:.2f}%!")
                break

            time.sleep(check_interval)

        except Exception as e:
            log(f"[Auto-Profit] Error for {symbol}: {e}", level="ERROR")
            break


def check_auto_profit(trade, threshold=AUTO_CLOSE_PROFIT_THRESHOLD):
    """
    Если где-то ещё вызывается: проверяем, достигнут ли threshold.
    """
    pass  # (можно не менять, если не используется напрямую)


###############################################################################
#                          MICRO PROFIT / MONITORING                          #
###############################################################################


def run_micro_profit_optimizer(symbol, side, entry_price, qty, start_time, check_interval=5):
    """
    Если позиция очень мала (micro), закрывать при малом профите или по тайм-ауту.
    """
    if not MICRO_PROFIT_ENABLED:
        return

    balance = get_cached_balance()
    position_value = qty * entry_price
    position_percentage = position_value / balance if balance > 0 else 0

    if position_percentage >= MICRO_TRADE_SIZE_THRESHOLD:
        log(f"{symbol} Not a micro-trade ({position_percentage:.2%} of balance)", level="DEBUG")
        return

    base_threshold = MICRO_PROFIT_THRESHOLD
    if position_percentage < 0.15:
        profit_threshold = base_threshold
    elif position_percentage < 0.25:
        profit_threshold = base_threshold * 1.33
    else:
        profit_threshold = base_threshold * 1.67

    log(f"{symbol} 🔍 Starting micro-profit optimizer with {profit_threshold:.1f}% threshold", level="INFO")

    while True:
        try:
            position_size = get_position_size(symbol)
            if position_size <= 0:
                log(f"{symbol} position closed, end micro-profit optimizer", level="DEBUG")
                break

            elapsed_minutes = (time.time() - start_time.timestamp()) / 60
            if elapsed_minutes >= MICRO_TRADE_TIMEOUT_MINUTES:
                ticker = safe_call_retry(exchange.fetch_ticker, symbol, label=f"micro_profit_optimizer {symbol}")
                if not ticker:
                    log(f"Failed to fetch price for {symbol} in micro-profit", level="WARNING")
                    break

                current_price = ticker["last"]
                if side.lower() == "buy":
                    profit_percent = ((current_price - entry_price) / entry_price) * 100
                else:
                    profit_percent = ((entry_price - current_price) / entry_price) * 100

                if profit_percent >= profit_threshold:
                    log(f"{symbol} 🕒 Micro-trade timeout => +{profit_percent:.2f}% profit", level="INFO")
                    trade_data = trade_manager.get_trade(symbol)
                    if trade_data:
                        safe_close_trade(exchange, symbol, trade_data, reason="micro_profit")
                        send_telegram_message(f"⏰ Micro-profit: {symbol} closed +{profit_percent:.2f}%", force=True)
                else:
                    log(f"{symbol} ❎ Micro-trade timeout => only {profit_percent:.2f}%, stopping", level="INFO")
                break

            time.sleep(check_interval)
        except Exception as e:
            log(f"[ERROR] Micro-profit {symbol}: {e}", level="ERROR")
            break


def monitor_active_position(symbol, side, entry_price, initial_qty, start_time):
    """
    Dynamic position management with full exit logic from OptiFlow v3.2 FINAL:
    Step TP, fallback, break-even, trailing, soft-exit, and max_hold enforcement.
    """
    import time

    from core.exchange_init import exchange
    from core.runtime_stats import record_trade_result
    from core.trade_engine import get_position_size, trade_manager
    from telegram.telegram_utils import send_telegram_message
    from utils_core import fetch_ohlcv, get_runtime_config, safe_call_retry
    from utils_logging import log

    config = get_runtime_config()
    _MAX_HOLD_MINUTES = config.get("max_hold_minutes", 60)
    SL_PRIORITY = config.get("sl_must_trigger_first", False)
    min_step_hit_required = config.get("minimum_step_profit_hit_required", False)
    allow_soft_exit_at_zero = config.get("soft_exit_allow_at_zero", False)

    step_profit_levels = config.get("step_tp_levels", [0.10, 0.20, 0.30])
    step_tp_sizes = config.get("step_tp_sizes", [0.1] * len(step_profit_levels))
    step_hits = [False] * len(step_profit_levels)
    tp_touch_flags = [False] * len(step_profit_levels)
    tp_touch_times = [None] * len(step_profit_levels)

    break_even_set = False
    trailing_tp_active = False
    last_fetched_price = entry_price

    is_buy = side.lower() == "buy"
    is_sell = not is_buy

    while True:
        try:
            trade = trade_manager.get_trade(symbol)
            if not trade:
                log(f"{symbol} => trade removed, stop dynamic monitoring", level="DEBUG")
                break

            tp_prices = trade.get("tp_prices", [])
            sl_price = trade.get("sl_price")

            if not tp_prices or len(tp_prices) < len(step_profit_levels):
                log(f"[Monitor] {symbol}: TP prices missing or incomplete → skipping step TP logic", level="WARNING")
                step_profit_levels = []
                step_tp_sizes = []
                step_hits = []
                tp_touch_flags = []
                tp_touch_times = []

            break_even_set = trade.get("break_even_set", False)
            trailing_tp_active = trade.get("trailing_tp_active", False)

            current_position = get_position_size(symbol)
            if not isinstance(current_position, (int, float)) or current_position <= 0:
                elapsed = time.time() - start_time.timestamp()
                if elapsed < 15:
                    log(f"[Monitor] {symbol} ⚠️ Position disappeared too fast (<15s)", level="WARNING")
                    return

                reason_type = "manual"
                if trade.get("sl_hit"):
                    reason_type = "sl"
                elif trade.get("tp2_hit"):
                    reason_type = "tp2"
                elif trade.get("tp1_hit"):
                    reason_type = "tp1"
                elif trade.get("soft_exit_hit"):
                    reason_type = "soft_exit"
                elif trade.get("post_hold_hit"):
                    reason_type = "post_hold"

                log(f"[Monitor] {symbol} position fully closed, reason: {reason_type}", level="INFO")
                record_trade_result(symbol, side, entry_price, last_fetched_price, result_type=reason_type)
                break

            price_data = safe_call_retry(exchange.fetch_ticker, symbol, label=f"monitor_position {symbol}")
            if not price_data:
                log(f"{symbol} monitor: failed to fetch price, retry later", level="WARNING")
                time.sleep(5)
                continue

            current_price = price_data["last"]
            last_fetched_price = current_price
            profit_percent = ((current_price - entry_price) / entry_price) * 100 if is_buy else ((entry_price - current_price) / entry_price) * 100
            profit_usd = abs(current_price - entry_price) * current_position
            elapsed = time.time() - start_time.timestamp()

            if SL_PRIORITY and not trade.get("sl_hit") and sl_price:
                if (is_buy and current_price < sl_price) or (is_sell and current_price > sl_price):
                    log(f"[SL-Priority] {symbol}: Waiting for SL trigger → price={current_price:.4f}, SL={sl_price:.4f}", level="DEBUG")
                    time.sleep(1)
                    continue

            for i, level in enumerate(step_profit_levels):
                tp_price = entry_price * (1 + level) if is_buy else entry_price * (1 - level)
                if not step_hits[i] and profit_percent >= (level * 100):
                    step_hits[i] = True
                    reduce_qty = round(current_position * step_tp_sizes[i], 6)
                    if reduce_qty >= 0.001:
                        safe_call_retry(exchange.create_market_order, symbol, "sell" if is_buy else "buy", reduce_qty, {"reduceOnly": True})
                        if i == 0:
                            trade_manager.update_trade(symbol, "tp1_hit", True)
                        if i == 1:
                            trade_manager.update_trade(symbol, "tp2_hit", True)
                        send_telegram_message(f"🌟 Step TP +{int(level * 100)}% → {symbol} partial close ({reduce_qty:.2f})")

                elif not tp_touch_flags[i] and ((is_buy and current_price >= tp_price) or (is_sell and current_price <= tp_price)):
                    tp_touch_flags[i] = True
                    tp_touch_times[i] = time.time()
                    send_telegram_message(f"⚠️ {symbol} touched TP{i+1} but order not filled")
                elif tp_touch_flags[i] and not step_hits[i] and time.time() - tp_touch_times[i] > 5:
                    reduce_qty = round(current_position * step_tp_sizes[i], 6)
                    safe_call_retry(exchange.create_market_order, symbol, "sell" if is_buy else "buy", reduce_qty, {"reduceOnly": True})
                    step_hits[i] = True
                    send_telegram_message(f"✅ {symbol} fallback TP{i+1} closed by market ({reduce_qty:.2f})")

            if not break_even_set and (profit_percent >= 1.5 or trade.get("tp1_hit")):
                new_sl = round(entry_price * 1.001, 6) if is_buy else round(entry_price * 0.999, 6)
                open_orders = exchange.fetch_open_orders(symbol)
                for o in open_orders:
                    if o["type"].upper() == "STOP_MARKET":
                        exchange.cancel_order(o["id"], symbol)
                safe_call_retry(exchange.create_order, symbol, "STOP_MARKET", "sell" if is_buy else "buy", current_position, None, {"stopPrice": new_sl, "reduceOnly": True})
                trade_manager.update_trade(symbol, "break_even_set", True)
                trade_manager.update_trade(symbol, "sl_price", new_sl)
                send_telegram_message(f"🔒 SL moved to break-even for {symbol}")

            if not trailing_tp_active and not trade.get("tp1_hit") and profit_percent > 2.5:
                ohlcv = fetch_ohlcv(symbol, timeframe="5m", limit=12)
                closes = [c[4] for c in ohlcv[-6:]]
                momentum = closes[-1] > closes[-2] > closes[-3] if is_buy else closes[-1] < closes[-2] < closes[-3]
                if momentum:
                    tp1 = current_price * 1.004 if is_buy else current_price * 0.996
                    tp2 = current_price * 1.007 if is_buy else current_price * 0.993
                    open_orders = exchange.fetch_open_orders(symbol)
                    for o in open_orders:
                        if o["type"].upper() == "LIMIT":
                            exchange.cancel_order(o["id"], symbol)
                    safe_call_retry(exchange.create_limit_order, symbol, "sell" if is_buy else "buy", current_position, tp1, {"reduceOnly": True, "postOnly": True})
                    safe_call_retry(exchange.create_limit_order, symbol, "sell" if is_buy else "buy", current_position * 0.2, tp2, {"reduceOnly": True, "postOnly": True})
                    trade_manager.update_trade(symbol, "trailing_tp_active", True)
                    send_telegram_message(f"🚀 Trailing TP moved higher for {symbol}")

            if elapsed > 600 and not any(step_hits):
                if (profit_usd >= 0.10) or (allow_soft_exit_at_zero and profit_usd >= 0) or (min_step_hit_required and any(step_hits)):
                    safe_call_retry(exchange.create_market_order, symbol, "sell" if is_buy else "buy", current_position, {"reduceOnly": True})
                    trade_manager.update_trade(symbol, "soft_exit_hit", True)
                    record_trade_result(symbol, side, entry_price, current_price, result_type="soft_exit")
                    send_telegram_message(f"💸 Soft exit: {symbol} closed at ${profit_usd:.2f} after {elapsed/60:.1f} min")
                    break

            if elapsed > (_MAX_HOLD_MINUTES * 60) and profit_percent < 0:
                recovery_start = time.time()
                while time.time() - recovery_start < 300:
                    price_data = safe_call_retry(exchange.fetch_ticker, symbol, label=f"post_hold_check {symbol}")
                    if price_data:
                        current_price = price_data["last"]
                        profit_percent = ((current_price - entry_price) / entry_price) * 100 if is_buy else ((entry_price - current_price) / entry_price) * 100
                        if profit_percent >= 0:
                            safe_call_retry(exchange.create_market_order, symbol, "sell" if is_buy else "buy", current_position, {"reduceOnly": True})
                            trade_manager.update_trade(symbol, "post_hold_hit", True)
                            record_trade_result(symbol, side, entry_price, current_price, result_type="post_hold")
                            send_telegram_message(f"🕓 Post-hold recovery: {symbol} closed at breakeven")
                            break
                    time.sleep(5)

            time.sleep(1)

        except Exception as e:
            log(f"Error in monitoring {symbol}: {e}", level="ERROR")
            time.sleep(5)


def handle_panic(stop_event):
    """
    Закрывает все позиции максимально быстро и завершает цикл.
    """
    import time

    from core.binance_api import get_open_positions
    from core.trade_engine import close_real_trade
    from telegram.telegram_utils import send_telegram_message
    from utils_logging import log

    log("[PANIC] Closing ALL positions now", level="WARNING")
    send_telegram_message("🚨 *PANIC MODE*: Closing ALL positions immediately...", force=True)

    try:
        positions = get_open_positions()
        for pos in positions:
            try:
                close_real_trade(pos["symbol"])
                log(f"[PANIC] Closing {pos['symbol']}", level="INFO")
            except Exception as e:
                log(f"[PANIC] Error closing {pos['symbol']}: {e}", level="ERROR")
    except Exception as e:
        log(f"[PANIC] Failed to fetch positions: {e}", level="ERROR")
        send_telegram_message(f"⚠️ PANIC error while fetching positions:\n{e}", force=True)

    # Установка флага остановки
    stop_event.set()
    log("[PANIC] stop_event set. Bot will shut down ASAP.", level="INFO")

    # 🔄 Повторная проверка, закрылось ли всё
    for i in range(10):  # 10 попыток по 3 секунды = 30 сек максимум
        try:
            positions = get_open_positions()
            still_open = [p for p in positions if float(p.get("contracts", 0)) > 0]
            if not still_open:
                send_telegram_message("✅ All positions force-closed successfully.", force=True)
                log("[PANIC] All positions confirmed closed.", level="INFO")
                return
            else:
                log(f"[PANIC] Still open after attempt {i+1}: {[p['symbol'] for p in still_open]}", level="WARNING")
        except Exception as e:
            log(f"[PANIC] Retry check error: {e}", level="ERROR")
        time.sleep(3)

    # Если всё ещё открыты — сообщаем
    send_telegram_message("⚠️ Some positions may still be open after PANIC.", force=True)
    log("[PANIC] Positions remained open after retries.", level="ERROR")
