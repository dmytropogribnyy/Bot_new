#!/usr/bin/env python3
"""
Order Manager for BinanceBot v2.1
Simplified version based on v2 structure
"""

import asyncio
import time
from pathlib import Path
from typing import Any

from core.config import TradingConfig
from core.exchange_client import OptimizedExchangeClient
from core.idempotency_store import IdempotencyStore
from core.ids import make_client_id
from core.precision import PrecisionError, normalize
from core.unified_logger import UnifiedLogger


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

        # Emergency shutdown flag (persistent)
        self.emergency_shutdown_flag = False
        self.shutdown_timestamp = None
        self.emergency_flag_file = "data/emergency_shutdown.flag"

        # Load emergency flag on initialization
        self._load_emergency_flag()

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

    def handle_ws_event(self, event: dict) -> None:
        """Handle WebSocket user data events"""
        event_type = event.get("e", "unknown")

        if event_type == "ORDER_TRADE_UPDATE":
            order = event.get("o", {})
            status = order.get("X")
            if status == "FILLED":
                self.logger.log_event("WS", "INFO", "Order filled via WS")

        elif event_type == "ACCOUNT_UPDATE":
            # Update positions from WS
            positions = event.get("a", {}).get("P", [])
            for pos in positions:
                symbol = pos.get("s")
                if symbol:
                    # Convert to ccxt format
                    quote = self.config.resolved_quote_coin
                    base = symbol[: -len(quote)]
                    ccxt_symbol = f"{base}/{quote}:{quote}"

                    position_amt = float(pos.get("pa", 0))
                    if abs(position_amt) > 0.001:
                        self.active_positions[ccxt_symbol] = {
                            "size": position_amt,
                            "entry_price": float(pos.get("ep", 0)),
                            "unrealized_pnl": float(pos.get("up", 0)),
                            "side": "buy" if position_amt > 0 else "sell",
                            "timestamp": time.time(),
                        }

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
