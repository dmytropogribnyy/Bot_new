#!/usr/bin/env python3
"""
Exchange Client for BinanceBot v2.1
Simplified version based on v2 structure
"""

import asyncio
import time
from typing import Any

import ccxt.async_support as ccxt

from core.config import TradingConfig
from core.symbol_utils import ensure_perp_usdc_format
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
                "apiKey": self.config.api_key,
                "secret": self.config.api_secret,
                "sandbox": self.config.testnet,
                "enableRateLimit": True,
                "options": {
                    "defaultType": "future",
                    "adjustForTimeDifference": True,
                    "recvWindow": 60000,
                },
            }

            # Remove sandbox config, let ccxt handle it
            # if self.config.testnet - ccxt will use set_sandbox_mode instead

            self.exchange = ccxt.binance(exchange_config)

            # Enable testnet mode if configured
            if self.config.testnet:
                self.exchange.set_sandbox_mode(True)
                self.logger.log_event("EXCHANGE", "INFO", "Testnet mode enabled")

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
        """Test exchange connection (USDC-focused, without hardcoded tickers)"""
        try:
            # Public API: load markets
            await self.exchange.load_markets()
            self.logger.log_event("EXCHANGE", "DEBUG", "Markets loaded (public API OK)")

            # Private API: fetch balance (skip in DRY RUN or when no keys configured)
            if self.config.dry_run or not (self.config.api_key and self.config.api_secret):
                self.logger.log_event("EXCHANGE", "DEBUG", "Skipping private API check (dry-run or no keys)")
            else:
                try:
                    await self.exchange.fetch_balance()
                    self.logger.log_event("EXCHANGE", "DEBUG", "Balance fetched (private API OK)")
                except Exception as e:
                    # On testnet allow public-only mode even if private check fails
                    if self.config.testnet:
                        self.logger.log_event(
                            "EXCHANGE",
                            "WARNING",
                            f"Private API check failed on testnet, continuing with public-only mode: {e}",
                        )
                    else:
                        raise

        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"Connection test failed: {e}")
            raise

    async def _set_default_leverage(self):
        """Set default leverage for USDC-margined futures"""
        try:
            try:
                if self.config.testnet:
                    symbols = await self.get_usdt_futures_symbols()
                else:
                    symbols = await self.get_usdc_futures_symbols()
            except Exception:
                symbols = []

            # Fallback: use config symbols by environment if discovery failed
            if not symbols:
                if self.config.testnet:
                    fallback = [
                        "BTC/USDT:USDT",
                        "ETH/USDT:USDT",
                        "BNB/USDT:USDT",
                        "SOL/USDT:USDT",
                        "ADA/USDT:USDT",
                    ]
                else:
                    fallback = getattr(self.config, "usdc_symbols", []) or []
                    # Ensure Binance perpetual format when possible
                    fallback = [
                        s if s.endswith(":USDC") else (s + ":USDC" if s.endswith("/USDC") else s) for s in fallback
                    ]
                symbols = fallback

            for pair in symbols[:5]:  # limit to a small set on init
                try:
                    await self.exchange.set_leverage(self.config.default_leverage, pair)
                    msg = f"Set leverage {self.config.default_leverage} for {pair}"
                    self.logger.log_event("EXCHANGE", "DEBUG", msg)
                except Exception as e:
                    self.logger.log_event("EXCHANGE", "WARNING", f"Failed to set leverage for {pair}: {e}")

        except Exception as e:
            self.logger.log_event("EXCHANGE", "WARNING", f"Failed to set default leverage: {e}")

    async def get_balance(self, force_refresh: bool = False) -> dict[str, Any]:
        """Get account balance with caching"""
        try:
            current_time = time.time()

            # Use cached balance if available and not expired
            if (
                not force_refresh
                and self.cached_balance
                and current_time - self.last_balance_check < self.balance_cache_duration
            ):
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
            return float(balance.get("USDT", {}).get("free", 0))
        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"Failed to get USDT balance: {e}")
            return 0.0

    async def get_usdc_balance(self) -> float:
        """Get USDC balance specifically"""
        try:
            balance = await self.get_balance()
            return float(balance.get("USDC", {}).get("free", 0))
        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"Failed to get USDC balance: {e}")
            return 0.0

    async def get_position(self, symbol: str) -> dict[str, Any] | None:
        """Get current position for a symbol"""
        try:
            await self._rate_limit()
            positions = await self.exchange.fetch_positions([symbol])

            for position in positions:
                if position.get("symbol") != symbol:
                    continue
                try:
                    size_val = float(position.get("size", position.get("contracts", 0)))
                except Exception:
                    size_val = 0.0
                if size_val != 0:
                    return position

            return None

        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"Failed to get position for {symbol}: {e}")
            return None

    async def get_all_positions(self) -> list[dict[str, Any]]:
        """Get all open positions"""
        try:
            await self._rate_limit()
            positions = await self.exchange.fetch_positions()

            # Filter only open positions, tolerant to size/"contracts" keys
            open_positions: list[dict[str, Any]] = []
            for pos in positions:
                try:
                    val = float(pos.get("size", pos.get("contracts", 0)))
                except Exception:
                    val = 0.0
                if val != 0:
                    open_positions.append(pos)

            return open_positions

        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"Failed to get all positions: {e}")
            return []

    async def create_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        amount: float,
        price: float | None = None,
        params: dict[str, Any] = None,
    ) -> dict[str, Any]:
        """Create an order"""
        try:
            await self._rate_limit()

            order_params = params or {}
            # Only send validation-only orders in DRY_RUN mode
            if self.config.dry_run:
                order_params["test"] = True

            normalized_type = self._normalize_order_type(order_type, price)

            order = await self.exchange.create_order(
                symbol=symbol, type=normalized_type, side=side, amount=amount, price=price, params=order_params
            )

            self.logger.log_event(
                "EXCHANGE",
                "INFO",
                f"Created order: {symbol} {side} {amount} @ {price or 'market'}",
                {"order_id": order.get("id"), "type": order_type},
            )

            return order

        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"Failed to create order for {symbol}: {e}")
            raise

    async def create_market_order(self, symbol: str, side: str, amount: float) -> dict[str, Any]:
        """Create a market order"""
        return await self.create_order(symbol, "market", side, amount)

    async def create_limit_order(self, symbol: str, side: str, amount: float, price: float) -> dict[str, Any]:
        """Create a limit order"""
        return await self.create_order(symbol, "limit", side, amount, price)

    async def create_stop_loss_order(self, symbol: str, side: str, amount: float, stop_price: float) -> dict[str, Any]:
        """Create a stop loss order (STOP/STOP_MARKET) with reduceOnly"""
        params = {"stopPrice": stop_price, "reduceOnly": True}
        # Prefer STOP_MARKET for SL
        return await self.create_order(symbol, "STOP_MARKET", side, amount, None, params)

    async def create_take_profit_order(
        self, symbol: str, side: str, amount: float, take_profit_price: float
    ) -> dict[str, Any]:
        """Create a take profit order (TAKE_PROFIT/TAKE_PROFIT_MARKET) with reduceOnly"""
        params = {"stopPrice": take_profit_price, "reduceOnly": True}
        # Use TAKE_PROFIT for limit-style TP when providing price
        return await self.create_order(symbol, "TAKE_PROFIT", side, amount, take_profit_price, params)

    async def cancel_order(self, order_id: str, symbol: str) -> dict[str, Any]:
        """Cancel an order"""
        try:
            await self._rate_limit()
            result = await self.exchange.cancel_order(order_id, symbol)

            self.logger.log_event("EXCHANGE", "INFO", f"Cancelled order {order_id} for {symbol}")

            return result

        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"Failed to cancel order {order_id}: {e}")
            raise

    async def cancel_all_orders(self, symbol: str) -> list[dict[str, Any]]:
        """Cancel all orders for a symbol"""
        try:
            await self._rate_limit()
            result = await self.exchange.cancel_all_orders(symbol)

            self.logger.log_event("EXCHANGE", "INFO", f"Cancelled all orders for {symbol}")

            return result

        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"Failed to cancel all orders for {symbol}: {e}")
            return []

    async def get_order(self, order_id: str, symbol: str) -> dict[str, Any] | None:
        """Get order details"""
        try:
            await self._rate_limit()
            return await self.exchange.fetch_order(order_id, symbol)
        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"Failed to get order {order_id}: {e}")
            return None

    async def get_open_orders(self, symbol: str = None) -> list[dict[str, Any]]:
        """Get open orders"""
        try:
            await self._rate_limit()
            return await self.exchange.fetch_open_orders(symbol)
        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"Failed to get open orders: {e}")
            return []

    async def get_ticker(self, symbol: str) -> dict[str, Any] | None:
        """Get ticker for a symbol"""
        try:
            await self._rate_limit()
            return await self.exchange.fetch_ticker(symbol)
        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"Failed to get ticker for {symbol}: {e}")
            return None

    async def get_ohlcv(self, symbol: str, timeframe: str = "1m", limit: int = 100) -> list[list[float]]:
        """Get OHLCV data"""
        try:
            await self._rate_limit()
            return await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"Failed to get OHLCV for {symbol}: {e}")
            return []

    async def get_markets(self) -> dict[str, Any]:
        """Get available markets"""
        try:
            if not self.exchange.markets:
                await self.exchange.load_markets()
            return self.exchange.markets
        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"Failed to get markets: {e}")
            return {}

    async def fetch_markets(self) -> dict[str, Any]:
        """Compatibility wrapper for components expecting fetch_markets()"""
        return await self.get_markets()

    async def get_usdc_futures_symbols(self) -> list[str]:
        """Get USDC-margined futures symbols"""
        try:
            markets = await self.get_markets()
            usdc_symbols = []

            for symbol, market in markets.items():
                market_type = market.get("type")
                quote = market.get("quote")
                settle = market.get("settle")
                is_active = market.get("active", True)
                is_contract = market.get("contract", False)

                # Accept Binance USDⓈ-M perpetuals (swap) and be tolerant to schema variations
                if (
                    is_active
                    and is_contract
                    and (quote == "USDC" or settle == "USDC")
                    and (market_type in ("swap", "future", None))
                ):
                    usdc_symbols.append(symbol)

            # Ensure consistent perpetual USDC symbol format
            return [ensure_perp_usdc_format(s) for s in usdc_symbols]

        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"Failed to get USDC symbols: {e}")
            return []

    async def get_usdt_futures_symbols(self) -> list[str]:
        """Get USDT-margined futures symbols (used on testnet)."""
        try:
            markets = await self.get_markets()
            symbols: list[str] = []
            for symbol, market in markets.items():
                market_type = market.get("type")
                quote = market.get("quote")
                settle = market.get("settle")
                is_active = market.get("active", True)
                is_contract = market.get("contract", False)
                if (
                    is_active
                    and is_contract
                    and (quote == "USDT" or settle == "USDT")
                    and (market_type in ("swap", "future", None))
                ):
                    symbols.append(symbol)
            return symbols
        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"Failed to get USDT symbols: {e}")
            return []

    async def _rate_limit(self):
        """Simple rate limiting"""
        current_time = time.time()

        if current_time - self.last_request_time < 1.0 / self.max_requests_per_second:
            await asyncio.sleep(0.1)

        self.last_request_time = current_time
        self.request_count += 1

    async def health_check(self) -> bool:
        """Check exchange connection health (no hardcoded USDT dependency)"""
        try:
            current_time = time.time()

            # Only check if enough time has passed
            if current_time - self.last_health_check < self.health_check_interval:
                return self.connection_healthy

            # Public + (optional) private quick checks
            await self.exchange.load_markets()
            if not self.config.dry_run and (self.config.api_key and self.config.api_secret):
                try:
                    await self.exchange.fetch_balance()
                except Exception as e:
                    if not self.config.testnet:
                        raise
                    # On testnet tolerate private fetch failures
                    self.logger.log_event("EXCHANGE", "WARNING", f"Health check: private fetch failed on testnet: {e}")

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

    def _normalize_order_type(self, order_type: str, price: float | None) -> str:
        """Normalize human-friendly order type names to ccxt binance unified types.

        Supported inputs:
          - STOP_MARKET, stop_market, stopLossMarket → stopLossMarket
          - STOP, stop, stop_loss → stopLoss (requires price)
          - TAKE_PROFIT, take_profit → takeProfit (requires price)
          - TAKE_PROFIT_MARKET, take_profit_market → takeProfitMarket
          - market, limit → passthrough
        """
        t = (order_type or "").strip().lower().replace(" ", "").replace("_", "")

        if t in ("stopmarket", "stoplossmarket", "slm"):
            return "stopLossMarket"
        if t in ("stop", "stoploss"):
            return "stopLoss"
        if t in ("takeprofitmarket", "tpmarket"):
            return "takeProfitMarket"
        if t in ("takeprofit", "tp"):
            return "takeProfit"
        if t in ("limit", "market"):
            return t
        # Fallback: if price provided assume limit-like, else market-like
        return "limit" if price is not None else "market"
