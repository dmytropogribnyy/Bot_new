#!/usr/bin/env python3
"""
Быстрый тест команд STOP и SHUTDOWN
"""

import asyncio
from unittest.mock import Mock

from telegram.command_handlers import CommandHandlers


class QuickMockEngine:
    """Быстрый мок для тестирования"""

    def __init__(self):
        self.in_position = {
            "BTCUSDC": {"entry_price": 50000.0, "qty": 0.001, "side": "BUY"}
        }
        self.paused = False
        self.logger = Mock()

    def get_open_positions(self):
        return [
            {
                "symbol": symbol,
                "side": pos["side"],
                "qty": pos["qty"],
                "entry_price": pos["entry_price"],
            }
            for symbol, pos in self.in_position.items()
        ]

    def pause_trading(self):
        self.paused = True
        print("🛑 Trading paused")

    async def close_position(self, symbol: str):
        if symbol in self.in_position:
            del self.in_position[symbol]
            return {"success": True, "pnl": 25.50, "win": True}
        return {"success": False, "error": "Position not found"}


async def quick_test():
    """Быстрый тест команд"""
    print("🚀 Быстрый тест команд STOP и SHUTDOWN")

    # Создаем моки
    engine = QuickMockEngine()
    handlers = CommandHandlers(
        leverage_manager=Mock(),
        symbol_selector=Mock(),
        exchange_client=Mock(),
        bot_engine=engine,
        config=Mock()
    )

    print("\n📋 Начальное состояние:")
    print(f"  Позиции: {len(engine.get_open_positions())}")
    print(f"  Paused: {engine.paused}")

    # Тест STOP без позиций
    print("\n🔍 Тест /stop (без позиций):")
    engine.in_position = {}
    result = await handlers.stop_trading()
    print(f"  Результат: {result}")
    print(f"  Paused: {engine.paused}")

    # Тест SHUTDOWN с позициями
    print("\n🔍 Тест /shutdown (с позициями):")
    engine.in_position = {"ETHUSDC": {"entry_price": 3000.0, "qty": 0.01, "side": "SELL"}}
    engine.paused = False
    result = await handlers.shutdown_bot()
    print(f"  Результат: {result}")
    print(f"  Paused: {engine.paused}")
    print(f"  Позиции после: {len(engine.get_open_positions())}")

    print("\n✅ Быстрый тест завершен!")


if __name__ == "__main__":
    asyncio.run(quick_test())
