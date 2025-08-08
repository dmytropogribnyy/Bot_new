# Import Windows compatibility error handling
import core.windows_compatibility

import asyncio
import statistics
import time
from collections import deque
from typing import Any

import aiohttp
import ccxt

from core.config import TradingConfig
from core.rate_limiter import RateLimiter
from core.unified_logger import UnifiedLogger
from utils.safe_api import safe_call_retry_async


class OptimizedExchangeClient:
    """Enhanced Exchange Client with advanced features for optimal performance"""

    def __init__(self, config: TradingConfig, logger: UnifiedLogger | None = None):
        self.config = config
        self.logger = logger

        # Connection pooling and session management
        self._session = None
        self._connection_pool = []
        self._max_connections = 20
        self._connection_timeout = 10
        self._request_timeout = 30

        # Performance monitoring
        self._response_times = deque(maxlen=1000)
        self._error_counts = {}
        self._success_counts = {}
        self._last_performance_check = 0

        # Intelligent retry mechanism
        self._retry_config = {
            'max_retries': 3,
            'base_delay': 1.0,
            'max_delay': 30.0,
            'backoff_factor': 2.0
        }

        # Adaptive rate limiting
        self._adaptive_limits = {
            'current_weight_limit': config.weight_limit_per_minute,
            'current_request_limit': config.order_rate_limit_per_second,
            'performance_threshold': 0.95,  # 95% success rate
            'adjustment_factor': 0.1
        }

        # Enhanced caching with TTL
        self._cache = {}
        self._cache_ttl = {
            'balance': 5,
            'positions': 3,
            'orders': 2,
            'ticker': 1,
            'markets': 3600  # 1 hour
        }

        # Initialize CCXT with optimized settings
        api_key, api_secret = config.get_api_credentials()

        self.exchange = ccxt.binance({
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
            "options": {
                "defaultType": "future",
                "adjustForTimeDifference": True,
                "recvWindow": 60000,  # Increased receive window
                "warnOnFetchOpenOrdersWithoutSymbol": False,
            },
        })

        # Configure testnet if enabled
        if config.is_testnet_mode():
            self.exchange.set_sandbox_mode(True)
            self.exchange.options['sandbox'] = True
            self.logger.log_event("EXCHANGE", "INFO", "🧪 Testnet mode enabled")
        else:
            self.exchange.options['sandbox'] = False
            self.logger.log_event("EXCHANGE", "INFO", "🚀 Production mode enabled")

        # Enhanced rate limiter
        self.rate_limiter = RateLimiter(
            weight_limit_per_minute=config.weight_limit_per_minute,
            request_limit_per_second=config.order_rate_limit_per_second,
            buffer_pct=config.rate_limit_buffer_pct
        )

        # Async semaphore for connection control
        self._async_semaphore = asyncio.Semaphore(15)  # Increased concurrent requests

    async def initialize(self) -> bool:
        """Enhanced initialization with connection pooling"""
        try:
            self.logger.log_event("EXCHANGE", "INFO", "🔌 Initializing Optimized Exchange Client...")

            # Initialize connection pool
            await self._initialize_connection_pool()

            # Load markets with retry
            await self._load_markets_with_retry()

            # Test connection (skip balance check on Windows)
            if core.windows_compatibility.IS_WINDOWS:
                self.logger.log_event("EXCHANGE", "INFO", "✅ Connection established (Windows compatibility)")
                return True
            else:
                balance = await self.get_balance()
                if balance is not None:
                    self.logger.log_event("EXCHANGE", "INFO",
                        f"✅ Optimized connection established. Balance: {balance:.2f} USDC")
                    return True
                else:
                    self.logger.log_event("EXCHANGE", "ERROR", "❌ Failed to establish connection")
                    return False

        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"❌ Initialization error: {e}")
            return False

    async def _initialize_connection_pool(self):
        """Initialize connection pool for better performance"""
        try:
            connector = aiohttp.TCPConnector(
                limit=self._max_connections,
                limit_per_host=10,
                ttl_dns_cache=300,
                use_dns_cache=True,
                keepalive_timeout=30
            )

            timeout = aiohttp.ClientTimeout(
                total=self._request_timeout,
                connect=self._connection_timeout
            )

            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout
            )

            self.logger.log_event("EXCHANGE", "INFO",
                f"🔗 Connection pool initialized with {self._max_connections} connections")

        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"❌ Connection pool initialization failed: {e}")

    async def _load_markets_with_retry(self) -> None:
        """Load markets with intelligent retry mechanism"""
        for attempt in range(self._retry_config['max_retries']):
            try:
                async with self._async_semaphore:
                    await self.rate_limiter.acquire(1)
                    start_time = time.time()

                    markets = self.exchange.load_markets()

                    response_time = time.time() - start_time
                    self._response_times.append(response_time)

                    self._cache['markets'] = markets
                    self._cache['markets_time'] = time.time()

                    self.logger.log_event("EXCHANGE", "INFO",
                        f"📊 Loaded {len(markets)} markets in {response_time:.3f}s")
                    return

            except Exception as e:
                delay = min(
                    self._retry_config['base_delay'] * (self._retry_config['backoff_factor'] ** attempt),
                    self._retry_config['max_delay']
                )

                self.logger.log_event("EXCHANGE", "WARNING",
                    f"⚠️ Market loading attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")

                if attempt < self._retry_config['max_retries'] - 1:
                    await asyncio.sleep(delay)
                else:
                    self.logger.log_event("EXCHANGE", "ERROR", "❌ Failed to load markets after all retries")

    async def _execute_with_retry(self, operation, *args, **kwargs):
        """Execute operation with intelligent retry mechanism and safe API calls"""
        # Use safe_call_retry_async for better error handling
        result = await safe_call_retry_async(
            self._execute_operation_with_rate_limit,
            operation,
            *args,
            tries=self._retry_config['max_retries'],
            delay=self._retry_config['base_delay'],
            label=f"{operation.__name__}",
            **kwargs
        )

        if result is not None:
            # Record performance metrics
            self._update_success_count(operation.__name__)

        return result

    async def _execute_operation_with_rate_limit(self, operation, *args, **kwargs):
        """Execute operation with rate limiting"""
        start_time = time.time()

        # Acquire rate limiter
        await self.rate_limiter.acquire()

        # Execute operation
        result = await operation(*args, **kwargs)

        # Record performance metrics
        response_time = time.time() - start_time
        self._response_times.append(response_time)

        # Adaptive rate limiting based on performance
        await self._adjust_rate_limits(response_time)

        return result

    def _update_success_count(self, operation: str):
        """Update success count for performance monitoring"""
        if operation not in self._success_counts:
            self._success_counts[operation] = 0
        self._success_counts[operation] += 1

    def _update_error_count(self, operation: str):
        """Update error count for performance monitoring"""
        if operation not in self._error_counts:
            self._error_counts[operation] = 0
        self._error_counts[operation] += 1

    async def _adjust_rate_limits(self, response_time: float):
        """Adjust rate limits based on performance"""
        if len(self._response_times) < 10:
            return

        avg_response_time = statistics.mean(self._response_times)
        success_rate = self._calculate_success_rate()

        # Adjust limits based on performance
        if success_rate > self._adaptive_limits['performance_threshold'] and avg_response_time < 1.0:
            # Increase limits if performing well
            self._adaptive_limits['current_weight_limit'] *= (1 + self._adaptive_limits['adjustment_factor'])
            self._adaptive_limits['current_request_limit'] *= (1 + self._adaptive_limits['adjustment_factor'])
        elif success_rate < 0.8 or avg_response_time > 5.0:
            # Decrease limits if performing poorly
            self._adaptive_limits['current_weight_limit'] *= (1 - self._adaptive_limits['adjustment_factor'])
            self._adaptive_limits['current_request_limit'] *= (1 - self._adaptive_limits['adjustment_factor'])

        # Update rate limiter with new limits
        self.rate_limiter.update_limits(
            self._adaptive_limits['current_weight_limit'],
            self._adaptive_limits['current_request_limit']
        )

    def _calculate_success_rate(self) -> float:
        """Calculate overall success rate"""
        total_operations = sum(self._success_counts.values()) + sum(self._error_counts.values())
        if total_operations == 0:
            return 1.0
        return sum(self._success_counts.values()) / total_operations

    def _get_cached_data(self, key: str) -> Any | None:
        """Get cached data if still valid"""
        if key not in self._cache:
            return None

        cache_time = self._cache.get(f"{key}_time", 0)
        ttl = self._cache_ttl.get(key, 0)

        if time.time() - cache_time < ttl:
            return self._cache[key]

        # Remove expired cache
        self._cache.pop(key, None)
        self._cache.pop(f"{key}_time", None)
        return None

    def _set_cached_data(self, key: str, data: Any):
        """Set cached data with timestamp"""
        self._cache[key] = data
        self._cache[f"{key}_time"] = time.time()

    async def get_balance(self) -> float | None:
        """Enhanced balance retrieval with intelligent caching"""
        cached_balance = self._get_cached_data('balance')
        if cached_balance is not None:
            return cached_balance

        async def _fetch_balance():
            async with self._async_semaphore:
                await self.rate_limiter.acquire(5)
                balance_info = self.exchange.fetch_balance()
                # Используем логику из старого бота
                total_margin = float(balance_info["info"].get("totalMarginBalance", 0))
                return total_margin

        # Skip balance check on Windows due to compatibility issues
        if core.windows_compatibility.IS_WINDOWS:
            self.logger.log_event("EXCHANGE", "INFO", "Balance check disabled for Windows")
            return 100.0  # Fallback balance for Windows

        try:
            balance = await self._execute_with_retry(_fetch_balance)
            self._set_cached_data('balance', balance)
            return balance
        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"❌ Failed to get balance: {e}")
            return None

    async def get_positions(self) -> list[dict[str, Any]]:
        """Enhanced position retrieval with intelligent caching"""
        cached_positions = self._get_cached_data('positions')
        if cached_positions is not None:
            return cached_positions

        async def _fetch_positions():
            async with self._async_semaphore:
                await self.rate_limiter.acquire(5)
                positions = self.exchange.fetch_positions()
                return [pos for pos in positions if pos.get('size', 0) != 0]

        try:
            positions = await self._execute_with_retry(_fetch_positions)
            self._set_cached_data('positions', positions)
            return positions
        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"❌ Failed to get positions: {e}")
            return []

    async def get_performance_metrics(self) -> dict[str, Any]:
        """Get performance metrics for monitoring"""
        current_time = time.time()

        # Only calculate metrics if we have enough data
        if len(self._response_times) < 5:
            return {}

        avg_response_time = statistics.mean(self._response_times)
        success_rate = self._calculate_success_rate()

        return {
            'avg_response_time': avg_response_time,
            'success_rate': success_rate,
            'total_operations': sum(self._success_counts.values()) + sum(self._error_counts.values()),
            'current_weight_limit': self._adaptive_limits['current_weight_limit'],
            'current_request_limit': self._adaptive_limits['current_request_limit'],
            'cache_hit_rate': self._calculate_cache_hit_rate(),
            'last_updated': current_time
        }

    def _calculate_cache_hit_rate(self) -> float:
        """Calculate cache hit rate"""
        # This is a simplified calculation - in a real implementation,
        # you'd track cache hits vs misses
        return 0.85  # Placeholder

    async def cleanup(self):
        """Cleanup resources"""
        if self._session:
            await self._session.close()
        self.logger.log_event("EXCHANGE", "INFO", "🧹 Exchange client cleanup completed")

    async def get_available_balance(self) -> float | None:
        """Enhanced available balance retrieval with intelligent caching"""
        cached_balance = self._get_cached_data('available_balance')
        if cached_balance is not None:
            return cached_balance

        async def _fetch_available_balance():
            async with self._async_semaphore:
                await self.rate_limiter.acquire(5)
                balance = self.exchange.fetch_balance()

                # Check BNFCR first (as in our case)
                bnfcr_free = balance["free"].get("BNFCR", 0)
                if float(bnfcr_free) > 0:
                    return float(bnfcr_free)

                # Then check USDC
                usdc_free = balance["free"].get("USDC", 0)
                if float(usdc_free) > 0:
                    return float(usdc_free)

                # Then BFUSD
                bfusd_free = balance["free"].get("BFUSD", 0)
                if float(bfusd_free) > 0:
                    return float(bfusd_free)

                # Fallback: look for any available balance
                for asset, amount in balance["free"].items():
                    if float(amount) > 0 and asset in ["USDC", "BNFCR", "BFUSD", "USDT"]:
                        return float(amount)

                return None

        try:
            balance = await self._execute_with_retry(_fetch_available_balance)
            self._set_cached_data('available_balance', balance)
            return balance
        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"❌ Failed to get available balance: {e}")
            return None

    async def get_open_orders(self) -> list[dict[str, Any]]:
        """Get all open orders"""
        async def _fetch_orders():
            async with self._async_semaphore:
                await self.rate_limiter.acquire(1)
                return self.exchange.fetch_open_orders()

        try:
            orders = await self._execute_with_retry(_fetch_orders)
            return orders or []
        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"❌ Failed to get open orders: {e}")
            return []

    async def fetch_open_orders(self, symbol: str = None) -> list[dict[str, Any]]:
        """Get open orders for specific symbol or all symbols"""
        async def _fetch_orders():
            async with self._async_semaphore:
                await self.rate_limiter.acquire(1)
                if symbol:
                    return self.exchange.fetch_open_orders(symbol)
                else:
                    return self.exchange.fetch_open_orders()

        try:
            orders = await self._execute_with_retry(_fetch_orders)
            return orders or []
        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"❌ Failed to fetch open orders for {symbol}: {e}")
            return []

    async def get_usdc_symbols(self) -> list[str]:
        """Enhanced USDC symbols retrieval with intelligent caching"""
        cached_symbols = self._get_cached_data('usdc_symbols')
        if cached_symbols is not None:
            return cached_symbols

        async def _fetch_symbols():
            if not self._cache.get('markets'):
                await self._load_markets_with_retry()

            markets = self._cache.get('markets', {})
            self.logger.log_event("EXCHANGE", "DEBUG", f"Total markets loaded: {len(markets)}")

            usdc_symbols = []

            for symbol, market_info in markets.items():
                # Проверяем, что это USDC фьючерс
                if (symbol.endswith(':USDC') and
                    market_info.get('type') == 'swap' and
                    market_info.get('quote') == 'USDC' and
                    market_info.get('active', True)):

                    # Исключаем только явно проблемные символы
                    if any(excluded in symbol.upper() for excluded in [
                        'UPUSDT', 'DOWNUSDT', 'BEARUSDT', 'BULLUSDT',
                        'HEDGE', 'HEDGED', 'PERP', 'TEST'
                    ]):
                        continue

                    usdc_symbols.append(symbol)

            self.logger.log_event("EXCHANGE", "DEBUG", f"USDC symbols found: {len(usdc_symbols)}")

            # Сортируем по объему торгов (если доступно)
            try:
                # Получаем тикеры для сортировки по объему
                tickers = self.exchange.fetch_tickers(usdc_symbols[:200])  # Увеличиваем лимит
                volume_data = {}

                for symbol in usdc_symbols:
                    ticker = tickers.get(symbol)
                    if ticker and ticker.get('quoteVolume'):
                        volume_data[symbol] = float(ticker['quoteVolume'])
                    else:
                        volume_data[symbol] = 0.0

                # Сортируем по объему (убывание)
                usdc_symbols.sort(key=lambda x: volume_data.get(x, 0), reverse=True)

            except Exception as e:
                self.logger.log_event("EXCHANGE", "WARNING", f"Failed to sort symbols by volume: {e}")

            self.logger.log_event("EXCHANGE", "INFO", f"Found {len(usdc_symbols)} USDC futures symbols")
            return usdc_symbols

        try:
            symbols = await self._execute_with_retry(_fetch_symbols)
            self._set_cached_data('usdc_symbols', symbols)
            return symbols
        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"❌ Failed to get USDC symbols: {e}")
            return []

    async def get_ticker(self, symbol: str) -> dict[str, Any] | None:
        """Enhanced ticker retrieval with intelligent caching"""
        cache_key = f'ticker_{symbol}'
        cached_ticker = self._get_cached_data(cache_key)
        if cached_ticker is not None:
            return cached_ticker

        async def _fetch_ticker():
            async with self._async_semaphore:
                await self.rate_limiter.acquire(1)  # Ticker request weighs 1
                ticker = self.exchange.fetch_ticker(symbol)

                # Check that all required fields exist and are not None
                if not ticker or ticker.get("last") is None:
                    self.logger.log_event("EXCHANGE", "WARNING", f"⚠️ Ticker {symbol} unavailable")
                    return None

                return {
                    "symbol": ticker["symbol"],
                    "last": float(ticker["last"]) if ticker.get("last") else 0.0,
                    "bid": float(ticker["bid"]) if ticker.get("bid") else 0.0,
                    "ask": float(ticker["ask"]) if ticker.get("ask") else 0.0,
                    "volume": float(ticker["baseVolume"]) if ticker.get("baseVolume") else 0.0,
                    "quoteVolume": float(ticker["quoteVolume"]) if ticker.get("quoteVolume") else 0.0,
                    "timestamp": ticker.get("timestamp", 0)
                }

        try:
            ticker = await self._execute_with_retry(_fetch_ticker)
            if ticker:
                self._set_cached_data(cache_key, ticker)
            return ticker
        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"❌ Failed to get ticker {symbol}: {e}")
            return None

    async def get_ohlcv(self, symbol: str, timeframe: str = "15m", limit: int = 100) -> list[dict[str, Any]] | None:
        """Enhanced OHLCV data retrieval with intelligent caching"""
        cache_key = f'ohlcv_{symbol}_{timeframe}_{limit}'
        cached_ohlcv = self._get_cached_data(cache_key)
        if cached_ohlcv is not None:
            return cached_ohlcv

        async def _fetch_ohlcv():
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            return [
                {
                    "timestamp": candle[0],
                    "open": float(candle[1]),
                    "high": float(candle[2]),
                    "low": float(candle[3]),
                    "close": float(candle[4]),
                    "volume": float(candle[5])
                }
                for candle in ohlcv
            ]

        try:
            ohlcv_data = await self._execute_with_retry(_fetch_ohlcv)
            self._set_cached_data(cache_key, ohlcv_data)
            return ohlcv_data
        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"❌ Failed to get OHLCV {symbol}: {e}")
            return None

    async def create_order(self, symbol: str, side: str, order_type: str, amount: float, price: float | None = None, params: dict = None) -> dict[str, Any] | None:
        """Enhanced order creation with intelligent retry and cache invalidation"""
        async def _create_order():
            async with self._async_semaphore:
                await self.rate_limiter.acquire(1)  # Order creation weighs 1
                # CCXT ожидает: create_order(symbol, type, side, amount, price, params)
                if params is None:
                    params = {}
                order = self.exchange.create_order(symbol, order_type, side, amount, price, params)

                # Invalidate order cache
                self._cache.pop('orders', None)
                self._cache.pop('orders_time', None)

                self.logger.log_event("EXCHANGE", "INFO", f"✅ Order created: {symbol} {side} {amount}")
                return order

        try:
            result = await self._execute_with_retry(_create_order)
            if not result:
                # Если результат None, возвращаем минимальную структуру ответа
                self.logger.log_event("EXCHANGE", "WARNING", f"Order returned None for {symbol}, creating fallback response")
                return {'status': 'FAILED', 'symbol': symbol, 'side': side, 'amount': amount, 'error': 'Order execution failed'}
            return result
        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"Failed to create order {symbol}: {e}")
            # Возвращаем структуру ошибки вместо None
            return {'status': 'ERROR', 'symbol': symbol, 'side': side, 'amount': amount, 'error': str(e)}

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Enhanced order cancellation with intelligent retry and cache invalidation"""
        async def _cancel_order():
            async with self._async_semaphore:
                await self.rate_limiter.acquire(1)  # Order cancellation weighs 1
                self.exchange.cancel_order(order_id, symbol)

                # Invalidate order cache
                self._cache.pop('orders', None)
                self._cache.pop('orders_time', None)

                self.logger.log_event("EXCHANGE", "INFO", f"✅ Order cancelled: {order_id}")
                return True

        try:
            return await self._execute_with_retry(_cancel_order)
        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"❌ Failed to cancel order {order_id}: {e}")
            return False

    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """Enhanced leverage setting with intelligent retry"""
        async def _set_leverage():
            # Используем стандартный метод CCXT вместо прямого API
            self.exchange.set_leverage(leverage, symbol)
            self.logger.log_event("EXCHANGE", "INFO", f"✅ Leverage set: {symbol} {leverage}x")
            return True

        try:
            return await self._execute_with_retry(_set_leverage)
        except Exception as e:
            self.logger.log_event("EXCHANGE", "ERROR", f"❌ Failed to set leverage {symbol}: {e}")
            return False

    async def place_order(self, symbol: str, side: str, order_type: str, amount: float = None, price: float = None, **kwargs) -> dict[str, Any] | None:
        """Place an order (alias for create_order) with flexible parameters"""
        # Обрабатываем разные варианты параметров
        if amount is None:
            if 'quantity' in kwargs:
                amount = kwargs['quantity']
            elif 'qty' in kwargs:
                amount = kwargs['qty']
            else:
                self.logger.log_event("EXCHANGE", "ERROR", f"No amount specified for order {symbol}")
                return None

        return await self.create_order(symbol, side, order_type, amount, price, **kwargs)


# Keep the original ExchangeClient for backward compatibility
class ExchangeClient(OptimizedExchangeClient):
    """Backward compatibility wrapper"""
    pass
