#!/usr/bin/env python3
"""
Тест команд STOP и SHUTDOWN для BinanceBot_V2
"""

import asyncio
from unittest.mock import Mock

from telegram.command_handlers import CommandHandlers


class MockTradingEngine:
    """Мок для TradingEngine с поддержкой pause/resume"""

    def __init__(self):
        self.in_position = {
            "BTCUSDC": {"entry_price": 50000.0, "qty": 0.001, "side": "BUY"},
            "ETHUSDC": {"entry_price": 3000.0, "qty": 0.01, "side": "SELL"},
        }
        self.paused = False
        self.running = True
        self.logger = Mock()

    def get_open_positions(self):
        positions = []
        for symbol, pos in self.in_position.items():
            positions.append({
                "symbol": symbol,
                "side": pos["side"],
                "qty": pos["qty"],
                "entry_price": pos["entry_price"],
            })
        return positions

    def pause_trading(self):
        self.paused = True
        self.logger.log_event("TRADING_ENGINE", "WARNING", "Trading paused")

    def resume_trading(self):
        self.paused = False
        self.logger.log_event("TRADING_ENGINE", "INFO", "Trading resumed")

    async def close_position(self, symbol: str):
        """Мок закрытия позиции"""
        if symbol in self.in_position:
            # Симулируем успешное закрытие
            del self.in_position[symbol]
            return {"success": True, "pnl": 25.50, "win": True}
        else:
            return {"success": False, "error": "Position not found"}


class MockLogger:
    """Мок для логгера"""

    def __init__(self):
        self.events = []

    def log_event(self, component, level, message, details=None):
        self.events.append({
            "component": component,
            "level": level,
            "message": message,
            "details": details
        })
        print(f"[{level}] {component}: {message}")


async def test_stop_command():
    """Тест команды /stop"""
    print("\n🔍 Тестирование команды /stop...")

    # Создаем моки
    engine = MockTradingEngine()
    engine.logger = MockLogger()

    handlers = CommandHandlers(
        leverage_manager=Mock(),
        symbol_selector=Mock(),
        exchange_client=Mock(),
        bot_engine=engine,
        config=Mock()
    )

    # Тест 1: Остановка без активных позиций
    print("\n📋 Тест 1: Остановка без активных позиций")
    engine.in_position = {}  # Нет позиций
    result = await handlers.stop_trading()
    print(f"Результат: {result}")
    assert "No active positions" in result
    assert engine.paused == True

    # Тест 2: Остановка с активными позициями (быстрое закрытие)
    print("\n📋 Тест 2: Остановка с активными позициями (быстрое закрытие)")
    engine.in_position = {"BTCUSDC": {"entry_price": 50000.0, "qty": 0.001, "side": "BUY"}}
    engine.paused = False

    # Мокаем быстрое закрытие позиций
    original_close = engine.close_position
    async def fast_close(symbol):
        await asyncio.sleep(0.1)  # Быстрое закрытие
        return await original_close(symbol)

    engine.close_position = fast_close

    result = await handlers.stop_trading()
    print(f"Результат: {result}")
    assert "successfully" in result or "still active" in result

    # Тест 3: Остановка с активными позициями (медленное закрытие)
    print("\n📋 Тест 3: Остановка с активными позициями (медленное закрытие)")
    engine.in_position = {"ETHUSDC": {"entry_price": 3000.0, "qty": 0.01, "side": "SELL"}}
    engine.paused = False

    # Мокаем медленное закрытие позиций
    async def slow_close(symbol):
        await asyncio.sleep(0.1)  # Имитируем задержку
        return {"success": False, "error": "Timeout"}  # Не закрывается

    engine.close_position = slow_close

    result = await handlers.stop_trading()
    print(f"Результат: {result}")
    assert "still active" in result or "Use /shutdown" in result


async def test_shutdown_command():
    """Тест команды /shutdown"""
    print("\n🔍 Тестирование команды /shutdown...")

    # Создаем моки
    engine = MockTradingEngine()
    engine.logger = MockLogger()

    handlers = CommandHandlers(
        leverage_manager=Mock(),
        symbol_selector=Mock(),
        exchange_client=Mock(),
        bot_engine=engine,
        config=Mock()
    )

    # Тест 1: Экстренная остановка без позиций
    print("\n📋 Тест 1: Экстренная остановка без позиций")
    engine.in_position = {}
    result = await handlers.shutdown_bot()
    print(f"Результат: {result}")
    assert "No active positions" in result
    assert engine.paused == True

    # Тест 2: Экстренная остановка с позициями (успешное закрытие)
    print("\n📋 Тест 2: Экстренная остановка с позициями (успешное закрытие)")
    engine.in_position = {
        "BTCUSDC": {"entry_price": 50000.0, "qty": 0.001, "side": "BUY"},
        "ETHUSDC": {"entry_price": 3000.0, "qty": 0.01, "side": "SELL"},
    }
    engine.paused = False

    result = await handlers.shutdown_bot()
    print(f"Результат: {result}")
    assert "Emergency shutdown executed" in result
    assert engine.paused == True

    # Тест 3: Экстренная остановка с ошибками закрытия
    print("\n📋 Тест 3: Экстренная остановка с ошибками закрытия")
    engine.in_position = {"BTCUSDC": {"entry_price": 50000.0, "qty": 0.001, "side": "BUY"}}
    engine.paused = False

    # Мокаем ошибку закрытия
    async def error_close(symbol):
        return {"success": False, "error": "Network error"}

    engine.close_position = error_close

    result = await handlers.shutdown_bot()
    print(f"Результат: {result}")
    assert "Emergency shutdown executed" in result
    assert "0/1" in result  # 0 успешно закрытых из 1 позиции


async def test_command_integration():
    """Тест интеграции команд"""
    print("\n🔍 Тестирование интеграции команд...")

    engine = MockTradingEngine()
    engine.logger = MockLogger()

    handlers = CommandHandlers(
        leverage_manager=Mock(),
        symbol_selector=Mock(),
        exchange_client=Mock(),
        bot_engine=engine,
        config=Mock()
    )

    # Тест последовательности команд
    print("\n📋 Тест последовательности: pause -> stop -> shutdown")

    # 1. Pause
    result1 = await handlers.pause_trading()
    print(f"Pause: {result1}")
    assert engine.paused == True

    # 2. Stop
    result2 = await handlers.stop_trading()
    print(f"Stop: {result2}")

    # 3. Shutdown
    result3 = await handlers.shutdown_bot()
    print(f"Shutdown: {result3}")

    # Проверяем логи
    print("\n📝 Логи событий:")
    for event in engine.logger.events:
        print(f"  [{event['level']}] {event['component']}: {event['message']}")


async def main():
    """Основная функция тестирования"""
    print("🚀 Тестирование команд STOP и SHUTDOWN")
    print("=" * 50)

    try:
        await test_stop_command()
        await test_shutdown_command()
        await test_command_integration()

        print("\n✅ Все тесты прошли успешно!")
        print("\n📋 Резюме работы команд:")
        print("  /stop - Graceful остановка с ожиданием закрытия позиций")
        print("  /shutdown - Экстренная остановка с принудительным закрытием")
        print("  Обе команды корректно логируют события и управляют состоянием")

    except Exception as e:
        print(f"\n❌ Ошибка в тестах: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
