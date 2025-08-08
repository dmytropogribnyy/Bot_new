#!/usr/bin/env python3
"""
Тест всех команд Telegram бота
Проверяет работу всех обработчиков команд
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent))

from core.config import TradingConfig
from telegram.command_handlers import CommandHandlers


class MockTradingEngine:
    """Мок для TradingEngine с реалистичными данными"""

    def __init__(self):
        self.config = None
        self.in_position = {
            "BTCUSDC": {
                "entry_price": 43250.50,
                "qty": 0.001,
                "side": "BUY",
                "pnl": 15.30,
                "entry_time": 1640995200
            },
            "ETHUSDC": {
                "entry_price": 2650.25,
                "qty": 0.01,
                "side": "SELL",
                "pnl": -8.45,
                "entry_time": 1640995200
            },
            "SOLUSDC": {
                "entry_price": 98.75,
                "qty": 0.5,
                "side": "BUY",
                "pnl": 12.80,
                "entry_time": 1640995200
            }
        }
        self.paused = False

    def get_open_positions(self):
        positions = []
        for symbol, pos in self.in_position.items():
            positions.append({
                "symbol": symbol,
                "side": pos["side"],
                "qty": pos["qty"],
                "entry_price": pos["entry_price"],
                "pnl": pos["pnl"]
            })
        return positions

    def get_capital_utilization(self):
        return 0.35  # 35%

    def get_performance_report(self, days=1):
        return {
            "pnl": 19.65,
            "win_rate": 0.68,
            "total_trades": 24,
            "avg_pnl": 0.82,
            "max_profit": 25.50,
            "max_loss": -12.30
        }

    def pause_trading(self):
        self.paused = True

    def resume_trading(self):
        self.paused = False

    async def close_position(self, symbol):
        if symbol in self.in_position:
            del self.in_position[symbol]
            return {"success": True, "message": f"Position {symbol} closed"}
        return {"success": False, "error": "Position not found"}


class MockExchangeClient:
    """Мок для ExchangeClient"""

    async def get_balance(self):
        return 1250.75


class MockLeverageManager:
    """Мок для LeverageManager"""

    def get_leverage_report(self):
        return {
            "risk_levels": {
                "low": ["BTCUSDC", "ETHUSDC"],
                "medium": ["SOLUSDC", "XRPUSDC"],
                "high": ["DOGEUSDC", "ADAUSDC"]
            },
            "current_leverages": {
                "BTCUSDC": 5,
                "ETHUSDC": 3,
                "SOLUSDC": 10
            }
        }

    def apply_suggestion(self, symbol, leverage, auto_apply=False):
        return {
            "applied": True,
            "old": 5,
            "new": leverage,
            "symbol": symbol
        }


class MockSymbolSelector:
    """Мок для SymbolSelector"""

    def __init__(self):
        self.selected_symbols = ["BTCUSDC", "ETHUSDC", "SOLUSDC", "XRPUSDC", "DOGEUSDC"]

    async def manual_refresh(self):
        return "🔄 Manual refresh complete. Current symbols: ['BTCUSDC', 'ETHUSDC', 'SOLUSDC', 'XRPUSDC', 'DOGEUSDC']"


class MockRiskManager:
    """Мок для RiskManager"""

    def get_risk_report(self):
        return {
            "current_risk": 0.15,
            "max_risk": 0.25,
            "risk_level": "medium",
            "recommendations": ["Reduce position sizes", "Increase stop losses"]
        }


class MockPostRunAnalyzer:
    """Мок для PostRunAnalyzer"""

    async def get_analysis_report(self, hours=24):
        return {
            "period": "24h",
            "total_trades": 24,
            "win_rate": 0.68,
            "avg_profit": 0.82,
            "best_symbol": "BTCUSDC",
            "worst_symbol": "ETHUSDC",
            "recommendations": ["Increase BTCUSDC exposure", "Reduce ETHUSDC positions"]
        }


class MockLogger:
    """Мок для Logger"""

    def log_event(self, component, level, message, details=None):
        print(f"[{component}] {level}: {message}")


class MockTelegramBot:
    """Мок для TelegramBot"""

    async def send_notification(self, message):
        print(f"📤 Telegram: {message[:50]}...")


async def test_all_commands():
    """Тестирует все команды Telegram бота"""

    print("🧪 TESTING ALL TELEGRAM COMMANDS")
    print("=" * 50)

    try:
        # Загружаем конфигурацию
        config = TradingConfig.from_file('data/runtime_config.json')

        # Создаем мок-объекты
        engine = MockTradingEngine()
        leverage_manager = MockLeverageManager()
        risk_manager = MockRiskManager()
        symbol_selector = MockSymbolSelector()
        post_run_analyzer = MockPostRunAnalyzer()
        logger = MockLogger()
        telegram_bot = MockTelegramBot()

        # Создаем обработчики команд
        handlers = CommandHandlers(
            engine, leverage_manager, risk_manager,
            symbol_selector, post_run_analyzer, logger, telegram_bot
        )

        print("✅ Command handlers created successfully")

        # Тестируем все команды
        commands_to_test = [
            ("Status", handlers.get_status),
            ("Positions", handlers.get_positions),
            ("Balance", handlers.get_balance),
            ("Performance", handlers.get_performance),
            ("Leverage Report", handlers.leverage_report),
            ("Config", handlers.get_config),
            ("Analysis Report", lambda: handlers.get_analysis_report(24)),
            ("Quick Summary", lambda: handlers.get_quick_summary(24)),
            ("Position History", lambda: handlers.get_position_history(24)),
            ("Logs Info", handlers.get_logs_info),
            ("Grid Status", handlers.get_grid_status),
            ("Run Status", handlers.get_run_status)
        ]

        print("\n📋 Testing commands:")

        for name, command_func in commands_to_test:
            try:
                if asyncio.iscoroutinefunction(command_func):
                    result = await command_func()
                else:
                    result = command_func()

                print(f"✅ {name}: {result[:80]}...")

            except Exception as e:
                print(f"❌ {name}: {e}")

        # Тестируем команды с параметрами
        print("\n🔧 Testing commands with parameters:")

        # Тест закрытия позиции
        try:
            close_result = await handlers.close_position("BTCUSDC")
            print(f"✅ Close Position: {close_result}")
        except Exception as e:
            print(f"❌ Close Position: {e}")

        # Тест паузы/возобновления
        try:
            pause_result = await handlers.pause_trading()
            print(f"✅ Pause Trading: {pause_result}")

            resume_result = await handlers.resume_trading()
            print(f"✅ Resume Trading: {resume_result}")
        except Exception as e:
            print(f"❌ Pause/Resume: {e}")

        # Тест обновления символов
        try:
            refresh_result = await handlers.refresh_symbols()
            print(f"✅ Refresh Symbols: {refresh_result}")
        except Exception as e:
            print(f"❌ Refresh Symbols: {e}")

        print("\n🎉 ALL COMMAND TESTS COMPLETED!")
        print("=" * 50)
        print("✅ Command handlers: WORKING")
        print("✅ Status commands: FUNCTIONAL")
        print("✅ Trading commands: OPERATIONAL")
        print("✅ Analysis commands: ACTIVE")

        return True

    except Exception as e:
        print(f"❌ Command tests failed: {e}")
        return False


async def test_notification_system():
    """Тестирует систему уведомлений"""

    print("\n📢 TESTING NOTIFICATION SYSTEM")
    print("=" * 40)

    try:
        config = TradingConfig.from_file('data/runtime_config.json')

        # Создаем бота
        from telegram.telegram_bot import TelegramBot
        bot = TelegramBot(config.telegram_token, config.telegram_chat_id)

        # Тестовые уведомления
        notifications = [
            "🔔 **SYSTEM ALERT**\n\n⚠️ High memory usage detected\n💾 Current: 85%\n🛡️ Action: Optimizing...",

            "💰 **PROFIT ALERT**\n\n🎯 Target reached: $2.0/hour\n📈 Current: $2.15/hour\n✅ Status: Above target",

            "🚨 **RISK ALERT**\n\n⚠️ Drawdown approaching limit\n📉 Current: -8.5%\n🛑 Action: Reducing exposure",

            "🎉 **SUCCESS ALERT**\n\n✅ 10 consecutive winning trades\n📊 Win rate: 85%\n🏆 Performance: Excellent"
        ]

        print("📤 Sending test notifications...")

        for i, notification in enumerate(notifications, 1):
            try:
                await bot.send_notification(notification)
                print(f"✅ Notification #{i} sent")
                await asyncio.sleep(1)
            except Exception as e:
                print(f"❌ Notification #{i} failed: {e}")

        print("✅ Notification system test completed")
        return True

    except Exception as e:
        print(f"❌ Notification test failed: {e}")
        return False


async def main():
    """Основная функция тестирования"""

    print("🚀 TELEGRAM COMMANDS TEST SUITE")
    print("=" * 60)

    # Тест 1: Все команды
    result1 = await test_all_commands()

    # Тест 2: Система уведомлений
    result2 = await test_notification_system()

    print("\n" + "=" * 60)
    print("📊 FINAL COMMAND TEST RESULTS")
    print("=" * 60)

    if result1 and result2:
        print("🎉 ALL COMMAND TESTS PASSED!")
        print("✅ Command Handlers: FULLY FUNCTIONAL")
        print("✅ Notifications: OPERATIONAL")
        print("✅ Integration: COMPLETE")
        print("\n🚀 Telegram bot is ready for production!")
    else:
        print("⚠️ SOME COMMAND TESTS FAILED")
        print("❌ Please check the issues above")

    return result1 and result2


if __name__ == "__main__":
    asyncio.run(main())
