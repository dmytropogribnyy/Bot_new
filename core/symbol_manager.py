"""
Symbol Manager for handling symbol rotation and selection
"""

import asyncio

from core.config import TradingConfig
from core.exchange_client import OptimizedExchangeClient
from core.symbol_utils import ensure_perp_usdc_format, is_usdc_contract_market
from core.unified_logger import UnifiedLogger


class SymbolManager:
    """Manages symbol selection and rotation"""

    def __init__(self, config: TradingConfig, exchange: OptimizedExchangeClient, logger: UnifiedLogger):
        self.config = config
        self.exchange = exchange
        self.logger = logger

        # Default perpetual symbols for prod/testnet
        if config.testnet:
            self.default_symbols = [
                "BTC/USDT:USDT",
                "ETH/USDT:USDT",
                "BNB/USDT:USDT",
                "SOL/USDT:USDT",
                "ADA/USDT:USDT",
            ]
        else:
            self.default_symbols = [
                "BTC/USDC:USDC",
                "ETH/USDC:USDC",
                "SOL/USDC:USDC",
                "BNB/USDC:USDC",
                "ADA/USDC:USDC",
            ]

        # Symbol cache
        self.symbols_cache = []
        self.last_update = 0
        self.cache_duration = 300  # 5 minutes

        # Symbol rotation index
        self.current_symbol_index = 0

    async def get_available_symbols(self) -> list[str]:
        """Get list of available symbols for trading"""
        try:
            # Check if cache is still valid
            if self.symbols_cache and (asyncio.get_event_loop().time() - self.last_update) < self.cache_duration:
                return self.symbols_cache

            # Fetch symbols from exchange
            if self.exchange.is_initialized:
                markets = await self.exchange.get_markets()
                selected_symbols: list[str] = []

                for symbol, market in markets.items():
                    # Always select USDC-settled contract markets
                    if is_usdc_contract_market(market):
                        selected_symbols.append(ensure_perp_usdc_format(symbol))

                if selected_symbols:
                    # Keep a manageable top slice
                    self.symbols_cache = selected_symbols[:10]  # Top 10
                    self.last_update = asyncio.get_event_loop().time()
                    quote = "USDT" if self.config.testnet else "USDC"
                    self.logger.log_event("SYMBOL", "INFO", f"Loaded {len(self.symbols_cache)} {quote} symbols")
                    return self.symbols_cache

            # Fallback to default symbols
            self.logger.log_event("SYMBOL", "WARNING", "Using default symbol list")
            return self.default_symbols

        except Exception as e:
            self.logger.log_event("SYMBOL", "ERROR", f"Error fetching symbols: {e}")
            return self.default_symbols

    async def get_next_symbol(self) -> str | None:
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

    async def get_symbols_with_volume_filter(self, min_volume_usdc: float = 10000) -> list[str]:
        """Get symbols filtered by minimum volume"""
        try:
            symbols = await self.get_available_symbols()
            filtered_symbols = []

            for symbol in symbols[:20]:  # Check top 20
                try:
                    # Skip invalid/delisted symbols
                    if any(x in symbol for x in ["TUSD", "BUSD", "QTUM", "NEO", "IOTA", "ONT"]):
                        continue
                    ticker = await self.exchange.get_ticker(symbol)
                    if not ticker:
                        continue

                    # Tolerant volume extraction (prefer quote volume in USDC)
                    volume_usdc_val = ticker.get("quoteVolume") or (ticker.get("info", {}) or {}).get("quoteVolume")

                    # Fallback: baseVolume * last/close
                    if not volume_usdc_val:
                        base_vol = ticker.get("baseVolume") or (ticker.get("info", {}) or {}).get("baseVolume")
                        last_price = ticker.get("last") or ticker.get("close") or 0
                        try:
                            volume_usdc_val = float(base_vol) * float(last_price) if base_vol and last_price else 0
                        except Exception:
                            volume_usdc_val = 0

                    try:
                        volume_usdc = float(volume_usdc_val or 0)
                    except Exception:
                        volume_usdc = 0.0

                    if volume_usdc >= float(min_volume_usdc):
                        filtered_symbols.append(symbol)

                except Exception as e:
                    self.logger.log_event("SYMBOL", "DEBUG", f"Error checking volume for {symbol}: {e}")
                    continue

            if filtered_symbols:
                self.logger.log_event("SYMBOL", "INFO", "Symbols with sufficient volume found")
                return filtered_symbols
            else:
                self.logger.log_event("SYMBOL", "WARNING", "No symbols meet volume threshold, using all available")
                return symbols[:5]  # Return top 5

        except Exception as e:
            self.logger.log_event("SYMBOL", "ERROR", f"Error filtering symbols by volume: {e}")
            return self.default_symbols

    def reset_rotation(self):
        """Reset symbol rotation to start"""
        self.current_symbol_index = 0
        self.logger.log_event("SYMBOL", "INFO", "Symbol rotation reset")

    async def get_symbol_info(self, symbol: str) -> dict:
        """Get detailed information about a symbol"""
        try:
            if not self.exchange.is_initialized:
                return {"error": "Exchange not initialized"}

            ticker = await self.exchange.get_ticker(symbol)
            return {
                "symbol": symbol,
                "last_price": ticker.get("last", 0),
                "volume_24h": ticker.get("quoteVolume", 0),
                "price_change_24h": ticker.get("percentage", 0),
                "high_24h": ticker.get("high", 0),
                "low_24h": ticker.get("low", 0),
            }

        except Exception as e:
            self.logger.log_event("SYMBOL", "ERROR", f"Error getting symbol info for {symbol}: {e}")
            return {"error": str(e)}
