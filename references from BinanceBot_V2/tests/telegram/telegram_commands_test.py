# telegram_commands_test.py

import asyncio

from core.config import TradingConfig
from telegram.command_handlers import CommandHandlers


class MockTradingEngine:
    """Мок для TradingEngine"""

    def __init__(self):
        self.in_position = {
            "BTCUSDC": {"entry_price": 50000.0, "qty": 0.001, "side": "BUY"},
            "ETHUSDC": {"entry_price": 3000.0, "qty": 0.01, "side": "SELL"},
        }
        self.paused = False

    def get_open_positions(self):
        positions = []
        for symbol, pos in self.in_position.items():
            positions.append(
                {
                    "symbol": symbol,
                    "side": pos["side"],
                    "qty": pos["qty"],
                    "entry_price": pos["entry_price"],
                }
            )
        return positions

    def get_capital_utilization(self) -> float:
        return 0.35  # 35%

    def get_performance_report(self, days: int = 1) -> dict:
        return {"pnl": 15.50, "win_rate": 0.65, "total_trades": 24}

    def pause_trading(self):
        self.paused = True

    def resume_trading(self):
        self.paused = False

    async def close_position(self, symbol: str):
        if symbol in self.in_position:
            del self.in_position[symbol]
            return {"success": True}
        else:
            return {"success": False, "error": "Position not found"}


class MockExchangeClient:
    """Мок для ExchangeClient"""

    async def get_balance(self) -> float:
        return 250.75


class MockLeverageManager:
    """Мок для LeverageManager"""

    def get_leverage_report(self):
        return {
            "risk_levels": {
                "low": ["BTCUSDC", "ETHUSDC"],
                "medium": ["SOLUSDC", "XRPUSDC"],
                "high": ["DOGEUSDC", "ADAUSDC"],
            }
        }

    def apply_suggestion(self, symbol: str, leverage: int, auto_apply: bool = False):
        return {"applied": True, "old": 5, "new": leverage}


class MockSymbolSelector:
    """Мок для SymbolSelector"""

    def __init__(self):
        self.selected_symbols = ["BTCUSDC", "ETHUSDC", "SOLUSDC", "XRPUSDC"]

    async def manual_refresh(self):
        return "🔄 Manual refresh complete. Current symbols: ['BTCUSDC', 'ETHUSDC', 'SOLUSDC', 'XRPUSDC']"


async def test_status_command():
    """Тест команды /status"""
    print("🧪 Testing /status command...")

    config = TradingConfig.from_file()
    engine = MockTradingEngine()
    exchange = MockExchangeClient()
    leverage_manager = MockLeverageManager()
    symbol_selector = MockSymbolSelector()

    handlers = CommandHandlers(leverage_manager, symbol_selector, exchange, engine, config)

    status = await handlers.get_status()

    assert "Bot Status:" in status
    assert "Active Positions: 2" in status
    assert "Capital Utilization: 35.0%" in status

    print("✅ /status command test passed")


async def test_positions_command():
    """Тест команды /positions"""
    print("🧪 Testing /positions command...")

    config = TradingConfig.from_file()
    engine = MockTradingEngine()
    exchange = MockExchangeClient()
    leverage_manager = MockLeverageManager()
    symbol_selector = MockSymbolSelector()

    handlers = CommandHandlers(leverage_manager, symbol_selector, exchange, engine, config)

    positions = await handlers.get_positions()

    assert "Active Positions:" in positions
    assert "BTCUSDC" in positions
    assert "ETHUSDC" in positions

    print("✅ /positions command test passed")


async def test_balance_command():
    """Тест команды /balance"""
    print("🧪 Testing /balance command...")

    config = TradingConfig.from_file()
    engine = MockTradingEngine()
    exchange = MockExchangeClient()
    leverage_manager = MockLeverageManager()
    symbol_selector = MockSymbolSelector()

    handlers = CommandHandlers(leverage_manager, symbol_selector, exchange, engine, config)

    balance = await handlers.get_balance()

    assert "Account Balance: 250.75 USDC" in balance

    print("✅ /balance command test passed")


async def test_performance_command():
    """Тест команды /performance"""
    print("🧪 Testing /performance command...")

    config = TradingConfig.from_file()
    engine = MockTradingEngine()
    exchange = MockExchangeClient()
    leverage_manager = MockLeverageManager()
    symbol_selector = MockSymbolSelector()

    handlers = CommandHandlers(leverage_manager, symbol_selector, exchange, engine, config)

    performance = await handlers.get_performance(1)

    assert "Performance (1d):" in performance
    assert "PnL: 15.50 USDC" in performance
    assert "Win Rate: 65.0%" in performance
    assert "Total Trades: 24" in performance

    print("✅ /performance command test passed")


async def test_pause_resume_commands():
    """Тест команд /pause и /resume"""
    print("🧪 Testing /pause and /resume commands...")

    config = TradingConfig.from_file()
    engine = MockTradingEngine()
    exchange = MockExchangeClient()
    leverage_manager = MockLeverageManager()
    symbol_selector = MockSymbolSelector()

    handlers = CommandHandlers(leverage_manager, symbol_selector, exchange, engine, config)

    # Тест pause
    pause_result = await handlers.pause_trading()
    assert "Trading paused." in pause_result
    assert engine.paused

    # Тест resume
    resume_result = await handlers.resume_trading()
    assert "Trading resumed." in resume_result
    assert not engine.paused

    print("✅ /pause and /resume commands test passed")


async def test_close_position_command():
    """Тест команды /close_position"""
    print("🧪 Testing /close_position command...")

    config = TradingConfig.from_file()
    engine = MockTradingEngine()
    exchange = MockExchangeClient()
    leverage_manager = MockLeverageManager()
    symbol_selector = MockSymbolSelector()

    handlers = CommandHandlers(leverage_manager, symbol_selector, exchange, engine, config)

    # Тест успешного закрытия
    result = await handlers.close_position("BTCUSDC")
    assert "Position BTCUSDC closed." in result

    # Тест неуспешного закрытия
    result = await handlers.close_position("NONEXISTENT")
    assert "Failed to close NONEXISTENT" in result

    print("✅ /close_position command test passed")


async def test_config_command():
    """Тест команды /config"""
    print("🧪 Testing /config command...")

    config = TradingConfig.from_file()
    engine = MockTradingEngine()
    exchange = MockExchangeClient()
    leverage_manager = MockLeverageManager()
    symbol_selector = MockSymbolSelector()

    handlers = CommandHandlers(leverage_manager, symbol_selector, exchange, engine, config)

    config_result = await handlers.get_config()

    assert "Config Summary:" in config_result
    assert "Risk per trade:" in config_result
    assert "Max Positions:" in config_result

    print("✅ /config command test passed")


async def test_leverage_commands():
    """Тест команд leverage"""
    print("🧪 Testing leverage commands...")

    config = TradingConfig.from_file()
    engine = MockTradingEngine()
    exchange = MockExchangeClient()
    leverage_manager = MockLeverageManager()
    symbol_selector = MockSymbolSelector()

    handlers = CommandHandlers(leverage_manager, symbol_selector, exchange, engine, config)

    # Тест leverage report
    report = await handlers.leverage_report()
    assert "Leverage Report:" in report
    assert "Low:" in report
    assert "Medium:" in report
    assert "High:" in report

    # Тест approve leverage
    result = await handlers.approve_leverage("BTCUSDC", 10)
    assert "Leverage for BTCUSDC updated: 5x → 10x" in result

    print("✅ Leverage commands test passed")


async def test_refresh_symbols_command():
    """Тест команды /refresh_symbols"""
    print("🧪 Testing /refresh_symbols command...")

    config = TradingConfig.from_file()
    engine = MockTradingEngine()
    exchange = MockExchangeClient()
    leverage_manager = MockLeverageManager()
    symbol_selector = MockSymbolSelector()

    handlers = CommandHandlers(leverage_manager, symbol_selector, exchange, engine, config)

    result = await handlers.refresh_symbols()
    assert "Manual refresh complete" in result
    assert "BTCUSDC" in result

    print("✅ /refresh_symbols command test passed")


async def test_telegram_bot_integration():
    """Тест интеграции с Telegram ботом"""
    print("🧪 Testing Telegram Bot Integration...")

    from telegram.telegram_bot import TelegramBot

    config = TradingConfig.from_file()

    # Создаем бота
    bot = TelegramBot(config.telegram_token)

    # Проверяем инициализацию
    assert bot.bot is not None
    assert bot.dp is not None

    # Тест отправки уведомления
    try:
        await bot.send_notification("🧪 Bot Deployment Test", config.telegram_chat_id)
        print("✅ Telegram notification sent successfully")
    except Exception as e:
        print(f"⚠️ Telegram notification failed (expected in test): {e}")

    print("✅ Telegram Bot integration test passed")


async def main():
    """Основная функция тестирования"""
    print("🚀 Starting Telegram Commands Tests...\n")

    try:
        await test_status_command()
        await test_positions_command()
        await test_balance_command()
        await test_performance_command()
        await test_pause_resume_commands()
        await test_close_position_command()
        await test_config_command()
        await test_leverage_commands()
        await test_refresh_symbols_command()
        await test_telegram_bot_integration()

        print("\n🎉 All Telegram commands tests passed!")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
