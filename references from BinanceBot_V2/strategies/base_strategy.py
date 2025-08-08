from abc import ABC, abstractmethod
from typing import Any


class BaseStrategy(ABC):
    """
    Абстрактный базовый класс для всех торговых стратегий.
    """

    def __init__(self, config, exchange_client, symbol_manager, logger):
        self.config = config
        self.exchange = exchange_client
        self.symbol_manager = symbol_manager
        self.logger = logger

    @abstractmethod
    async def analyze_market(self, symbol: str) -> dict[str, Any] | None:
        """
        Анализирует рынок для данного символа и возвращает сигнал входа.
        Возвращает словарь:
        {
            "side": "BUY" or "SELL",
            "entry_price": float,
            "confidence": float  # (0.0 - 1.0)
        }
        или None, если сигнала нет.
        """
        pass

    @abstractmethod
    async def should_exit(self, symbol: str, position_data: dict[str, Any]) -> bool:
        """
        Определяет, следует ли закрыть позицию.
        Возвращает True, если условия выхода достигнуты.
        """
        pass

    async def log_strategy_decision(self, symbol: str, decision: str, details: dict[str, Any]):
        """
        Логирование решения стратегии (например, сигнал входа/выхода).
        """
        message = f"[{symbol}] Strategy Decision: {decision} | {details}"
        self.logger.log_event("STRATEGY", "DEBUG", message)
