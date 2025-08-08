#!/usr/bin/env python3
"""
Exchange Client for BinanceBot v2.1
Simplified version based on v2 structure
"""

import asyncio
import time
from typing import Any, Dict, List, Optional, Tuple

import ccxt.async_support as ccxt
from core.config import TradingConfig
from core.unified_logger import UnifiedLogger


class OptimizedExchangeClient:
    """Optimized exchange client for Binance USDC-margined futures"""

    def __init__(self, config: TradingConfig, logger: UnifiedLogger):
        self.config = config
        self.logger = logger
        self.exchange = None
        self.is_initialized = False
        self.last_balance_check = 0
        self.cached_balance = None
        self.balance_cache_duration = 30  # seconds

        # Rate limiting
        self.request_count = 0
        self.last_request_time = 0
        self.max_requests_per_second = 10

        # Connection status
        self.connection_healthy = False
        self.last_health_check = 0
        self.health_check_interval = 60  # seconds

    async def initialize(self):
        """Initialize exchange connection"""
        try:
            self.logger.log_event("EXCHANGE", "INFO", "Initializing exchange connection...")

            # Create exchange instance
            exchange_config = {
                'apiKey': self.config.api_key,
                'secret': self.config.api_secret,
                'sandbox': self.config.testnet,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future',
                    'adjustForTimeDifference': True,
                    'recvWindow': 60000,
                }
            }

            if self.config.testnet:
                exchange_config['urls'] = {
                    'api': {
                        'public': 'https://testnet.binancefuture.com/fapi/v1',
                        'private': 'https://testnet.binancefuture.com/fapi/v1',
                    }
                }

            self.exchange = ccxt.binance(exchange_config)

            # Test connection
            await self._test_connection()

            # Load markets
            await self.exchange.load_markets()

            # Set default leverage
            await self._set_default_leverage()

            self.is_initialized = True
            self.connection_healthy = True
            self.last_health_check = time.time()

            self.logger.log_event("EXCHANGE", "INFO", "Exchange connection initialized successfully")

        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"Failed to initialize exchange: {e}")
            raise

    async def _test_connection(self):
        """Test exchange connection"""
        try:
            # Test public API
            await self.exchange.fetch_ticker('BTC/USDT')
            self.logger.log_event("EXCHANGE", "DEBUG", "Public API connection test passed")

            # Test private API
            await self.exchange.fetch_balance()
            self.logger.log_event("EXCHANGE", "DEBUG", "Private API connection test passed")

        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"Connection test failed: {e}")
            raise

    async def _set_default_leverage(self):
        """Set default leverage for USDC-margined futures"""
        try:
            # Set leverage for common pairs
            common_pairs = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'ADA/USDT', 'SOL/USDT']

            for pair in common_pairs:
                try:
                    await self.exchange.set_leverage(self.config.default_leverage, pair)
                    self.logger.log_event("EXCHANGE", "DEBUG", f"Set leverage {self.config.default_leverage} for {pair}")
                except Exception as e:
                    self.logger.log_event("EXCHANGE", "WARNING", f"Failed to set leverage for {pair}: {e}")

        except Exception as e:
            self.logger.log_event("EXCHANGE", "WARNING", f"Failed to set default leverage: {e}")

    async def get_balance(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get account balance with caching"""
        try:
            current_time = time.time()

            # Use cached balance if available and not expired
            if (not force_refresh and
                self.cached_balance and
                current_time - self.last_balance_check < self.balance_cache_duration):
                return self.cached_balance

            await self._rate_limit()
            balance = await self.exchange.fetch_balance()

            # Cache the balance
            self.cached_balance = balance
            self.last_balance_check = current_time

            return balance

        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"Failed to fetch balance: {e}")
            return self.cached_balance or {}

    async def get_usdt_balance(self) -> float:
        """Get USDT balance specifically"""
        try:
            balance = await self.get_balance()
            return float(balance.get('USDT', {}).get('free', 0))
        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"Failed to get USDT balance: {e}")
            return 0.0

    async def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get current position for a symbol"""
        try:
            await self._rate_limit()
            positions = await self.exchange.fetch_positions([symbol])

            for position in positions:
                if position['symbol'] == symbol and float(position['size']) != 0:
                    return position

            return None

        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"Failed to get position for {symbol}: {e}")
            return None

    async def get_all_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions"""
        try:
            await self._rate_limit()
            positions = await self.exchange.fetch_positions()

            # Filter only open positions
            open_positions = [
                pos for pos in positions
                if float(pos['size']) != 0
            ]

            return open_positions

        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"Failed to get all positions: {e}")
            return []

    async def create_order(self, symbol: str, order_type: str, side: str,
                          amount: float, price: Optional[float] = None,
                          params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create an order"""
        try:
            await self._rate_limit()

            order_params = params or {}
            if self.config.testnet:
                order_params['test'] = True

            order = await self.exchange.create_order(
                symbol=symbol,
                type=order_type,
                side=side,
                amount=amount,
                price=price,
                params=order_params
            )

            self.logger.log_event("EXCHANGE", "INFO",
                                f"Created order: {symbol} {side} {amount} @ {price or 'market'}",
                                {"order_id": order.get('id'), "type": order_type})

            return order

        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR",
                                f"Failed to create order for {symbol}: {e}")
            raise

    async def create_market_order(self, symbol: str, side: str, amount: float) -> Dict[str, Any]:
        """Create a market order"""
        return await self.create_order(symbol, 'market', side, amount)

    async def create_limit_order(self, symbol: str, side: str, amount: float, price: float) -> Dict[str, Any]:
        """Create a limit order"""
        return await self.create_order(symbol, 'limit', side, amount, price)

    async def create_stop_loss_order(self, symbol: str, side: str, amount: float,
                                    stop_price: float) -> Dict[str, Any]:
        """Create a stop loss order"""
        params = {
            'stopPrice': stop_price,
            'type': 'stop'
        }
        return await self.create_order(symbol, 'stop', side, amount, stop_price, params)

    async def create_take_profit_order(self, symbol: str, side: str, amount: float,
                                     take_profit_price: float) -> Dict[str, Any]:
        """Create a take profit order"""
        params = {
            'stopPrice': take_profit_price,
            'type': 'take_profit'
        }
        return await self.create_order(symbol, 'limit', side, amount, take_profit_price, params)

    async def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """Cancel an order"""
        try:
            await self._rate_limit()
            result = await self.exchange.cancel_order(order_id, symbol)

            self.logger.log_event("EXCHANGE", "INFO",
                                f"Cancelled order {order_id} for {symbol}")

            return result

        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR",
                                f"Failed to cancel order {order_id}: {e}")
            raise

    async def cancel_all_orders(self, symbol: str) -> List[Dict[str, Any]]:
        """Cancel all orders for a symbol"""
        try:
            await self._rate_limit()
            result = await self.exchange.cancel_all_orders(symbol)

            self.logger.log_event("EXCHANGE", "INFO",
                                f"Cancelled all orders for {symbol}")

            return result

        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR",
                                f"Failed to cancel all orders for {symbol}: {e}")
            return []

    async def get_order(self, order_id: str, symbol: str) -> Optional[Dict[str, Any]]:
        """Get order details"""
        try:
            await self._rate_limit()
            return await self.exchange.fetch_order(order_id, symbol)
        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR",
                                f"Failed to get order {order_id}: {e}")
            return None

    async def get_open_orders(self, symbol: str = None) -> List[Dict[str, Any]]:
        """Get open orders"""
        try:
            await self._rate_limit()
            return await self.exchange.fetch_open_orders(symbol)
        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR",
                                f"Failed to get open orders: {e}")
            return []

    async def get_ticker(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get ticker for a symbol"""
        try:
            await self._rate_limit()
            return await self.exchange.fetch_ticker(symbol)
        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR",
                                f"Failed to get ticker for {symbol}: {e}")
            return None

    async def get_ohlcv(self, symbol: str, timeframe: str = '1m',
                        limit: int = 100) -> List[List[float]]:
        """Get OHLCV data"""
        try:
            await self._rate_limit()
            return await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR",
                                f"Failed to get OHLCV for {symbol}: {e}")
            return []

    async def get_markets(self) -> Dict[str, Any]:
        """Get available markets"""
        try:
            if not self.exchange.markets:
                await self.exchange.load_markets()
            return self.exchange.markets
        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"Failed to get markets: {e}")
            return {}

    async def get_usdc_futures_symbols(self) -> List[str]:
        """Get USDC-margined futures symbols"""
        try:
            markets = await self.get_markets()
            usdc_symbols = []

            for symbol, market in markets.items():
                if (market['type'] == 'future' and
                    market['quote'] == 'USDT' and
                    market['active']):
                    usdc_symbols.append(symbol)

            return usdc_symbols

        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"Failed to get USDC symbols: {e}")
            return []

    async def _rate_limit(self):
        """Simple rate limiting"""
        current_time = time.time()

        if current_time - self.last_request_time < 1.0 / self.max_requests_per_second:
            await asyncio.sleep(0.1)

        self.last_request_time = current_time
        self.request_count += 1

    async def health_check(self) -> bool:
        """Check exchange connection health"""
        try:
            current_time = time.time()

            # Only check if enough time has passed
            if current_time - self.last_health_check < self.health_check_interval:
                return self.connection_healthy

            # Test connection
            await self.get_ticker('BTC/USDT')

            self.connection_healthy = True
            self.last_health_check = current_time

            return True

        except Exception as e:
            self.logger.log_event("EXCHANGE", "WARNING", f"Health check failed: {e}")
            self.connection_healthy = False
            return False

    async def close(self):
        """Close exchange connection"""
        try:
            if self.exchange:
                await self.exchange.close()
                self.logger.log_event("EXCHANGE", "INFO", "Exchange connection closed")
        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"Failed to close exchange: {e}")

    def is_connected(self) -> bool:
        """Check if exchange is connected"""
        return self.is_initialized and self.connection_healthy
