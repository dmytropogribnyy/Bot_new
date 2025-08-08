#!/usr/bin/env python3
"""
Order Manager for BinanceBot v2.1
Simplified version based on v2 structure
"""

import asyncio
import json
import time
from typing import Any, Dict, List, Optional

from core.config import TradingConfig
from core.exchange_client import OptimizedExchangeClient
from core.unified_logger import UnifiedLogger


class OrderManager:
    """Comprehensive order and position management system"""

    def __init__(self, config: TradingConfig, exchange: OptimizedExchangeClient,
                 logger: UnifiedLogger):
        self.config = config
        self.exchange = exchange
        self.logger = logger

        # Position and order tracking
        self.active_positions: Dict[str, Dict] = {}  # symbol -> position_data
        self.pending_orders: Dict[str, List[Dict]] = {}  # symbol -> [orders]
        self.tp_orders: Dict[str, List[Dict]] = {}  # symbol -> [tp_orders]
        self.sl_orders: Dict[str, Dict] = {}  # symbol -> sl_order

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

    def _load_emergency_flag(self):
        """Load emergency shutdown flag from file"""
        try:
            import os
            if os.path.exists(self.emergency_flag_file):
                with open(self.emergency_flag_file) as f:
                    flag_data = f.read().strip()
                    if flag_data == 'EMERGENCY_SHUTDOWN':
                        self.emergency_shutdown_flag = True
                        self.logger.log_event("ORDER_MANAGER", "WARNING",
                            "Emergency shutdown flag detected from previous run")
        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR", f"Failed to load emergency flag: {e}")

    def _save_emergency_flag(self):
        """Save emergency shutdown flag to file"""
        try:
            import os
            os.makedirs(os.path.dirname(self.emergency_flag_file), exist_ok=True)
            with open(self.emergency_flag_file, 'w') as f:
                f.write('EMERGENCY_SHUTDOWN')
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
            positions = await self.exchange.get_all_positions()

            async with self.position_lock:
                self.active_positions.clear()

                for position in positions:
                    symbol = position['symbol']
                    size = float(position['size'])

                    if size != 0:
                        self.active_positions[symbol] = {
                            'symbol': symbol,
                            'size': size,
                            'side': 'long' if size > 0 else 'short',
                            'entry_price': float(position['entryPrice']),
                            'mark_price': float(position['markPrice']),
                            'unrealized_pnl': float(position['unrealizedPnl']),
                            'leverage': int(position['leverage']),
                            'timestamp': time.time()
                        }

            self.logger.log_event("ORDER_MANAGER", "DEBUG",
                                f"Synced {len(self.active_positions)} positions from exchange")

        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR", f"Failed to sync positions: {e}")

    async def place_position_with_tp_sl(self, symbol: str, side: str, quantity: float,
                                       entry_price: float, leverage: int = 5) -> Dict[str, Any]:
        """Place position with TP/SL orders"""
        try:
            # Check if we already have a position
            if symbol in self.active_positions:
                self.logger.log_event("ORDER_MANAGER", "WARNING",
                                    f"Position already exists for {symbol}")
                return {"success": False, "reason": "Position already exists"}

            # Check position limit
            if len(self.active_positions) >= self.config.max_positions:
                self.logger.log_event("ORDER_MANAGER", "WARNING",
                                    f"Maximum positions reached ({self.config.max_positions})")
                return {"success": False, "reason": "Maximum positions reached"}

            # Set leverage
            try:
                await self.exchange.exchange.set_leverage(leverage, symbol)
            except Exception as e:
                self.logger.log_event("ORDER_MANAGER", "WARNING",
                                    f"Failed to set leverage for {symbol}: {e}")

            # Place market order
            order = await self.exchange.create_market_order(symbol, side, quantity)

            if not order or 'id' not in order:
                return {"success": False, "reason": "Failed to place order"}

            # Calculate TP/SL levels
            sl_price = self.calculate_stop_loss(entry_price, side)
            tp_levels = self.calculate_take_profit_levels(entry_price, side)

            # Place TP/SL orders
            tp_sl_result = await self.place_tp_sl_orders(symbol, side, quantity, entry_price)

            # Update active positions
            async with self.position_lock:
                self.active_positions[symbol] = {
                    'symbol': symbol,
                    'size': quantity,
                    'side': side,
                    'entry_price': entry_price,
                    'mark_price': entry_price,
                    'unrealized_pnl': 0,
                    'leverage': leverage,
                    'order_id': order['id'],
                    'timestamp': time.time()
                }

            self.logger.log_event("ORDER_MANAGER", "INFO",
                                f"Position opened: {symbol} {side} {quantity} @ {entry_price}")

            return {
                "success": True,
                "order_id": order['id'],
                "entry_price": entry_price,
                "sl_price": sl_price,
                "tp_levels": tp_levels,
                "tp_sl_orders": tp_sl_result
            }

        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR",
                                f"Failed to place position for {symbol}: {e}")
            return {"success": False, "reason": str(e)}

    async def place_tp_sl_orders(self, symbol: str, side: str, quantity: float,
                                entry_price: float) -> Dict[str, Any]:
        """Place take profit and stop loss orders"""
        try:
            # Calculate prices
            sl_price = self.calculate_stop_loss(entry_price, side)
            tp_levels = self.calculate_take_profit_levels(entry_price, side)

            # Place stop loss order
            sl_order = await self.exchange.create_stop_loss_order(
                symbol, side, quantity, sl_price
            )

            # Place take profit orders
            tp_orders = []
            for tp_price, tp_quantity in tp_levels:
                tp_order = await self.exchange.create_take_profit_order(
                    symbol, side, tp_quantity, tp_price
                )
                tp_orders.append(tp_order)

            # Store orders
            async with self.order_lock:
                self.sl_orders[symbol] = sl_order
                self.tp_orders[symbol] = tp_orders

            self.logger.log_event("ORDER_MANAGER", "INFO",
                                f"Placed TP/SL orders for {symbol}: SL@{sl_price}, TP@{[tp[1] for tp in tp_levels]}")

            return {
                "sl_order": sl_order,
                "tp_orders": tp_orders,
                "sl_price": sl_price,
                "tp_prices": [tp[1] for tp in tp_levels]
            }

        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR",
                                f"Failed to place TP/SL orders for {symbol}: {e}")
            return {"success": False, "reason": str(e)}

    def calculate_stop_loss(self, entry_price: float, side: str) -> float:
        """Calculate stop loss price"""
        if side == 'buy':
            return entry_price * (1 - self.config.stop_loss_percent / 100)
        else:
            return entry_price * (1 + self.config.stop_loss_percent / 100)

    def calculate_take_profit_levels(self, entry_price: float, side: str) -> List[tuple[float, float]]:
        """Calculate take profit levels"""
        if side == 'buy':
            tp1_price = entry_price * (1 + self.config.take_profit_percent / 100)
            tp2_price = entry_price * (1 + (self.config.take_profit_percent * 1.5) / 100)
        else:
            tp1_price = entry_price * (1 - self.config.take_profit_percent / 100)
            tp2_price = entry_price * (1 - (self.config.take_profit_percent * 1.5) / 100)

        # Split quantity: 70% at TP1, 30% at TP2
        return [(tp1_price, 0.7), (tp2_price, 0.3)]

    async def close_position_emergency(self, symbol: str) -> Dict[str, Any]:
        """Emergency close position"""
        try:
            position = self.active_positions.get(symbol)
            if not position:
                return {"success": False, "reason": "Position not found"}

            # Cancel all orders first
            await self.cancel_all_orders(symbol)

            # Close position with market order
            side = 'sell' if position['side'] == 'long' else 'buy'
            order = await self.exchange.create_market_order(
                symbol, side, abs(position['size'])
            )

            # Remove from tracking
            async with self.position_lock:
                self.active_positions.pop(symbol, None)

            self.logger.log_event("ORDER_MANAGER", "WARNING",
                                f"Emergency closed position: {symbol}")

            return {"success": True, "order": order}

        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR",
                                f"Failed to emergency close {symbol}: {e}")
            return {"success": False, "reason": str(e)}

    async def cancel_all_orders(self, symbol: str):
        """Cancel all orders for a symbol"""
        try:
            await self.exchange.cancel_all_orders(symbol)

            # Clear from tracking
            async with self.order_lock:
                self.sl_orders.pop(symbol, None)
                self.tp_orders.pop(symbol, None)

            self.logger.log_event("ORDER_MANAGER", "INFO",
                                f"Cancelled all orders for {symbol}")

        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR",
                                f"Failed to cancel orders for {symbol}: {e}")

    async def cleanup_hanging_orders(self):
        """Clean up hanging orders"""
        try:
            open_orders = await self.exchange.get_open_orders()

            for order in open_orders:
                order_age = time.time() - (order.get('timestamp', 0) / 1000)

                if order_age > self.order_timeout:
                    try:
                        await self.exchange.cancel_order(order['id'], order['symbol'])
                        self.logger.log_event("ORDER_MANAGER", "INFO",
                                            f"Cleaned up hanging order: {order['id']}")
                    except Exception as e:
                        self.logger.log_event("ORDER_MANAGER", "WARNING",
                                            f"Failed to cancel hanging order {order['id']}: {e}")

        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR", f"Failed to cleanup hanging orders: {e}")

    async def monitor_positions(self):
        """Monitor active positions"""
        try:
            for symbol, position in list(self.active_positions.items()):
                # Check if position still exists on exchange
                current_position = await self.exchange.get_position(symbol)

                if not current_position:
                    # Position was closed
                    async with self.position_lock:
                        self.active_positions.pop(symbol, None)

                    # Clean up orders
                    await self.cancel_all_orders(symbol)

                    self.logger.log_event("ORDER_MANAGER", "INFO",
                                        f"Position closed on exchange: {symbol}")

                else:
                    # Update position data
                    async with self.position_lock:
                        self.active_positions[symbol].update({
                            'mark_price': float(current_position['markPrice']),
                            'unrealized_pnl': float(current_position['unrealizedPnl'])
                        })

        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR", f"Failed to monitor positions: {e}")

    async def check_order_executions(self):
        """Check for executed orders"""
        try:
            for symbol in list(self.active_positions.keys()):
                # Check TP orders
                if symbol in self.tp_orders:
                    for tp_order in self.tp_orders[symbol]:
                        order_status = await self.exchange.get_order(tp_order['id'], symbol)
                        if order_status and order_status['status'] == 'closed':
                            self.logger.log_event("ORDER_MANAGER", "INFO",
                                                f"Take profit executed: {symbol} @ {order_status['price']}")

                # Check SL order
                if symbol in self.sl_orders:
                    sl_order = self.sl_orders[symbol]
                    order_status = await self.exchange.get_order(sl_order['id'], symbol)
                    if order_status and order_status['status'] == 'closed':
                        self.logger.log_event("ORDER_MANAGER", "WARNING",
                                            f"Stop loss executed: {symbol} @ {order_status['price']}")

        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR", f"Failed to check order executions: {e}")

    async def check_timeouts(self):
        """Check for order timeouts"""
        try:
            current_time = time.time()

            for symbol in list(self.active_positions.keys()):
                position = self.active_positions[symbol]
                position_age = current_time - position.get('timestamp', 0)

                # Check for emergency stop loss
                if (self.config.emergency_stop_enabled and
                    position_age > 3600):  # 1 hour

                    unrealized_pnl = position.get('unrealized_pnl', 0)
                    entry_price = position.get('entry_price', 0)
                    mark_price = position.get('mark_price', 0)

                    if entry_price > 0:
                        loss_percent = abs(mark_price - entry_price) / entry_price * 100

                        if loss_percent > self.config.emergency_stop_loss:
                            self.logger.log_event("ORDER_MANAGER", "WARNING",
                                                f"Emergency stop loss triggered for {symbol}: {loss_percent:.2f}%")
                            await self.close_position_emergency(symbol)

        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR", f"Failed to check timeouts: {e}")

    def get_active_positions(self) -> List[Dict]:
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

            self.logger.log_event("ORDER_MANAGER", "INFO",
                                f"OrderManager shutdown complete (emergency: {emergency})")

        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR", f"Failed to shutdown OrderManager: {e}")
