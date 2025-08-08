"""
Base strategy class for all trading strategies
"""
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Optional, Tuple, Any
import pandas as pd

from core.config import TradingConfig
from core.unified_logger import UnifiedLogger


class BaseStrategy(ABC):
    """Base class for all trading strategies"""
    
    def __init__(self, config: TradingConfig, logger: UnifiedLogger):
        self.config = config
        self.logger = logger
        self.name = self.__class__.__name__
        
    @abstractmethod
    async def should_enter_trade(self, symbol: str, df: pd.DataFrame) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Determine if we should enter a trade for the given symbol
        
        Returns:
            Tuple of (direction, breakdown) where:
            - direction: "buy", "sell", or None
            - breakdown: Dict with signal analysis details
        """
        pass
    
    @abstractmethod
    async def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate technical indicators for the given dataframe
        
        Args:
            df: OHLCV dataframe
            
        Returns:
            DataFrame with added indicator columns
        """
        pass
    
    def validate_market_conditions(self, current: pd.Series) -> Tuple[bool, str]:
        """
        Validate market conditions for trading
        
        Args:
            current: Current market data series
            
        Returns:
            Tuple of (is_valid, reason)
        """
        # Default implementation - can be overridden
        return True, "ok"
    
    def get_signal_breakdown(self, current: pd.Series, prev: pd.Series) -> Dict[str, Any]:
        """
        Get detailed signal breakdown for analysis
        
        Args:
            current: Current market data
            prev: Previous market data
            
        Returns:
            Dict with signal components
        """
        # Default implementation - can be overridden
        return {}
    
    def log_strategy_event(self, event_type: str, data: Dict[str, Any]):
        """Log strategy-specific events"""
        self.logger.log_event("STRATEGY", "INFO", f"{self.name}: {event_type} - {data}") 