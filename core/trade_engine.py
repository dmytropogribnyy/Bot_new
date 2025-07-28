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
from utils_core import get_cached_balance, load_state, normalize_symbol, safe_call_retry
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

    def get_active_trades(self) -> list[str]:
        with self._lock:
            return list(self._trades.keys())


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
        rf, _ = get_symbol_risk_factor(symbol)  # ✅ Исправлено
        risk_factor = rf
        log(f"[Risk] Risk factor for {symbol}: {risk_factor:.2f}", level="DEBUG")

    # === Расчёт итогового риска
    risk_amount = balance * base_risk_pct * risk_multiplier * risk_factor

    # === Фикс #4.3: минимальный риск, если < MIN_NOTIONAL_OPEN
    min_notional_open = cfg.get("MIN_NOTIONAL_OPEN", 20.0)
    if risk_amount < min_notional_open:
        adjusted_risk = min_notional_open * 1.5
        log(f"[Risk] risk_amount ${risk_amount:.2f} < MIN_NOTIONAL_OPEN → forcing to ${adjusted_risk:.2f}", level="WARNING")
        risk_amount = adjusted_risk

    log(f"[Risk] balance={balance:.2f}, base_pct={base_risk_pct:.4f}, multiplier={risk_multiplier}, factor={risk_factor:.2f} → risk=${risk_amount:.2f}, SL={effective_sl:.4f}", level="DEBUG")

    return risk_amount, effective_sl


def calculate_position_size(symbol, entry_price, balance, leverage, runtime_config=None, risk_amount=None):
    """
    Рассчитывает размер позиции с учётом:
    - risk_amount (если передан извне — используется напрямую)
    - base_risk_pct и balance, если risk_amount не задан
    - max_margin_percent на сделку
    - max_capital_utilization_pct на все сделки
    - минимального нотионала и min_trade_qty
    Возвращает (qty, risk_amount)
    """
    from common.config_loader import get_dynamic_min_notional
    from core.tp_utils import safe_round_and_validate
    from utils_core import get_runtime_config, get_total_position_value
    from utils_logging import log

    if runtime_config is None:
        runtime_config = get_runtime_config()

    base_risk_pct = runtime_config.get("base_risk_pct", 0.01)
    max_capital_utilization_pct = runtime_config.get("max_capital_utilization_pct", 0.7)
    max_margin_percent = runtime_config.get("max_margin_percent", 0.5)
    min_trade_qty = runtime_config.get("min_trade_qty", 0.001)
    auto_reduce = runtime_config.get("auto_reduce_entry_if_risk_exceeds", False)

    if entry_price <= 0:
        log(f"[ERROR] Invalid entry price {entry_price} for {symbol}", level="ERROR")
        return 0.0, 0.0

    # ✅ Используем risk_amount, если задан, иначе рассчитываем
    if risk_amount is None:
        risk_amount = balance * base_risk_pct

    # Boost для малых балансов (FIX для qty=0.0)
    if risk_amount < 20.0:
        risk_amount = min(20.0, balance * 0.1)  # минимум $20 или 10% баланса
        log(f"[Risk] Boosted risk_amount to ${risk_amount:.2f} for small balance", level="INFO")

    max_trade_value = balance * max_margin_percent

    qty_raw = (risk_amount * leverage) / entry_price
    notional = qty_raw * entry_price
    log(f"[QTY CALC] {symbol} → initial qty={qty_raw:.6f}, notional={notional:.2f}", level="DEBUG")

    if notional > max_trade_value:
        qty_raw = max_trade_value / entry_price
        notional = qty_raw * entry_price
        log(f"[CAP LIMIT] {symbol}: reduced qty to fit max_margin_percent ({max_margin_percent * 100:.1f}%)", level="WARNING")

    total_used = get_total_position_value()
    projected_total = total_used + notional
    max_total = balance * max_capital_utilization_pct

    if projected_total > max_total:
        if auto_reduce:
            allowed_notional = max_total - total_used
            qty_raw = allowed_notional / entry_price
            log(f"[AUTO REDUCE] {symbol}: adjusted qty to fit capital usage", level="WARNING")
        else:
            log(f"[BLOCKED] {symbol}: capital usage {projected_total:.2f} > {max_total:.2f} (limit {max_capital_utilization_pct * 100:.0f}%)", level="WARNING")
            return 0.0, 0.0

    qty = safe_round_and_validate(symbol, qty_raw)
    if not qty:
        log(f"[QTY] {symbol}: Qty is invalid after rounding — skipping", level="WARNING")
        return 0.0, 0.0

    log(f"[QTY ROUND] {symbol} raw={qty_raw:.6f} → rounded={qty:.6f}", level="DEBUG")

    min_notional_dynamic = get_dynamic_min_notional(symbol)
    if qty < min_trade_qty:
        fallback_qty = min_trade_qty
        fallback_notional = fallback_qty * entry_price
        projected_total_fallback = total_used + fallback_notional

        if fallback_notional >= min_notional_dynamic and projected_total_fallback <= max_total:
            log(f"[Fallback] {symbol}: calculated qty={qty:.6f} → using fallback qty={fallback_qty:.6f}", level="WARNING")
            return fallback_qty, fallback_qty * entry_price / leverage
        else:
            log(f"[REJECTED] {symbol}: qty {qty:.6f} < min_trade_qty {min_trade_qty} and can't boost safely (dynamic min {min_notional_dynamic:.2f})", level="WARNING")
            return 0.0, 0.0

    if qty < min_trade_qty and notional >= min_notional_dynamic:
        log(f"[QTY NOTICE] {symbol}: qty {qty:.6f} < min_trade_qty but passes notional — fallback allowed", level="INFO")

    notional = qty * entry_price
    if notional < min_notional_dynamic:
        log(f"[REJECTED] {symbol}: final notional {notional:.2f} < dynamic min {min_notional_dynamic:.2f}", level="WARNING")
        return 0.0, 0.0

    if qty == min_trade_qty:
        log(f"[NOTICE] {symbol}: qty at min_trade_qty threshold ({qty:.6f}) — monitor for TP/SL placement", level="INFO")

    log(f"[QTY OK] {symbol} → qty={qty:.6f}, notional={notional:.2f}, risk={risk_amount:.2f}", level="DEBUG")
    return qty, risk_amount


def get_position_size(symbol):
    """
    Возвращает объём открытой позиции (в контрактах) для заданного symbol.
    Проверяет contracts / positionAmt / amount. Возвращает abs(amount).
    Логирует малые позиции отдельно для мониторинга.
    """
    from utils_core import get_cached_positions, normalize_symbol
    from utils_logging import log

    try:
        positions = get_cached_positions()
        if not positions:
            log("[get_position_size] No cached positions found — possible desync", level="WARNING")
            return 0

        symbol_norm = normalize_symbol(symbol)
        log(f"[get_position_size] Looking for {symbol_norm} in {len(positions)} positions", level="DEBUG")

        for pos in positions:
            pos_symbol = normalize_symbol(pos.get("symbol", ""))
            if pos_symbol != symbol_norm:
                continue

            raw_value = pos.get("contracts") or pos.get("positionAmt") or pos.get("amount")
            if raw_value is None:
                log(f"[get_position_size] Missing size key for {symbol}: no contracts/positionAmt/amount", level="WARNING")
                continue

            try:
                amount = float(raw_value)
                abs_amount = abs(amount)
                if abs_amount > 0:
                    log(f"[get_position_size] {symbol} → {abs_amount} contracts", level="DEBUG")
                    if abs_amount <= 0.0008:
                        log(f"[get_position_size] {symbol}: small position detected ({abs_amount:.6f}) — monitoring only", level="INFO")
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

    with _active_trades_save_lock:
        try:
            with open("data/active_trades.json", "w", encoding="utf-8") as f:
                json.dump(dict(trade_manager._trades), f, indent=2, default=str)
            log("[Save] active_trades.json updated", level="DEBUG")
        except Exception as e:
            log(f"[ERROR] Failed to save active_trades.json: {e}", level="ERROR")


def enter_trade(symbol, side, is_reentry=False, breakdown=None, pair_type="unknown"):
    """
    Финальная версия enter_trade (v3.8 Stage 2.2):
    - Сохраняет структуру 1.3.3 + Stage 1
    - Подтверждение позиции через Confirm Loop с 10 попытками
    - Обновление qty на подтверждённый
    - Защита от tp_sl_fail и fallback закрытия
    """
    import time
    from threading import Lock, Thread

    import numpy as np

    from common.config_loader import DRY_RUN, MAX_OPEN_ORDERS, MIN_NOTIONAL_OPEN, SHORT_TERM_MODE, get_priority_small_balance_pairs, get_runtime_config
    from common.leverage_config import get_leverage_for_symbol
    from core.binance_api import convert_symbol, create_safe_market_order
    from core.component_tracker import log_component_data
    from core.engine_controller import sync_open_positions
    from core.entry_logger import log_entry
    from core.exchange_init import exchange
    from core.fail_stats_tracker import get_symbol_risk_factor
    from core.position_manager import check_entry_allowed
    from core.runtime_stats import update_trade_count
    from core.signal_utils import passes_1plus1
    from core.strategy import fetch_data_multiframe
    from core.tp_utils import calculate_tp_levels, place_take_profit_and_stop_loss_orders
    from telegram.telegram_utils import send_telegram_message
    from utils_core import api_cache, cache_lock, extract_symbol, get_cached_balance, is_optimal_trading_hour, safe_call_retry
    from utils_logging import log, now

    global open_positions_count, dry_run_positions_count
    open_positions_lock = Lock()

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
            send_telegram_message(f"🚱 Skipping {symbol}: failed passes_1plus1 check", force=True)
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
        if rf < min_rf:
            log(f"[Skip] {symbol}: risk_factor {rf:.2f} < min_risk_factor {min_rf}", level="INFO")
            send_telegram_message(f"⚠️ Skipping {symbol}: risk factor too low ({rf:.2f} < {min_rf})", force=True)
            return False

        atr_percent = ticker.get("atr_percent")

        risk_amount, effective_sl = calculate_risk_amount(balance, symbol=symbol, atr_percent=atr_percent)
        if effective_sl <= 0:
            log(f"[Risk] Invalid effective SL for {symbol}", level="ERROR")
            return False

        leverage = get_leverage_for_symbol(symbol)
        qty, _ = calculate_position_size(symbol, entry_price, balance, leverage, risk_amount=risk_amount)
        cfg = get_runtime_config()
        min_qty = cfg.get("min_trade_qty", 0.001)

        if qty is None or qty <= 0:
            log(f"[ENTER] ❌ Rejected {symbol}: qty={qty} is invalid (<= 0)", level="WARNING")
            send_telegram_message(f"⚠️ Skipping {symbol}: qty={qty} is invalid (<= 0)", force=True)
            return False

        qty = round(qty, 6)
        if qty < min_qty:
            log(f"[ENTER] ❌ qty={qty:.6f} < min_trade_qty={min_qty} → skipping {symbol}", level="WARNING")
            send_telegram_message(f"⚠️ Skipping {symbol}: qty={qty:.4f} < min_trade_qty={min_qty}", force=True)
            return False

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

        tp1, tp2, sl_price, share1, share2, tp3_share = calculate_tp_levels(entry_price, side, df=df)
        if any(x is None or (isinstance(x, float) and np.isnan(x)) for x in (tp1, sl_price, share1)) or tp1 <= 0:
            log(f"[TPCheck] ❌ Invalid TP/SL for {symbol} — aborting entry", level="WARNING")
            send_telegram_message(f"⚠️ Aborting entry {symbol}: invalid TP/SL", force=True)
            return False

        tp3 = round(tp2 + (tp2 - tp1), 6) if side.lower() == "buy" else round(tp2 - (tp1 - tp2), 6)
        tp_prices = [tp1, tp2, tp3]

        result = create_safe_market_order(api_symbol, side.lower(), qty)
        if not result["success"] or result.get("filled_qty", 0) == 0:
            log("[Enter Trade] Market order failed or 0 filled qty", level="ERROR")
            send_telegram_message(f"❌ Market order issue for {symbol}", force=True)
            return False

        # ✅ Критичный блок подтверждения позиции
        actual_qty = result.get("filled_qty", qty)
        entry_price = result.get("avg_price", entry_price)
        order_id = result.get("result", {}).get("id")

        max_retries = 10
        position_confirmed = False
        confirmed_qty = 0

        log(f"[Enter Trade] Waiting for position confirmation for {symbol}...", level="INFO")

        for i in range(max_retries):
            time.sleep(0.5)
            with cache_lock:
                api_cache["positions"]["timestamp"] = 0
            sync_open_positions()
            current_qty = get_position_size(symbol)
            if current_qty > 0:
                position_confirmed = True
                confirmed_qty = current_qty
                log(f"[Enter Trade] Position confirmed: {symbol} qty={confirmed_qty}", level="INFO")
                break
            if i == 4:
                exchange.load_markets()
                log(f"[Enter Trade] Reloaded markets, attempt {i + 1}/{max_retries}", level="DEBUG")

        if not position_confirmed:
            log(f"[Enter Trade] WARNING: Position not confirmed after {max_retries} attempts", level="WARNING")
            send_telegram_message(f"⚠️ {symbol}: Position not confirmed, using order qty for TP/SL")
            confirmed_qty = actual_qty
        qty = confirmed_qty
        log(f"[Enter Trade] Using qty={qty} for TP/SL placement", level="INFO")
        time.sleep(2)

        opened_position = True
        with open_positions_lock:
            if DRY_RUN:
                dry_run_positions_count += 1
            else:
                open_positions_count += 1

        update_trade_count()

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
            "tp3_share": tp3_share,
            "tp_total_qty": qty,
            "tp_sl_success": False,
            "tp_fallback_used": False,
            "order_id": order_id,
        }

        trade_manager.add_trade(symbol, trade_data)
        save_active_trades()

        try:
            if DRY_RUN:
                success = True
                trade_manager.update_trade(symbol, "tp_sl_success", success)
                trade_manager.update_trade(symbol, "tp_fallback_used", False)
            else:
                success = place_take_profit_and_stop_loss_orders(api_symbol, side, entry_price, qty, tp_prices, sl_price)
                trade_manager.update_trade(symbol, "tp_sl_success", success)
                trade_manager.update_trade(symbol, "tp_fallback_used", not success)
                trade_manager.update_trade(symbol, "tp_total_qty", qty)

            if not success:
                if get_runtime_config().get("ABORT_IF_NO_TP", True):
                    close_real_trade(symbol, reason="tp_sl_fail")
                    record_trade_result(symbol, side, entry_price, entry_price, result_type="manual")
                    send_telegram_message(f"⚠️ {symbol}: TP/SL failed — position closed", force=True)
                    return False

        except Exception as e:
            log(f"[TP/SL] Error placing TP/SL: {e}", level="ERROR")
            send_telegram_message(f"⚠️ TP/SL placement failed for {symbol}: {e}", force=True)

        log_entry(trade_data, status="SUCCESS")
        send_telegram_message(f"🚀 ENTER {symbol} {side.upper()} qty={qty:.4f} @ {entry_price:.4f}", force=True)

        Thread(target=monitor_active_position, args=(symbol, side, entry_price, qty, start_time), daemon=True).start()
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
    - Уведомляет в Telegram (включая TP1/TP2-hit отдельно)
    - Удаляет позицию из активных
    - Возвращает dict с итогами
    - FIX #4: Динамический порог минимальной прибыли
    """
    import math
    import time
    import traceback

    import pandas as pd

    from core.component_tracker import log_component_data
    from core.exchange_init import exchange
    from core.runtime_state import get_loss_streak, increment_loss_streak, pause_symbol, reset_loss_streak
    from telegram.telegram_utils import send_telegram_message
    from tp_logger import log_trade_result as csv_log_trade_result
    from utils_core import get_min_net_profit, normalize_symbol
    from utils_logging import log

    symbol = normalize_symbol(symbol)
    caller_info = traceback.format_stack()[-2]
    global open_positions_count, dry_run_positions_count

    log(f"[DEBUG] record_trade_result for {symbol}, {result_type}, caller: {caller_info}", level="DEBUG")

    # === Предотвращаем повторную запись
    trade_key = f"{symbol}_{result_type}_{entry_price}_{round(exit_price, 4)}"
    with logged_trades_lock:
        if trade_key in logged_trades:
            log(f"[DEBUG] Skipping duplicate logging {symbol}, {result_type}", level="DEBUG")
            return
        logged_trades.add(trade_key)

    # === Снижаем счётчик активных позиций
    with open_positions_lock:
        if DRY_RUN:
            dry_run_positions_count -= 1
        else:
            open_positions_count -= 1

    trade = trade_manager.get_trade(symbol)
    if not trade or trade.get("closed_logged"):
        log(f"[DEBUG] {symbol} already recorded or not found", level="DEBUG")
        return
    trade["closed_logged"] = True

    # === Параметры TP/SL
    tp_total_qty = float(trade.get("tp_total_qty") or 0.0)
    tp_fallback_used = bool(trade.get("tp_fallback_used"))
    tp_sl_success = trade.get("tp_sl_success", False)
    commission = float(trade.get("commission") or 0.0)

    if tp_fallback_used:
        send_telegram_message(f"🔭️ {symbol}: TP fallback mode was used", force=True)

    # === Обоснование причины выхода
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

    # === Продолжительность
    start = trade.get("start_time")
    if isinstance(start, str):
        try:
            start = pd.to_datetime(start)
        except Exception:
            log(f"[WARN] Failed to parse start_time for {symbol}", level="WARNING")
            start = pd.Timestamp.now()
    duration = int((time.time() - start.timestamp()) / 60)

    # === Расчёт прибыли
    qty = float(trade.get("qty") or 0.0)
    atr = float(trade.get("atr") or 0.0)
    pair_type = trade.get("pair_type", "unknown")
    breakdown = trade.get("breakdown", {})
    signal_score = breakdown.get("signal_score", 0.0)

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

    # ✅ FIX #4: Динамический порог минимальной прибыли из runtime config
    min_profit_threshold = get_min_net_profit()
    log(f"[TP Filter] Using min_profit_threshold={min_profit_threshold:.4f} from runtime config", level="DEBUG")

    if trade.get("tp1_hit") and net_absolute_profit < min_profit_threshold:
        log(f"[TP1 Filtered] {symbol}: TP1 hit ignored due to net_profit={net_absolute_profit:.4f} < {min_profit_threshold:.4f}", level="WARNING")
        trade["tp1_hit"] = False

    if trade.get("tp2_hit") and net_absolute_profit < min_profit_threshold:
        log(f"[TP2 Filtered] {symbol}: TP2 hit ignored due to net_profit={net_absolute_profit:.4f} < {min_profit_threshold:.4f}", level="WARNING")
        trade["tp2_hit"] = False

    log(f"[PnL] {symbol} entry={entry_price}, exit={exit_price}, qty={qty}, gross={absolute_profit:.2f}, net={net_absolute_profit:.2f}, fee={commission:.2f}", level="DEBUG")
    log(f"[FinalResult] {symbol} exit={exit_reason}, final={final_result_type}, pnl={net_pnl_percent:.4f}%, score={signal_score:.4f}", level="INFO")

    # === Успешность сигнала
    is_successful = (exit_reason.startswith("tp") or final_result_type == "trailing_tp") and net_absolute_profit > 0
    log_component_data(symbol, breakdown, is_successful=is_successful)

    # === Telegram: TP-хиты
    if trade.get("tp1_hit") and not trade.get("tp2_hit"):
        send_telegram_message(f"✅ *TP1 HIT*: {symbol} — partial target reached", force=True)
    if trade.get("tp2_hit"):
        send_telegram_message(f"✅ *TP2 HIT*: {symbol} — major target reached", force=True)

    # === CSV запись
    try:
        csv_log_trade_result(
            symbol=symbol,
            direction=side.upper(),
            entry_price=entry_price,
            exit_price=exit_price,
            qty=qty,
            tp1_hit=trade.get("tp1_hit", False),
            tp2_hit=trade.get("tp2_hit", False),
            sl_hit=trade.get("sl_hit", False),
            pnl_percent=round(net_pnl_percent, 4),
            duration_minutes=duration,
            result_type=final_result_type,
            exit_reason=exit_reason,
            atr=atr,
            pair_type=pair_type,
            commission=commission,
            net_pnl=round(net_pnl_percent, 4),
            absolute_profit=round(net_absolute_profit, 2),
            tp_sl_success=tp_sl_success,
            tp_total_qty=tp_total_qty,
            tp_fallback_used=tp_fallback_used,
        )
    except Exception as e:
        log(f"[ERROR] Failed to log trade to CSV: {e}", level="ERROR")

    # === Адаптация min_profit_threshold
    # if is_successful:
    #     prev = get_min_net_profit()
    #     if prev < 0.30:
    #         new_val = round(min(0.30, prev + 0.10), 2)
    #         update_runtime_config({"min_profit_threshold": new_val})
    #         log(f"[ProfitAdapt] min_profit_threshold updated to {new_val}", level="INFO")
    # elif result_type == "sl" and net_absolute_profit < 0:
    #     update_runtime_config({"min_profit_threshold": 0.10})
    #     log("[ProfitAdapt] Reset min_profit_threshold to 0.10 after SL", level="WARNING")

    # === SL streak & pause
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

    # === Telegram итоги
    icon = "🟢" if final_result_type in ["tp", "tp1", "tp2", "trailing_tp"] else "🔴" if final_result_type == "sl" else "⚪"
    msg = (
        f"{icon} *Trade Closed* [{final_result_type.upper()} / {exit_reason.upper()}]\n"
        f"• {symbol} — {side.upper()}\n"
        f"• Entry: {round(entry_price, 4)} → Exit: {round(exit_price, 4)}\n"
        f"• PnL: {round(net_pnl_percent, 4)}% | Gross: ${round(absolute_profit, 2)} | Net: ${round(net_absolute_profit, 2)}\n"
        f"• Held: {duration} min | Time: {pd.Timestamp.now().strftime('%H:%M:%S')}\n"
        f"• Score: {signal_score:.4f}"
    )
    send_telegram_message(msg, force=True)

    # === Очистка ордеров
    try:
        exchange.cancel_all_orders(symbol)
        log(f"[Cleanup] Cancelled all remaining orders for {symbol}", level="INFO")
    except Exception as e:
        log(f"[Cleanup] Failed to cancel orders for {symbol}: {e}", level="WARNING")

    # === Удаление позиции
    trade_manager.remove_trade(symbol)
    log(f"[Cleanup] Removed {symbol} from active trades", level="DEBUG")
    save_active_trades()
    log(f"[Save] active_trades.json updated after closing {symbol}", level="DEBUG")

    return {
        "symbol": symbol,
        "exit_reason": exit_reason,
        "result_type": final_result_type,
        "net_usd": round(net_absolute_profit, 2),
        "pnl_percent": round(net_pnl_percent, 4),
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


def close_real_trade(symbol: str, reason: str = "manual") -> bool:
    """
    Гарантированное закрытие позиции:
    - Пытается закрыть до 5 раз (market → fallback IOC limit)
    - Проверяет остаток позиции после каждой попытки
    - Вызывает record_trade_result только при успехе
    - Записывает в hang_trades.json при ошибке
    - FIX #2: полностью очищает кеш после успешного закрытия
    """
    import json
    import time
    from pathlib import Path

    from core.exchange_init import exchange
    from core.trade_engine import save_active_trades, trade_manager
    from telegram.telegram_utils import send_telegram_message
    from utils_core import api_cache, cache_lock, normalize_symbol, safe_call_retry
    from utils_logging import log

    global DRY_RUN

    symbol = normalize_symbol(symbol)
    log(f"[Close] Starting close for {symbol}, reason={reason}", level="INFO")

    trade = trade_manager.get_trade(symbol)
    if not trade:
        log(f"[Close] No active trade for {symbol}", level="WARNING")
        return False

    side = trade.get("side", "buy")
    entry_price = trade.get("entry", 0)

    # === Cancel all open orders
    try:
        orders = exchange.fetch_open_orders(symbol)
        for order in orders:
            try:
                exchange.cancel_order(order["id"], symbol)
                log(f"[Close] Cancelled order {order['id']} for {symbol}", level="DEBUG")
            except Exception as e:
                log(f"[Close] Failed to cancel order: {e}", level="WARNING")
    except Exception as e:
        log(f"[Close] Error fetching orders: {e}", level="WARNING")

    max_attempts = 5
    close_success = False
    exit_price = None

    for attempt in range(max_attempts):
        try:
            current_qty = get_position_size(symbol)
            if current_qty < 1e-6:
                log(f"[Close] Position already closed for {symbol}", level="INFO")
                close_success = True
                break

            ticker = safe_call_retry(exchange.fetch_ticker, symbol)
            current_price = ticker.get("last") if ticker else entry_price

            log(f"[Close] Attempt {attempt + 1}: closing {symbol} qty={current_qty:.6f}", level="INFO")
            close_side = "sell" if side.lower() == "buy" else "buy"

            if DRY_RUN:
                log(f"[Close] DRY_RUN mode - simulating close for {symbol}", level="INFO")
                close_success = True
                exit_price = current_price
                break

            try:
                order = exchange.create_market_order(symbol, close_side, current_qty, params={"reduceOnly": True})
                exit_price = order.get("average", order.get("price", current_price))
                time.sleep(2)
                remaining = get_position_size(symbol)

                if remaining < 1e-6:
                    log(f"[Close] Successfully closed {symbol} at {exit_price}", level="INFO")
                    close_success = True
                    break
                else:
                    log(f"[Close] Still open: {remaining:.6f}", level="WARNING")

            except Exception as e:
                log(f"[Close] Market order failed for {symbol}: {e}", level="ERROR")

                # Fallback: limit order IOC
                try:
                    limit_price = current_price * 0.998 if close_side == "sell" else current_price * 1.002
                    order = exchange.create_limit_order(symbol, close_side, current_qty, limit_price, params={"reduceOnly": True, "timeInForce": "IOC"})
                    exit_price = order.get("average", limit_price)
                    time.sleep(2)
                    remaining = get_position_size(symbol)

                    if remaining < 1e-6:
                        log(f"[Close] Fallback IOC close success for {symbol}", level="INFO")
                        close_success = True
                        break
                    else:
                        log(f"[Close] Fallback IOC: still open: {remaining:.6f}", level="WARNING")

                except Exception as e2:
                    log(f"[Close] Fallback IOC failed: {e2}", level="ERROR")

        except Exception as e:
            log(f"[Close] Attempt {attempt + 1} error: {e}", level="ERROR")

        safe_call_retry(exchange.fetch_positions, label="post_close_sync")
        time.sleep(1)

    final_qty = get_position_size(symbol)
    if final_qty < 1e-6:
        close_success = True

    if close_success:
        if not exit_price:
            try:
                ticker = safe_call_retry(exchange.fetch_ticker, symbol)
                exit_price = ticker.get("last") or entry_price
            except Exception:
                exit_price = entry_price

        log(f"[Close] Recording trade result for {symbol}", level="INFO")
        record_trade_result(symbol=symbol, side=side, entry_price=entry_price, exit_price=exit_price, result_type=reason)

        trade_manager.remove_trade(symbol)
        trade_manager.set_last_closed_time(symbol, time.time())
        save_active_trades()

        # ✅ ИСПРАВЛЕНО: Сброс timestamp вместо clear()
        with cache_lock:
            if "positions" in api_cache:
                api_cache["positions"]["timestamp"] = 0
            if "balance" in api_cache:
                api_cache["balance"]["timestamp"] = 0
        log(f"[Close] 🔄 Reset cache timestamps after closing {symbol}", level="DEBUG")

        log(f"[Close] ✅ Completed close for {symbol}", level="INFO")
        return True

    # ❌ FAILED
    log(f"[Close] ❌ FAILED to close {symbol} after {max_attempts} attempts", level="ERROR")
    send_telegram_message(f"🚨 URGENT: Failed to close {symbol} - manual intervention required!")

    trade["pending_exit"] = True
    trade["exit_fail_reason"] = reason
    trade_manager.update_trade(symbol, "pending_exit", True)
    trade_manager.update_trade(symbol, "exit_fail_reason", reason)

    try:
        hangs_path = Path("data/hang_trades.json")
        hangs = {}
        if hangs_path.exists():
            with open(hangs_path, "r") as f:
                hangs = json.load(f)
        hangs[symbol] = {"qty": final_qty, "side": side, "reason": reason, "timestamp": time.time()}
        with open(hangs_path, "w") as f:
            json.dump(hangs, f, indent=2)
        log(f"[Close] Added {symbol} to hang_trades.json", level="WARNING")
    except Exception as e:
        log(f"[Close] Failed to write hang_trades.json: {e}", level="ERROR")

    return False


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
                close_real_trade(symbol, reason="bonus_profit")
                record_trade_result(symbol, side, entry_price, current_price, "tp")
                send_telegram_message(f"🎉 *Bonus Profit!* {symbol} closed at +{profit_pct:.2f}%!")
                break

            # Если достигли обычного порога
            elif profit_pct >= AUTO_CLOSE_PROFIT_THRESHOLD:
                log(f"[Auto-Profit] ✅ Auto-closing {symbol} at +{profit_pct:.2f}%", level="INFO")
                close_real_trade(symbol, reason="auto_profit")
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
                        close_real_trade(symbol, reason="micro_profit")
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
    Мониторит активную позицию и исполняет step TP, SL restore, AutoProfit, soft-exit и принудительное закрытие.
    Версия v5.5 с полным step TP исполнением, SL qty валидацией и FIX #2, #3.
    """
    import time

    from core.exchange_init import exchange
    from core.tp_utils import safe_round_and_validate
    from telegram.telegram_utils import send_telegram_message
    from utils_core import api_cache, cache_lock, get_runtime_config, safe_call_retry, safe_float_conversion
    from utils_logging import log

    config = get_runtime_config()
    step_levels = config.get("step_tp_levels", [0.004, 0.008, 0.012])
    step_sizes = config.get("step_tp_sizes", [0.4, 0.3, 0.3])
    auto_profit_pct = config.get("auto_profit_threshold", 1.5)
    max_hold = config.get("max_hold_minutes", 30) * 60

    is_buy = side.lower() == "buy"
    step_hits = [False] * len(step_levels)

    if start_time is None or not isinstance(start_time, float):
        start_time = time.time()

    log(f"[Monitor] Started monitoring {symbol} at entry={entry_price} qty={initial_qty}", level="INFO")

    # ✅ ДОБАВЛЕНО: Защита всего потока мониторинга
    try:
        while True:
            time.sleep(5)
            qty = get_position_size(symbol)

            if qty <= 0:
                log(f"[Monitor] {symbol}: position closed — exit", level="INFO")
                # ✅ ИСПРАВЛЕНО: Добавлена проверка существования ключей
                with cache_lock:
                    if "positions" in api_cache:
                        api_cache["positions"]["timestamp"] = 0
                    else:
                        log("[Monitor] Warning: positions key missing in api_cache", level="WARNING")
                    if "balance" in api_cache:
                        api_cache["balance"]["timestamp"] = 0
                    else:
                        log("[Monitor] Warning: balance key missing in api_cache", level="WARNING")

                trade_manager.remove_trade(symbol)
                from core.engine_controller import sync_open_positions

                sync_open_positions()
                return

            elapsed = time.time() - start_time
            if elapsed > max_hold:
                log(f"[Monitor] {symbol}: max hold time exceeded → closing", level="WARNING")
                send_telegram_message(f"⏳ Max hold time exceeded for {symbol} → closing position")
                close_real_trade(symbol, reason="timeout")
                return

            price_data = safe_call_retry(exchange.fetch_ticker, symbol)
            if not price_data:
                continue
            current_price = safe_float_conversion(price_data.get("last", 0))

            if current_price <= 0:
                log(f"[Monitor] {symbol}: invalid current price: {current_price}", level="WARNING")
                continue

            if is_buy:
                profit_pct = ((current_price - entry_price) / entry_price) * 100
            else:
                profit_pct = ((entry_price - current_price) / entry_price) * 100

            for i, level in enumerate(step_levels):
                if not step_hits[i] and profit_pct >= level * 100:
                    qty_raw = qty * step_sizes[i]
                    qty_i = safe_round_and_validate(symbol, qty_raw)
                    if qty_i is None or qty_i <= 0:
                        log(f"[Monitor] Skipping TP{i + 1} for {symbol} due to invalid qty", level="WARNING")
                        continue
                    try:
                        order_side = "sell" if is_buy else "buy"
                        safe_call_retry(exchange.create_market_order, symbol, order_side, qty_i, params={"reduceOnly": True})
                        step_hits[i] = True
                        send_telegram_message(f"✅ TP{i + 1} HIT: {symbol} +{profit_pct:.2f}% qty={qty_i:.4f}")
                        trade_manager.update_trade(symbol, f"tp{i + 1}_hit", True)
                    except Exception as e:
                        log(f"[Monitor] Failed to execute TP{i + 1} for {symbol}: {e}", level="ERROR")

            if profit_pct >= auto_profit_pct:
                log(f"[Monitor] AutoProfit triggered at {profit_pct:.2f}%", level="INFO")
                send_telegram_message(f"🚀 AutoProfit threshold reached for {symbol} ({profit_pct:.2f}%) → closing")
                close_real_trade(symbol, reason="auto_profit")
                return

            open_orders = safe_call_retry(exchange.fetch_open_orders, symbol)
            trade = trade_manager.get_trade(symbol)
            sl_price = trade.get("sl_price") if trade else None
            sl_restored = trade.get("sl_restored", False) if trade else False

            if not open_orders and not sl_restored and sl_price and qty > 0:
                sl_price = safe_float_conversion(sl_price)
                sl_distance = abs(current_price - sl_price) / current_price
                # ✅ FIX #3: Унифицированный порог 0.5% как в tp_utils.py
                if sl_distance < 0.005:  # ✅ Изменено с 0.01 на 0.005
                    sl_price = round(current_price * (0.99 if is_buy else 1.01), 6)
                    log(f"[Monitor] Adjusted SL to {sl_price} (was too close, distance={sl_distance:.4f})", level="INFO")
                qty_validated = safe_round_and_validate(symbol, qty)
                if not qty_validated:
                    log("[Monitor] Can't validate qty for SL restore", level="WARNING")
                    continue
                try:
                    sl_side = "sell" if is_buy else "buy"
                    safe_call_retry(exchange.create_order, symbol, "STOP_MARKET", sl_side, qty_validated, params={"stopPrice": sl_price, "reduceOnly": True})
                    send_telegram_message(f"🛡 SL restored for {symbol}")
                    trade_manager.update_trade(symbol, "sl_restored", True)
                except Exception as e:
                    if "immediately trigger" in str(e):
                        log("[Monitor] SL restore failed - too close to price", level="WARNING")
                    else:
                        log(f"[Monitor] SL restore error: {e}", level="ERROR")

    except Exception as e:
        # ✅ КРИТИЧНО: Защита от падения потока
        log(f"[Monitor] CRITICAL: Monitor thread crashed for {symbol}: {e}", level="ERROR")
        send_telegram_message(f"🚨 Monitor crashed for {symbol}! Attempting emergency close...")

        # Попытка аварийного закрытия позиции
        try:
            close_real_trade(symbol, reason="monitor_crash")
        except Exception as close_error:
            log(f"[Monitor] Failed to emergency close {symbol}: {close_error}", level="ERROR")
            send_telegram_message(f"❌ FAILED to close {symbol} after monitor crash! MANUAL INTERVENTION REQUIRED!")


def handle_panic(stop_event):
    """
    Закрывает все позиции максимально быстро и завершает цикл.
    """
    import time

    from core.binance_api import get_open_positions
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
                log(f"[PANIC] Still open after attempt {i + 1}: {[p['symbol'] for p in still_open]}", level="WARNING")
        except Exception as e:
            log(f"[PANIC] Retry check error: {e}", level="ERROR")
        time.sleep(3)

    # Если всё ещё открыты — сообщаем
    send_telegram_message("⚠️ Some positions may still be open after PANIC.", force=True)
    log("[PANIC] Positions remained open after retries.", level="ERROR")
