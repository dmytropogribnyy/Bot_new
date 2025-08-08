"""
Symbol Manager for handling symbol rotation and selection
"""
import asyncio
from typing import List, Dict, Optional
import pandas as pd

from core.config import TradingConfig
from core.unified_logger import UnifiedLogger
from core.exchange_client import OptimizedExchangeClient


class SymbolManager:
    """Manages symbol selection and rotation"""

    def __init__(self, config: TradingConfig, exchange: OptimizedExchangeClient, logger: UnifiedLogger):
        self.config = config
        self.exchange = exchange
        self.logger = logger

        # Default USDC perpetual symbols (top 5 by volume)
        self.default_symbols = [
            "BTC/USDC:USDC",
            "ETH/USDC:USDC",
            "SOL/USDC:USDC",
            "BNB/USDC:USDC",
            "ADA/USDC:USDC"
        ]

        # Symbol cache
        self.symbols_cache = []
        self.last_update = 0
        self.cache_duration = 300  # 5 minutes

        # Symbol rotation index
        self.current_symbol_index = 0

    async def get_available_symbols(self) -> List[str]:
        """Get list of available symbols for trading"""
        try:
            # Check if cache is still valid
            if self.symbols_cache and (asyncio.get_event_loop().time() - self.last_update) < self.cache_duration:
                return self.symbols_cache

            # Fetch symbols from exchange
            if self.exchange.is_initialized:
                markets = await self.exchange.fetch_markets()
                usdc_symbols = []

                for symbol, market in markets.items():
                    if (market.get('type') == 'swap' and
                        market.get('quote') == 'USDC' and
                        market.get('active', False)):
                        usdc_symbols.append(symbol)

                if usdc_symbols:
                    # Sort by volume if available, otherwise use default order
                    self.symbols_cache = usdc_symbols[:10]  # Top 10
                    self.last_update = asyncio.get_event_loop().time()
                    self.logger.log_event("SYMBOL", "INFO", f"Loaded {len(self.symbols_cache)} USDC symbols")
                    return self.symbols_cache

            # Fallback to default symbols
            self.logger.log_event("SYMBOL", "WARNING", "Using default symbol list")
            return self.default_symbols

        except Exception as e:
            self.logger.log_event("SYMBOL", "ERROR", f"Error fetching symbols: {e}")
            return self.default_symbols

    async def get_next_symbol(self) -> Optional[str]:
        """Get next symbol for trading (round-robin)"""
        try:
            symbols = await self.get_available_symbols()
            if not symbols:
                return None

            symbol = symbols[self.current_symbol_index]
            self.current_symbol_index = (self.current_symbol_index + 1) % len(symbols)

            return symbol

        except Exception as e:
            self.logger.log_event("SYMBOL", "ERROR", f"Error getting next symbol: {e}")
            return None

    async def get_symbols_with_volume_filter(self, min_volume_usdc: float = 10000) -> List[str]:
        """Get symbols filtered by minimum volume"""
        try:
            symbols = await self.get_available_symbols()
            filtered_symbols = []

            for symbol in symbols[:20]:  # Check top 20
                try:
                    ticker = await self.exchange.fetch_ticker(symbol)
                    volume_usdc = ticker.get('quoteVolume', 0)

                    if volume_usdc >= min_volume_usdc:
                        filtered_symbols.append(symbol)

                except Exception as e:
                    self.logger.log_event("SYMBOL", "DEBUG", f"Error checking volume for {symbol}: {e}")
                    continue

            if filtered_symbols:
                self.logger.log_event("SYMBOL", "INFO", f"Found {len(filtered_symbols)} symbols with volume >= {min_volume_usdc}")
                return filtered_symbols
            else:
                self.logger.log_event("SYMBOL", "WARNING", f"No symbols meet volume threshold, using all available")
                return symbols[:5]  # Return top 5

        except Exception as e:
            self.logger.log_event("SYMBOL", "ERROR", f"Error filtering symbols by volume: {e}")
            return self.default_symbols

    def reset_rotation(self):
        """Reset symbol rotation to start"""
        self.current_symbol_index = 0
        self.logger.log_event("SYMBOL", "INFO", "Symbol rotation reset")

    async def get_symbol_info(self, symbol: str) -> Dict:
        """Get detailed information about a symbol"""
        try:
            if not self.exchange.is_initialized:
                return {"error": "Exchange not initialized"}

            ticker = await self.exchange.fetch_ticker(symbol)
            return {
                "symbol": symbol,
                "last_price": ticker.get('last', 0),
                "volume_24h": ticker.get('quoteVolume', 0),
                "price_change_24h": ticker.get('percentage', 0),
                "high_24h": ticker.get('high', 0),
                "low_24h": ticker.get('low', 0),
            }

        except Exception as e:
            self.logger.log_event("SYMBOL", "ERROR", f"Error getting symbol info for {symbol}: {e}")
            return {"error": str(e)}
