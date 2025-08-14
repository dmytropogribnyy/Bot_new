#!/usr/bin/env python3
"""
Order Manager for BinanceBot v2.3
Simplified version based on v2 structure
"""

import asyncio
import time
from pathlib import Path
from typing import Any

from core.audit_logger import get_audit_logger
from core.config import TradingConfig
from core.exchange_client import OptimizedExchangeClient
from core.idempotency_store import IdempotencyStore
from core.ids import make_client_id
from core.precision import PrecisionError, normalize
from core.qty_rules import minimal_trade_qty
from core.risk_checks import check_margin_before_entry
from core.risk_guard import (
    is_symbol_blocked,
    is_symbol_recently_traded,
    pause_symbol,
    update_symbol_last_entry,
)
from core.risk_guard_stage_f import RiskGuardStageF
from core.sizing import calculate_position_from_risk
from core.unified_logger import UnifiedLogger
from tools.pre_trade_check import can_enter_position


class OrderManager:
    """Comprehensive order and position management system"""

    def __init__(self, config: TradingConfig, exchange: OptimizedExchangeClient, logger: UnifiedLogger):
        self.config = config
        self.exchange = exchange
        self.logger = logger

        # Idempotency store (persistent across restarts)
        self.idem = IdempotencyStore(path=str(Path("runtime") / "idemp.json"))
        Path("runtime").mkdir(parents=True, exist_ok=True)
        try:
            self.idem.load()
        except Exception:
            pass

        # Position and order tracking
        self.active_positions: dict[str, dict] = {}  # symbol -> position_data
        self.pending_orders: dict[str, list[dict]] = {}  # symbol -> [orders]
        self.tp_orders: dict[str, list[dict]] = {}  # symbol -> [tp_orders]
        self.sl_orders: dict[str, dict] = {}  # symbol -> sl_order

        # Monitoring and synchronization
        self.last_sync_time = 0
        self.sync_interval = 30  # seconds
        self.order_timeout = 300  # 5 minutes for hanging orders

        # Locks
        self.position_lock = asyncio.Lock()
        self.order_lock = asyncio.Lock()

        # State flags
        self.shutdown_requested = False
        self.emergency_mode = False

        # Lightweight WS idempotency window to avoid duplicate processing on reconnects
        self._ws_seen: set[tuple[object, object, object]] = set()
        self._ws_seen_max: int = 10000

        # Emergency shutdown flag (persistent)
        self.emergency_shutdown_flag = False
        self.shutdown_timestamp = None
        self.emergency_flag_file = "data/emergency_shutdown.flag"

        # Load emergency flag on initialization
        self._load_emergency_flag()

        # Initialize risk management
        self.risk_guard_f = RiskGuardStageF(self.config, self.logger)
        self.deposit_usdc = self.config.trading_deposit  # Trading deposit
        self.logger.log_event("ORDER_MANAGER", "INFO", "Risk Guard Stage F initialized")

        # Audit logger (env-scoped)
        try:
            self.audit = get_audit_logger(testnet=self.config.testnet)
        except Exception:
            self.audit = None  # optional

    async def get_trading_capital(self) -> float:
        """
        Возвращает капитал для расчёта risk/margin:
        - при use_dynamic_balance=True: фактический quote-баланс * balance_percentage
        - иначе: фиксированный trading_deposit
        """
        if getattr(self.config, "use_dynamic_balance", False):
            try:
                balance = await self.exchange.get_quote_balance()  # уже реализовано в exchange_client
                return float(balance) * float(getattr(self.config, "balance_percentage", 0.95))
            except Exception as e:
                self.logger.log_event("ORDER_MANAGER", "WARNING", f"[CAPITAL] fallback to fixed deposit: {e}")
                return float(self.config.trading_deposit)
        return float(self.config.trading_deposit)

    def _ensure_pos_cache(self):
        """Инициализировать кэш позиций если его нет"""
        if not hasattr(self, "positions"):
            self.positions = {}  # { symbol: {"contracts": float, "unrealized_pnl": float} }
        if not hasattr(self, "_reported_exits"):
            self._reported_exits = set()  # Защита от дублей записей

    def _position_is_zero(self, symbol: str) -> bool:
        """Проверить что позиция по символу закрыта (размер ~0)"""
        self._ensure_pos_cache()
        pos = self.positions.get(symbol) or {}
        try:
            size = abs(float(pos.get("contracts", 0.0)))
        except Exception:
            size = 0.0
        return size < 1e-6  # Меньше минимального размера

    def record_rest_exit_if_closed(self, symbol: str, realized_or_est_pnl: float) -> None:
        """REST fallback: записать выход когда обнаружили через REST что позиция закрыта"""
        try:
            if self.audit:
                self.audit.record_exit_decision(
                    symbol=symbol,
                    reason="NORMAL_EXIT_REST",
                    pnl=float(realized_or_est_pnl or 0.0),
                    metadata={"source": "REST_POLL"},
                )
        except Exception as e:
            self.logger.log_event("AUDIT", "ERROR", f"record_rest_exit_if_closed failed: {e}")

    def _intent_key(
        self,
        *,
        env: str,
        strategy: str,
        symbol: str,
        side: str,
        order_type: str,
        qty_norm: float,
        price_norm: float | None,
        tp: float | None = None,
        sl: float | None = None,
    ) -> str:
        return f"{env}|{strategy}|{symbol}|{side}|{order_type}|{qty_norm}|{price_norm or 'MKT'}|{tp or ''}|{sl or ''}"

    def _load_emergency_flag(self):
        """Load emergency shutdown flag from file"""
        try:
            import os

            if os.path.exists(self.emergency_flag_file):
                with open(self.emergency_flag_file) as f:
                    flag_data = f.read().strip()
                    if flag_data == "EMERGENCY_SHUTDOWN":
                        self.emergency_shutdown_flag = True
                        self.logger.log_event(
                            "ORDER_MANAGER", "WARNING", "Emergency shutdown flag detected from previous run"
                        )
        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR", f"Failed to load emergency flag: {e}")

    async def startup_cleanup(self, symbols: list[str]) -> dict:
        """
        Отменяет «хвосты»:
         - reduceOnly TP/SL без соответствующей позиции (или при qty≈0)
         - минимальная дедупликация по параметрам при возможности
        Возвращает статистику {'cancelled': N, 'skipped': M}.
        """
        cancelled = 0
        skipped = 0

        for sym in symbols:
            try:
                orders = await self.exchange.get_open_orders(sym)
            except Exception:
                orders = []

            try:
                pos = await self.exchange.get_position(sym)
            except Exception:
                pos = None

            try:
                size_val = abs(float((pos or {}).get("contracts") or (pos or {}).get("size") or 0))
            except Exception:
                size_val = 0.0

            has_pos = bool(size_val > 0)

            for o in orders or []:
                try:
                    is_reduce = bool(o.get("reduceOnly") is True or (o.get("info", {}).get("reduceOnly") is True))
                    if is_reduce and not has_pos:
                        try:
                            await self.exchange.cancel_order(o["id"], sym)
                            cancelled += 1
                        except Exception:
                            skipped += 1
                    else:
                        skipped += 1
                except Exception:
                    skipped += 1

        # Log summary
        try:
            self.logger.log_event("ORDER_MANAGER", "INFO", f"[CLEANUP] cancelled={cancelled} skipped={skipped}")
        except Exception:
            pass

        # TTL cleanup for idempotency store
        try:
            self.idem.cleanup_old(days=7)
        except Exception:
            pass

        return {"cancelled": cancelled, "skipped": skipped}

    def _save_emergency_flag(self):
        """Save emergency shutdown flag to file"""
        try:
            import os

            os.makedirs(os.path.dirname(self.emergency_flag_file), exist_ok=True)
            with open(self.emergency_flag_file, "w") as f:
                f.write("EMERGENCY_SHUTDOWN")
            self.logger.log_event("ORDER_MANAGER", "INFO", "Emergency shutdown flag saved")
        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR", f"Failed to save emergency flag: {e}")

    def _clear_emergency_flag(self):
        """Clear emergency shutdown flag"""
        try:
            import os

            if os.path.exists(self.emergency_flag_file):
                os.remove(self.emergency_flag_file)
                self.logger.log_event("ORDER_MANAGER", "INFO", "Emergency shutdown flag cleared")
        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR", f"Failed to clear emergency flag: {e}")

    async def initialize(self):
        """Initialize OrderManager"""
        try:
            # Sync with real positions on Binance
            await self.sync_positions_from_exchange()

            # Clean up hanging orders
            await self.cleanup_hanging_orders()

            self.logger.log_event("ORDER_MANAGER", "INFO", "OrderManager initialized successfully")
            return True

        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR", f"Failed to initialize OrderManager: {e}")
            return False

    async def sync_positions_from_exchange(self):
        """Sync positions with exchange"""
        try:
            positions = await self.exchange.get_positions()

            async with self.position_lock:
                self.active_positions.clear()

                for position in positions:
                    symbol = position["symbol"]
                    # Be tolerant to ccxt schema variations: size vs contracts
                    try:
                        size = float(position.get("size", position.get("contracts", 0)))
                    except Exception:
                        size = 0.0

                    if size != 0:
                        self.active_positions[symbol] = {
                            "symbol": symbol,
                            "size": size,
                            "side": "long" if size > 0 else "short",
                            "entry_price": float(position["entryPrice"]),
                            "mark_price": float(position["markPrice"]),
                            "unrealized_pnl": float(position["unrealizedPnl"]),
                            "leverage": int(position["leverage"]),
                            "timestamp": time.time(),
                        }

            self.logger.log_event(
                "ORDER_MANAGER", "DEBUG", f"Synced {len(self.active_positions)} positions from exchange"
            )

        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR", f"Failed to sync positions: {e}")

    async def place_position_with_tp_sl(
        self, symbol: str, side: str, quantity: float, entry_price: float, leverage: int = 5
    ) -> dict[str, Any]:
        """Place position with TP/SL orders"""
        try:
            # ========== RISK MANAGEMENT CHECKS ==========

            # 1. Global risk check (Stage F)
            can_open, reason = self.risk_guard_f.can_open_new_position()
            if not can_open:
                self.logger.log_event("RISK_F", "WARNING", f"Position blocked: {reason}")
                return {"success": False, "reason": f"STAGE_F: {reason}"}

            # 2. Symbol-specific blocks
            if is_symbol_blocked(symbol):
                self.logger.log_event("RISK_GUARD", "INFO", f"{symbol} is temporarily blocked")
                return {"success": False, "reason": "SYMBOL_BLOCKED"}

            # 3. Symbol cooldown check
            cooldown_seconds = getattr(self.config, "entry_cooldown_seconds", 300)
            if is_symbol_recently_traded(symbol, cooldown_seconds):
                self.logger.log_event("RISK_GUARD", "DEBUG", f"{symbol} on cooldown")
                return {"success": False, "reason": "COOLDOWN_ACTIVE"}

            # 4. Get current price for sizing
            ticker = await self.exchange.get_ticker(symbol)
            current_price = float(ticker.get("last", 0) or ticker.get("close", 0))
            if not current_price:
                return {"success": False, "reason": "NO_PRICE"}

            # 5. Calculate position size from risk (dynamic/static capital)
            capital = await self.get_trading_capital()
            risk_pct = 0.0075  # 0.75% от капитала
            risk_usdc = float(capital) * risk_pct
            sl_percent = float(self.config.stop_loss_percent)

            sizing = await calculate_position_from_risk(
                self.exchange, symbol, current_price, risk_usdc, sl_percent, leverage
            )

            # 6. Check margin limits against available capital
            ok_margin, msg = await check_margin_before_entry(self, symbol, sizing.margin, capital)
            if not ok_margin:
                self.logger.log_event("RISK_CHECK", "WARNING", f"Margin check failed: {msg}")
                return {"success": False, "reason": msg}

            # 7. Run pre-trade filters
            ok_filters, filter_details = await can_enter_position(self, symbol, sizing.margin)
            if not ok_filters:
                failed_checks = [k for k, v in filter_details.items() if not v]
                self.logger.log_event("PRE_TRADE", "INFO", f"Filters failed for {symbol}: {failed_checks}")
                return {"success": False, "reason": "FILTERS", "details": filter_details}

            # 8. Override quantity with calculated value
            quantity = sizing.qty

            # 9. Ensure minimum quantity
            min_qty = await minimal_trade_qty(self.exchange, symbol, current_price)
            if quantity < min_qty:
                quantity = min_qty

            self.logger.log_event(
                "RISK_SIZING",
                "INFO",
                f"{symbol} Sized: qty={quantity:.4f}, margin=${sizing.margin:.2f}, risk=${risk_usdc:.2f}",
            )

            # ========== END RISK MANAGEMENT ==========

            # Check if we already have a position
            if symbol in self.active_positions:
                self.logger.log_event("ORDER_MANAGER", "WARNING", f"Position already exists for {symbol}")
                return {"success": False, "reason": "Position already exists"}

            # Check position limit
            if len(self.active_positions) >= self.config.max_positions:
                self.logger.log_event(
                    "ORDER_MANAGER", "WARNING", f"Maximum positions reached ({self.config.max_positions})"
                )
                return {"success": False, "reason": "Maximum positions reached"}

            # Set leverage
            try:
                await self.exchange.exchange.set_leverage(leverage, symbol)
            except Exception as e:
                self.logger.log_event("ORDER_MANAGER", "WARNING", f"Failed to set leverage for {symbol}: {e}")

            # Precision gate for market entry
            markets = await self.exchange.get_markets()
            market = markets.get(symbol, {})
            ticker = await self.exchange.get_ticker(symbol)
            try:
                current_price = float((ticker or {}).get("last") or (ticker or {}).get("close") or 0) or None
            except Exception:
                current_price = None

            _, qty_norm, _ = normalize(None, float(quantity), market, current_price, symbol)
            self.logger.log_event(
                "ORDER_MANAGER",
                "DEBUG",
                f"Normalized market entry for {symbol}: qty {quantity} -> {qty_norm}",
            )

            # Place market order with normalized qty (idempotent)
            env = getattr(self.config, "ENV", "PROD")
            strategy = getattr(self.config, "STRATEGY", "DEFAULT")
            intent_entry = self._intent_key(
                env=env,
                strategy=strategy,
                symbol=symbol,
                side=side,
                order_type="MARKET",
                qty_norm=qty_norm,
                price_norm=None,
            )
            cid_entry = self.idem.get(intent_entry) or make_client_id(env, strategy, symbol, side, intent_entry)
            if self.idem.get(intent_entry) is None:
                self.idem.put(intent_entry, cid_entry)
            params_entry = {"newClientOrderId": cid_entry}
            self.logger.log_event("ORDER_MANAGER", "DEBUG", f"[IDEMP] intent={intent_entry} clientId={cid_entry}")

            order = await self.exchange.create_order(symbol, "market", side, qty_norm, None, params_entry)

            if not order or "id" not in order:
                return {"success": False, "reason": "Failed to place order"}

            # Audit order placement
            try:
                if self.audit:
                    self.audit.log_order_placed(order, reason="Entry signal")
            except Exception:
                pass

            # Calculate TP/SL levels
            sl_price = self.calculate_stop_loss(entry_price, side)
            tp_levels = self.calculate_take_profit_levels(entry_price, side)

            # Place TP/SL orders
            tp_sl_result = await self.place_tp_sl_orders(symbol, side, quantity, entry_price)

            # Update active positions
            async with self.position_lock:
                self.active_positions[symbol] = {
                    "symbol": symbol,
                    "size": quantity,
                    "side": side,
                    "entry_price": entry_price,
                    "mark_price": entry_price,
                    "unrealized_pnl": 0,
                    "leverage": leverage,
                    "order_id": order["id"],
                    "timestamp": time.time(),
                }

            self.logger.log_event(
                "ORDER_MANAGER", "INFO", f"Position opened: {symbol} {side} {quantity} @ {entry_price}"
            )
            # Mark symbol as traded for cooldown
            update_symbol_last_entry(symbol)

            return {
                "success": True,
                "order_id": order["id"],
                "entry_price": entry_price,
                "sl_price": sl_price,
                "tp_levels": tp_levels,
                "tp_sl_orders": tp_sl_result,
            }

        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR", f"Failed to place position for {symbol}: {e}")
            return {"success": False, "reason": str(e)}

    async def place_tp_sl_orders(self, symbol: str, side: str, quantity: float, entry_price: float) -> dict[str, Any]:
        """Place take profit and stop loss orders"""
        try:
            # Calculate prices
            sl_price = self.calculate_stop_loss(entry_price, side)
            tp_levels = self.calculate_take_profit_levels(entry_price, side)

            # Load market schema for precision gate
            markets = await self.exchange.get_markets()
            market = markets.get(symbol, {})

            # Determine closing side for protective orders (opposite to entry)
            close_side = "sell" if side == "buy" else "buy"

            # Normalize SL before placing
            sl_price_norm, sl_qty_norm, _ = normalize(sl_price, float(quantity), market, None, symbol)
            self.logger.log_event(
                "ORDER_MANAGER",
                "DEBUG",
                f"Normalized SL for {symbol}: price {sl_price} -> {sl_price_norm}, qty {quantity} -> {sl_qty_norm}",
            )
            # Idempotent SL order
            env = getattr(self.config, "ENV", "PROD")
            strategy = getattr(self.config, "STRATEGY", "DEFAULT")
            intent_sl = self._intent_key(
                env=env,
                strategy=strategy,
                symbol=symbol,
                side=close_side,
                order_type="STOP_MARKET",
                qty_norm=sl_qty_norm,
                price_norm=sl_price_norm,
                tp=None,
                sl=sl_price_norm,
            )
            cid_sl = self.idem.get(intent_sl) or make_client_id(env, strategy, symbol, close_side, intent_sl)
            if self.idem.get(intent_sl) is None:
                self.idem.put(intent_sl, cid_sl)
            params_sl = {
                "stopPrice": float(sl_price_norm),
                "reduceOnly": True,
                "workingType": self.config.working_type,
                "newClientOrderId": cid_sl,
            }
            self.logger.log_event("ORDER_MANAGER", "DEBUG", f"[IDEMP] intent={intent_sl} clientId={cid_sl}")
            sl_order = await self.exchange.create_order(symbol, "STOP_MARKET", close_side, sl_qty_norm, None, params_sl)

            # КРИТИЧНО: Проверка что SL реально установился
            if sl_price_norm and not sl_order.get("id"):
                self.logger.log_event("ORDER_MANAGER", "CRITICAL", f"SL FAILED for {symbol} - CLOSING POSITION")
                # Немедленно закрыть позицию
                close_order = await self.exchange.create_order(
                    symbol, "market", close_side, float(quantity), None, {"reduceOnly": True}
                )
                return {"success": False, "error": "SL_NOT_SET", "closed": close_order.get("id")}

            # Дополнительная проверка через REST API
            await asyncio.sleep(1.5)
            open_orders = await self.exchange.get_open_orders(symbol)

            # Нормализуем проверку типа
            has_sl = False
            for o in open_orders:
                otype = str(o.get("type") or o.get("info", {}).get("type") or "").upper()
                is_reduce = (o.get("reduceOnly") is True) or (o.get("info", {}).get("reduceOnly") is True)
                if (("STOP" in otype) or (otype in {"STOP", "STOP_MARKET"})) and is_reduce:
                    has_sl = True
                    break

            if sl_price_norm and not has_sl:
                self.logger.log_event("ORDER_MANAGER", "CRITICAL", f"SL NOT FOUND on exchange for {symbol}")
                # Экстренное закрытие
                await self.exchange.create_order(
                    symbol, "market", close_side, float(quantity), None, {"reduceOnly": True}
                )
                return {"success": False, "error": "SL_VERIFICATION_FAILED"}

            # Audit SL order placement
            try:
                if sl_order and sl_order.get("id") and self.audit:
                    self.audit.log_order_placed(sl_order, reason="Stop loss protection")
            except Exception:
                pass

            # Place take profit orders
            tp_orders = []
            for tp_price, tp_fraction in tp_levels:
                # Convert fraction to absolute amount
                tp_amount = round(float(quantity) * float(tp_fraction), 6)
                if tp_amount <= 0:
                    continue
                # Normalize TP before placing
                tp_price_norm, tp_qty_norm, _ = normalize(tp_price, tp_amount, market, None, symbol)
                if tp_qty_norm <= 0:
                    continue
                self.logger.log_event(
                    "ORDER_MANAGER",
                    "DEBUG",
                    f"Normalized TP for {symbol}: price {tp_price} -> {tp_price_norm}, qty {tp_amount} -> {tp_qty_norm}",
                )
                # Idempotent TP order
                intent_tp = self._intent_key(
                    env=env,
                    strategy=strategy,
                    symbol=symbol,
                    side=close_side,
                    order_type=("TAKE_PROFIT_MARKET" if self.config.tp_order_style == "market" else "TAKE_PROFIT"),
                    qty_norm=tp_qty_norm,
                    price_norm=tp_price_norm,
                    tp=tp_price_norm,
                    sl=None,
                )
                cid_tp = self.idem.get(intent_tp) or make_client_id(env, strategy, symbol, close_side, intent_tp)
                if self.idem.get(intent_tp) is None:
                    self.idem.put(intent_tp, cid_tp)
                params_tp = {
                    "reduceOnly": True,
                    "workingType": self.config.working_type,
                    "newClientOrderId": cid_tp,
                }
                if self.config.tp_order_style == "market":
                    params_tp["stopPrice"] = float(tp_price_norm)
                    tp_order = await self.exchange.create_order(
                        symbol, "TAKE_PROFIT_MARKET", close_side, tp_qty_norm, None, params_tp
                    )
                else:
                    params_tp["stopPrice"] = float(tp_price_norm)
                    tp_order = await self.exchange.create_order(
                        symbol, "TAKE_PROFIT", close_side, tp_qty_norm, float(tp_price_norm), params_tp
                    )
                tp_orders.append(tp_order)

                # Audit TP placement
                try:
                    if tp_order and tp_order.get("id") and self.audit:
                        self.audit.log_order_placed(tp_order, reason="Take profit target")
                except Exception:
                    pass

            # Store orders
            async with self.order_lock:
                self.sl_orders[symbol] = sl_order
                self.tp_orders[symbol] = tp_orders

            self.logger.log_event(
                "ORDER_MANAGER",
                "INFO",
                f"Placed TP/SL orders for {symbol}: SL@{sl_price}, TP@{[tp[0] for tp in tp_levels]}",
            )

            return {
                "sl_order": sl_order,
                "tp_orders": tp_orders,
                "sl_price": sl_price,
                "tp_prices": [tp[0] for tp in tp_levels],
            }

        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR", f"Failed to place TP/SL orders for {symbol}: {e}")
            return {"success": False, "reason": str(e)}

    def calculate_stop_loss(self, entry_price: float, side: str) -> float:
        """Calculate stop loss price"""
        if side == "buy":
            return entry_price * (1 - self.config.stop_loss_percent / 100)
        else:
            return entry_price * (1 + self.config.stop_loss_percent / 100)

    def calculate_take_profit_levels(self, entry_price: float, side: str) -> list[tuple[float, float]]:
        """Calculate take profit levels"""
        if side == "buy":
            tp1_price = entry_price * (1 + self.config.take_profit_percent / 100)
            tp2_price = entry_price * (1 + (self.config.take_profit_percent * 1.5) / 100)
        else:
            tp1_price = entry_price * (1 - self.config.take_profit_percent / 100)
            tp2_price = entry_price * (1 - (self.config.take_profit_percent * 1.5) / 100)

        # Split quantity: 70% at TP1, 30% at TP2
        return [(tp1_price, 0.7), (tp2_price, 0.3)]

    async def close_position_emergency(self, symbol: str) -> dict[str, Any]:
        """Emergency close position"""
        try:
            position = self.active_positions.get(symbol)
            if not position:
                return {"success": False, "reason": "Position not found"}

            # Cancel all orders first
            await self.cancel_all_orders(symbol)

            # Close position with market order
            side = "sell" if position["side"] == "long" else "buy"
            order = await self.exchange.create_market_order(symbol, side, abs(position["size"]))

            # Remove from tracking
            async with self.position_lock:
                self.active_positions.pop(symbol, None)

            self.logger.log_event("ORDER_MANAGER", "WARNING", f"Emergency closed position: {symbol}")

            return {"success": True, "order": order}

        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR", f"Failed to emergency close {symbol}: {e}")
            return {"success": False, "reason": str(e)}

    async def cancel_all_orders(self, symbol: str):
        """Cancel all orders for a symbol"""
        try:
            await self.exchange.cancel_all_orders(symbol)

            # Clear from tracking
            async with self.order_lock:
                self.sl_orders.pop(symbol, None)
                self.tp_orders.pop(symbol, None)

            self.logger.log_event("ORDER_MANAGER", "INFO", f"Cancelled all orders for {symbol}")

        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR", f"Failed to cancel orders for {symbol}: {e}")

    async def cleanup_hanging_orders(self):
        """Clean up hanging orders"""
        try:
            open_orders = await self.exchange.get_open_orders()

            for order in open_orders:
                order_age = time.time() - (order.get("timestamp", 0) / 1000)

                if order_age > self.order_timeout:
                    try:
                        await self.exchange.cancel_order(order["id"], order["symbol"])
                        self.logger.log_event("ORDER_MANAGER", "INFO", f"Cleaned up hanging order: {order['id']}")
                    except Exception as e:
                        self.logger.log_event(
                            "ORDER_MANAGER", "WARNING", f"Failed to cancel hanging order {order['id']}: {e}"
                        )

        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR", f"Failed to cleanup hanging orders: {e}")

    async def monitor_positions(self):
        """Monitor active positions"""
        try:
            for symbol, _position in list(self.active_positions.items()):
                # Check if position still exists on exchange
                current_position = await self.exchange.get_position(symbol)

                if not current_position:
                    # Position was closed
                    async with self.position_lock:
                        self.active_positions.pop(symbol, None)

                    # Clean up orders
                    await self.cancel_all_orders(symbol)

                    self.logger.log_event("ORDER_MANAGER", "INFO", f"Position closed on exchange: {symbol}")

                else:
                    # Update position data
                    async with self.position_lock:
                        self.active_positions[symbol].update(
                            {
                                "mark_price": float(current_position["markPrice"]),
                                "unrealized_pnl": float(current_position["unrealizedPnl"]),
                            }
                        )

        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR", f"Failed to monitor positions: {e}")

    async def check_order_executions(self):
        """Check for executed orders"""
        try:
            for symbol in list(self.active_positions.keys()):
                # Check TP orders
                if symbol in self.tp_orders:
                    for tp_order in self.tp_orders[symbol]:
                        order_status = await self.exchange.get_order(tp_order["id"], symbol)
                        if order_status and order_status["status"] == "closed":
                            self.logger.log_event(
                                "ORDER_MANAGER", "INFO", f"Take profit executed: {symbol} @ {order_status['price']}"
                            )

                # Check SL order
                if symbol in self.sl_orders:
                    sl_order = self.sl_orders[symbol]
                    order_status = await self.exchange.get_order(sl_order["id"], symbol)
                    if order_status and order_status["status"] == "closed":
                        self.logger.log_event(
                            "ORDER_MANAGER", "WARNING", f"Stop loss executed: {symbol} @ {order_status['price']}"
                        )

        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR", f"Failed to check order executions: {e}")

    async def check_timeouts(self):
        """Check for order timeouts"""
        try:
            current_time = time.time()

            for symbol in list(self.active_positions.keys()):
                position = self.active_positions[symbol]
                position_age = current_time - position.get("timestamp", 0)

                # Check for emergency stop loss
                if self.config.emergency_stop_enabled and position_age > 3600:  # 1 hour
                    position.get("unrealized_pnl", 0)
                    entry_price = position.get("entry_price", 0)
                    mark_price = position.get("mark_price", 0)

                    if entry_price > 0:
                        loss_percent = abs(mark_price - entry_price) / entry_price * 100

                        if loss_percent > self.config.emergency_stop_loss:
                            self.logger.log_event(
                                "ORDER_MANAGER",
                                "WARNING",
                                f"Emergency stop loss triggered for {symbol}: {loss_percent:.2f}%",
                            )
                            await self.close_position_emergency(symbol)

        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR", f"Failed to check timeouts: {e}")

    async def check_auto_profit(self) -> None:
        """Check positions for auto-profit closure"""
        if not self.config.auto_profit_enabled:
            return

        try:
            # Use existing positions registry
            positions = self.active_positions.copy()

            for symbol, position in positions.items():
                # Get current price
                ticker = await self.exchange.get_ticker(symbol)
                if not ticker:
                    continue

                current_price = ticker.get("last", 0)
                if not current_price:
                    continue

                # Calculate PnL%
                entry_price = position.get("entry_price", 0)
                side = position.get("side", "").lower()

                if not entry_price or not side:
                    continue

                if side == "buy":
                    pnl_pct = ((current_price - entry_price) / entry_price) * 100
                else:
                    pnl_pct = ((entry_price - current_price) / entry_price) * 100

                # Check time in position
                timestamp = position.get("timestamp", 0)
                hold_minutes = (time.time() - timestamp) / 60 if timestamp else 0

                # Auto-close logic
                should_close = False
                reason = ""

                # Bonus threshold - immediate close
                if pnl_pct >= self.config.bonus_profit_threshold:
                    should_close = True
                    reason = f"BONUS_PROFIT_{pnl_pct:.1f}%"
                # Normal threshold after max hold time
                elif hold_minutes >= self.config.max_hold_minutes and pnl_pct >= self.config.auto_profit_threshold:
                    should_close = True
                    reason = f"AUTO_PROFIT_{pnl_pct:.1f}%_after_{hold_minutes:.0f}min"

                if should_close:
                    self.logger.log_event("AUTO_PROFIT", "INFO", f"Closing {symbol}: {reason}")

                    # Close using existing method
                    await self.close_position_market(symbol)

        except Exception as e:
            self.logger.log_event("AUTO_PROFIT", "ERROR", f"Check failed: {e}")

    async def close_position_market(self, symbol: str) -> bool:
        """Close position at market price"""
        try:
            position = self.active_positions.get(symbol)
            if not position:
                return False

            side = position.get("side", "").lower()
            size = position.get("size", 0)

            if not side or not size:
                return False

            # Opposite side for closing
            close_side = "sell" if side == "buy" else "buy"

            # Use existing exchange method
            order = await self.exchange.create_order(
                symbol=symbol, type="MARKET", side=close_side, amount=abs(size), params={"reduceOnly": True}
            )

            if order:
                self.logger.log_event("ORDER_MANAGER", "INFO", f"Market closed {symbol}: {order.get('id')}")
                return True

        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR", f"Failed to close {symbol}: {e}")

        return False

    async def handle_ws_event(self, event: dict):
        """
        Handle WebSocket user data stream events with complete audit.
        Правильно детектирует ликвидации, ADL, обычные выходы. Записывает все в аудит с точным realized PnL.
        """
        # Deduplicate repeated WS events (reconnects/duplicates)
        etype = event.get("e")
        try:
            ts = event.get("E")
            oid = event.get("o", {}).get("i") if etype == "ORDER_TRADE_UPDATE" else None
            eid = (etype, ts, oid)
            if eid in self._ws_seen:
                return
            self._ws_seen.add(eid)
            if len(self._ws_seen) > self._ws_seen_max:
                # Keep a rolling window; order is not guaranteed but sufficient for lightweight dedup
                self._ws_seen = set(list(self._ws_seen)[-self._ws_seen_max :])
        except Exception:
            pass

        # === ORDER_TRADE_UPDATE: ордера, сделки, ликвидации ===
        if etype == "ORDER_TRADE_UPDATE":
            o = event.get("o", {})  # order payload
            symbol = o.get("s")
            status = o.get("X")  # FILLED / PARTIALLY_FILLED / CANCELED / EXPIRED / NEW
            order_type = (
                o.get("ot") or ""
            ).upper()  # MARKET, LIMIT, STOP, STOP_MARKET, TAKE_PROFIT, TAKE_PROFIT_MARKET, LIQUIDATION
            exec_type = (o.get("x") or "").upper()  # NEW, CANCELED, CALCULATED, EXPIRED, TRADE
            reduce_only = bool(o.get("R"))
            try:
                realized_pnl = float(o.get("rp") or 0.0)
            except Exception:
                realized_pnl = 0.0
            order_id = o.get("i")
            client_id = str(o.get("c") or "")

            # Обновить внутреннее состояние ордера если есть метод
            if hasattr(self, "_update_order_state"):
                try:
                    await self._update_order_state(order_id, status, o)  # type: ignore[misc]
                except Exception as e:
                    self.logger.log_event("WS", "WARNING", f"_update_order_state failed: {e}")

            # --- КРИТИЧНО: Правильная детекция ликвидации/ADL с безопасной проверкой CALCULATED ---
            is_liq = (
                order_type == "LIQUIDATION"
                or client_id.startswith("autoclose-")
                or client_id == "adl_autoclose"
                or (
                    exec_type == "CALCULATED" and (client_id.startswith("autoclose-") or order_type == "LIQUIDATION")
                )  # CALCULATED только вместе с другими маркерами!
            )

            if is_liq:
                # Различаем ADL от обычной ликвидации
                reason = "ADL" if client_id == "adl_autoclose" else "LIQUIDATION"

                self.logger.log_event(
                    "WS", "CRITICAL", f"🚨 {reason} detected! Symbol: {symbol}, PnL: ${realized_pnl:.2f}"
                )

                # Запись в аудит
                try:
                    if self.audit:
                        self.audit.record_exit_decision(
                            symbol=symbol,
                            reason=reason,
                            pnl=realized_pnl,
                            metadata={
                                "order_id": order_id,
                                "order_type": order_type,
                                "exec_type": exec_type,
                                "client_id": client_id,
                                "source": "WS_ORDER_TRADE_UPDATE",
                                "event_time": event.get("E"),
                            },
                        )
                except Exception as e:
                    self.logger.log_event("AUDIT", "ERROR", f"Failed to record liquidation: {e}")

                # Telegram алерт
                if hasattr(self, "telegram_bot") and self.telegram_bot:
                    try:
                        await self.telegram_bot.send_message(
                            f"🚨 {reason}!\nSymbol: {symbol}\nPnL: ${realized_pnl:.2f}"
                        )
                    except Exception:
                        pass

                return  # Ликвидация обработана

            # --- Обычный выход: FILLED + (reduceOnly или позиция стала 0) ---
            pos_is_zero = self._position_is_zero(symbol)

            if status == "FILLED" and (reduce_only or pos_is_zero):
                # Определяем причину выхода
                reason = "MANUAL_CLOSE"
                if order_type in {"TAKE_PROFIT", "TAKE_PROFIT_MARKET"}:
                    reason = "TP_HIT"
                elif order_type in {"STOP", "STOP_MARKET"}:
                    reason = "SL_HIT"

                # Защита от дублей записей
                self._ensure_pos_cache()
                key = (symbol, order_id)

                if key not in getattr(self, "_reported_exits", set()):
                    self._reported_exits.add(key)

                    self.logger.log_event(
                        "WS", "INFO", f"Position closed: {symbol}, Reason: {reason}, PnL: ${realized_pnl:.2f}"
                    )

                    # Запись в аудит
                    try:
                        if self.audit:
                            self.audit.record_exit_decision(
                                symbol=symbol,
                                reason=reason,
                                pnl=realized_pnl,
                                metadata={
                                    "order_id": order_id,
                                    "order_type": order_type,
                                    "source": "WS_ORDER_TRADE_UPDATE",
                                    "event_time": event.get("E"),
                                },
                            )
                    except Exception as e:
                        self.logger.log_event("AUDIT", "ERROR", f"Failed to record exit: {e}")

        # === ACCOUNT_UPDATE: обновляем кэш позиций ===
        elif etype == "ACCOUNT_UPDATE":
            a = event.get("a", {})
            self._ensure_pos_cache()

            # Обновляем позиции из события
            try:
                for p in a.get("P", []):  # Positions array
                    s = p.get("s")  # Symbol (e.g., BTCUSDT)
                    pa = float(p.get("pa") or 0.0)  # Position amount
                    up = float(p.get("up") or 0.0)  # Unrealized PnL

                    if s:
                        old_size = (self.positions.get(s, {}) or {}).get("contracts", 0)
                        self.positions[s] = {"contracts": pa, "unrealized_pnl": up}

                        # Логируем если позиция закрылась
                        if old_size != 0 and pa == 0:
                            self.logger.log_event("WS", "INFO", f"Position zeroed via ACCOUNT_UPDATE: {s}")

            except Exception as e:
                self.logger.log_event("WS", "WARNING", f"ACCOUNT_UPDATE parse error: {e}")

            # Балансы (опционально можно сохранять)
            for b in a.get("B", []):  # Balances array
                _asset = b.get("a")
                _wallet_balance = float(b.get("wb", 0))
                _cross_wallet = float(b.get("cw", 0))
                # Ничего не делаем по умолчанию

        # === MARGIN_CALL: предупреждение о риске (НЕ факт ликвидации!) ===
        elif etype == "MARGIN_CALL":
            self.logger.log_event("WS", "WARNING", f"⚠️ MARGIN_CALL warning: {event}")

            # Telegram алерт
            if hasattr(self, "telegram_bot") and self.telegram_bot:
                try:
                    await self.telegram_bot.send_message("⚠️ MARGIN CALL WARNING!\nCheck your positions immediately!")
                except Exception:
                    pass

        # === listenKeyExpired: логируем, восстановление произойдет автоматически ===
        elif etype == "listenKeyExpired":
            self.logger.log_event("WS", "ERROR", "ListenKey expired — keepalive loop will recover it")

            # Telegram уведомление
            if hasattr(self, "telegram_bot") and self.telegram_bot:
                try:
                    await self.telegram_bot.send_message("🔄 listenKeyExpired received. Recreating via keepalive…")
                except Exception:
                    pass

    def update_price_cache(self, symbol: str, price: float) -> None:
        """Update price cache from WebSocket"""
        if not hasattr(self, "ws_price_cache"):
            self.ws_price_cache = {}
        self.ws_price_cache[symbol] = {"price": price, "timestamp": time.time()}
        self.ws_connected = True

    def get_active_positions(self) -> list[dict]:
        """Get list of active positions"""
        return list(self.active_positions.values())

    def get_position_count(self) -> int:
        """Get number of active positions"""
        return len(self.active_positions)

    async def record_position_close(self, symbol: str, pnl_usdc: float, pnl_pct: float):
        """
        Record position closure for risk management.

        Args:
            symbol: Trading symbol
            pnl_usdc: PnL in USDC
            pnl_pct: PnL in percentage
        """
        try:
            # Update Stage F with trade result
            self.risk_guard_f.record_trade_close(pnl_pct)

            # Block symbol if significant loss
            if pnl_pct < -1.5:  # Loss > 1.5%
                pause_symbol(symbol, minutes=120)
                self.logger.log_event(
                    "RISK_GUARD", "WARNING", f"{symbol} blocked for 2 hours after {pnl_pct:.2f}% loss"
                )
            elif pnl_pct < -1.0:  # Loss > 1%
                pause_symbol(symbol, minutes=60)
                self.logger.log_event("RISK_GUARD", "INFO", f"{symbol} blocked for 1 hour after {pnl_pct:.2f}% loss")

            # Log the closure
            self.logger.log_event("POSITION_CLOSE", "INFO", f"{symbol} closed: PnL ${pnl_usdc:.2f} ({pnl_pct:.2f}%)")

        except Exception as e:
            self.logger.log_event("POSITION_CLOSE", "ERROR", f"Failed to record close for {symbol}: {e}")

    async def has_position(self, symbol: str) -> bool:
        """Check if we have a position for a symbol"""
        return symbol in self.active_positions

    def reset_emergency_flag(self):
        """Reset emergency shutdown flag"""
        self.emergency_shutdown_flag = False
        self._clear_emergency_flag()

    def is_emergency_shutdown(self) -> bool:
        """Check if emergency shutdown is active"""
        return self.emergency_shutdown_flag

    async def place_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        quantity: float,
        price: float | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Place an order with pre-order precision normalization and validation.

        Applies PRICE_FILTER, LOT_SIZE, and MIN_NOTIONAL checks before sending.
        """
        try:
            # Determine current price for market orders
            current_price: float | None = None
            if (order_type or "").strip().upper() == "MARKET":
                try:
                    ticker = await self.exchange.get_ticker(symbol)
                    if ticker:
                        last_val = ticker.get("last") or ticker.get("close")
                        current_price = float(last_val) if last_val is not None else None
                except Exception:
                    current_price = None

            # Pull market schema once from exchange client
            try:
                markets = await self.exchange.get_markets()
                market_schema = markets.get(symbol, {})
            except Exception:
                market_schema = {}

            # Normalize and validate against filters
            price_norm, qty_norm, _min_notional = normalize(
                price, float(quantity), market_schema, current_price, symbol
            )

            # Idempotent client order ID
            env = getattr(self.config, "ENV", "PROD")
            strategy = getattr(self.config, "STRATEGY", "DEFAULT")
            intent = self._intent_key(
                env=env,
                strategy=strategy,
                symbol=symbol,
                side=side,
                order_type=(order_type or "").upper(),
                qty_norm=qty_norm,
                price_norm=price_norm,
                tp=None,
                sl=None,
            )
            client_id = self.idem.get(intent) or make_client_id(env, strategy, symbol, side, intent)
            if self.idem.get(intent) is None:
                self.idem.put(intent, client_id)

            params = (params or {}) | {"newClientOrderId": client_id}
            self.logger.log_event("ORDER_MANAGER", "DEBUG", f"[IDEMP] intent={intent} clientId={client_id}")

            # Create order using normalized values
            return await self.exchange.create_order(symbol, order_type, side, qty_norm, price_norm, params)

        except PrecisionError:
            raise
        except Exception as e:
            # Map known filter failures to PrecisionError for clarity
            err_text = str(e)
            lowered = err_text.lower()
            if any(key in lowered for key in ("price_filter", "lot_size", "min_notional", "notional")):
                raise PrecisionError(f"Exchange filter rejection: {err_text}") from None
            raise

    async def shutdown(self, emergency: bool = False):
        """Shutdown OrderManager"""
        try:
            self.shutdown_requested = True

            if emergency:
                self.emergency_shutdown_flag = True
                self.shutdown_timestamp = time.time()
                self._save_emergency_flag()

                # Close all positions
                for symbol in list(self.active_positions.keys()):
                    await self.close_position_emergency(symbol)

            # Cancel all orders
            for symbol in list(self.active_positions.keys()):
                await self.cancel_all_orders(symbol)

            self.logger.log_event("ORDER_MANAGER", "INFO", f"OrderManager shutdown complete (emergency: {emergency})")

        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR", f"Failed to shutdown OrderManager: {e}")

    async def sync_with_exchange(self):
        """Синхронизация локального состояния с биржей каждые 30 сек"""
        try:
            # Получаем реальные позиции с биржи
            positions = await self.exchange.get_positions()
            exchange_positions = {p["symbol"]: p for p in positions if float(p.get("contracts", p.get("size", 0))) > 0}

            # Проверяем каждую позицию на наличие SL
            for symbol, pos in exchange_positions.items():
                open_orders = await self.exchange.get_open_orders(symbol)

                # Нормализованная проверка SL
                has_sl = False
                for o in open_orders:
                    otype = str(o.get("type") or o.get("info", {}).get("type") or "").upper()
                    is_reduce = (o.get("reduceOnly") is True) or (o.get("info", {}).get("reduceOnly") is True)
                    if (("STOP" in otype) or (otype in {"STOP", "STOP_MARKET"})) and is_reduce:
                        has_sl = True
                        break

                if not has_sl:
                    self.logger.log_event("SYNC", "CRITICAL", f"Position {symbol} WITHOUT SL - closing")
                    # Закрываем позицию без SL
                    side = "sell" if pos.get("side") == "long" else "buy"
                    qty = float(pos.get("contracts", pos.get("size", 0)))
                    await self.exchange.create_order(symbol, "market", side, qty, None, {"reduceOnly": True})

            # Убираем висячие ордера без позиций
            all_orders = await self.exchange.get_open_orders()
            for order in all_orders:
                is_reduce = (order.get("reduceOnly") is True) or (order.get("info", {}).get("reduceOnly") is True)
                if is_reduce and order["symbol"] not in exchange_positions:
                    await self.exchange.cancel_order(order["id"], order["symbol"])
                    self.logger.log_event("SYNC", "INFO", f"Cancelled orphan order {order['id']}")

        except Exception as e:
            self.logger.log_event("SYNC", "ERROR", f"Sync failed: {e}")


# Helper: cleanup stray reduceOnly orders by prefix when no position
async def cleanup_stray_orders(exchange_client: OptimizedExchangeClient, symbol: str, prefix: str) -> dict[str, int]:
    """Cancel reduceOnly orders for a symbol that are tagged with clientOrderId starting with prefix,
    only when there is no open position. Returns stats dict.
    """
    cancelled = 0
    kept = 0
    try:
        try:
            pos = await exchange_client.get_position(symbol)
        except Exception:
            pos = None
        has_pos = False
        try:
            size_val = float((pos or {}).get("contracts", (pos or {}).get("size", 0)) or 0)
            has_pos = abs(size_val) > 0
        except Exception:
            has_pos = False

        orders = []
        try:
            orders = await exchange_client.get_open_orders(symbol)
        except Exception:
            orders = []

        for order in orders or []:
            try:
                info = order.get("info", {}) or {}
                ro = bool(order.get("reduceOnly") is True or info.get("reduceOnly") is True)
                coid = order.get("clientOrderId") or info.get("clientOrderId") or ""
                if ro and (prefix and str(coid).startswith(prefix)) and not has_pos:
                    try:
                        await exchange_client.cancel_order(order["id"], symbol)
                        cancelled += 1
                    except Exception:
                        kept += 1
                else:
                    kept += 1
            except Exception:
                kept += 1
    except Exception:
        pass
    return {"cancelled": cancelled, "kept": kept}
