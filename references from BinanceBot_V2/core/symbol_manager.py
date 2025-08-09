#!/usr/bin/env python3
"""
Упрощенный Symbol Manager - основан на архитектуре старого бота
"""

import asyncio
import random
from typing import Any

from core.config import TradingConfig
from core.exchange_client import OptimizedExchangeClient
from core.unified_logger import UnifiedLogger


class SymbolManager:
    """Упрощенный менеджер символов на основе старого бота"""

    def __init__(self, config: TradingConfig, logger: UnifiedLogger):
        self.config = config
        self.logger = logger
        self.exchange = None
        self.active_symbols = []
        self.symbol_rotation_time = 0
        self.rotation_interval = 3600  # 1 час

    async def initialize(self):
        """Инициализация менеджера символов"""
        self.logger.log_event("SYMBOL_MANAGER", "INFO", "🚀 Symbol Manager инициализирован")

    def set_exchange(self, exchange: OptimizedExchangeClient):
        """Устанавливает ссылку на exchange client"""
        self.exchange = exchange

    async def get_active_symbols(self) -> list[str]:
        """Получает активные символы для торговли"""
        try:
            # Проверяем, нужно ли обновить список символов
            current_time = asyncio.get_event_loop().time()
            if (
                not self.active_symbols
                or current_time - self.symbol_rotation_time > self.rotation_interval
            ):
                await self._update_active_symbols()
                self.symbol_rotation_time = current_time

            return self.active_symbols

        except Exception as e:
            self.logger.log_event(
                "SYMBOL_MANAGER", "ERROR", f"Ошибка получения активных символов: {e}"
            )
            return []

    async def _update_active_symbols(self):
        """Обновляет список активных символов"""
        try:
            if not self.exchange:
                self.logger.log_event("SYMBOL_MANAGER", "ERROR", "Exchange client не установлен")
                return

            # Получаем все USDC символы
            all_symbols = await self.exchange.get_usdc_symbols()

            if not all_symbols:
                self.logger.log_event("SYMBOL_MANAGER", "WARNING", "Не удалось получить символы")
                return

            # Фильтруем символы по объему и ликвидности
            filtered_symbols = await self._filter_symbols_by_volume(all_symbols)

            # Выбираем случайные символы для ротации
            max_symbols = min(self.config.max_concurrent_positions * 2, len(filtered_symbols))
            selected_symbols = random.sample(
                filtered_symbols, min(max_symbols, len(filtered_symbols))
            )

            self.active_symbols = selected_symbols

            self.logger.log_event(
                "SYMBOL_MANAGER",
                "INFO",
                f"Обновлен список символов: {len(self.active_symbols)} активных из {len(all_symbols)} доступных",
            )

        except Exception as e:
            self.logger.log_event("SYMBOL_MANAGER", "ERROR", f"Ошибка обновления символов: {e}")

    async def _filter_symbols_by_volume(self, symbols: list[str]) -> list[str]:
        """Фильтрует символы по объему торгов"""
        try:
            filtered_symbols = []
            min_volume_usdc = getattr(
                self.config, "min_volume_24h_usdc", 5000000.0
            )  # Используем существующий атрибут

            for symbol in symbols[:50]:  # Проверяем только первые 50 для производительности
                try:
                    ticker = await self.exchange.get_ticker(symbol)
                    if ticker and ticker.get("quoteVolume", 0) > min_volume_usdc:
                        filtered_symbols.append(symbol)
                except Exception as e:
                    self.logger.log_event(
                        "SYMBOL_MANAGER", "DEBUG", f"Ошибка получения тикера {symbol}: {e}"
                    )
                    continue

            self.logger.log_event(
                "SYMBOL_MANAGER",
                "INFO",
                f"Отфильтровано {len(filtered_symbols)} символов из {len(symbols)} по объему",
            )

            return filtered_symbols

        except Exception as e:
            self.logger.log_event("SYMBOL_MANAGER", "ERROR", f"Ошибка фильтрации символов: {e}")
            return symbols[:20]  # Возвращаем первые 20 если фильтрация не удалась

    def get_symbol_info(self, symbol: str) -> dict[str, Any]:
        """Получает информацию о символе"""
        return {
            "symbol": symbol,
            "active": symbol in self.active_symbols,
            "rotation_time": self.symbol_rotation_time,
        }

    async def force_symbol_rotation(self):
        """Принудительно обновляет список символов"""
        self.symbol_rotation_time = 0
        await self._update_active_symbols()
        self.logger.log_event("SYMBOL_MANAGER", "INFO", "Принудительная ротация символов выполнена")
