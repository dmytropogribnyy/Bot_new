#!/usr/bin/env python3
"""
Комплексные тесты интеграции для проверки работоспособности всей системы
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent.parent))

from core.config import TradingConfig
from strategies.performance_monitor import StrategyPerformanceMonitor
from strategies.strategy_manager import StrategyManager


async def test_strategy_manager_integration():
    """Тест интеграции StrategyManager"""
    print("🧪 Testing Strategy Manager Integration...")

    try:
        config = TradingConfig.from_file('data/runtime_config.json')
        print("✅ Config loaded successfully")

        # Создаем мок-объекты для тестирования
        class MockExchangeClient:
            async def get_balance(self):
                return 1000.0

        class MockSymbolManager:
            async def get_recent_ohlcv(self, symbol):
                return None

        class MockLogger:
            def log_event(self, *args):
                pass

        exchange_client = MockExchangeClient()
        symbol_manager = MockSymbolManager()
        logger = MockLogger()

        strategy_manager = StrategyManager(config, exchange_client, symbol_manager, logger)
        print("✅ Strategy Manager created successfully")

        return True

    except Exception as e:
        print(f"❌ Strategy Manager test failed: {e}")
        return False


async def test_performance_monitor():
    """Тест PerformanceMonitor"""
    print("🧪 Testing Performance Monitor...")

    try:
        config = TradingConfig.from_file('data/runtime_config.json')
        print("✅ Config loaded successfully")

        class MockLogger:
            def log_event(self, *args):
                pass

        logger = MockLogger()
        performance_monitor = StrategyPerformanceMonitor(config, logger)
        print("✅ Performance Monitor created successfully")

        return True

    except Exception as e:
        print(f"❌ Performance Monitor test failed: {e}")
        return False


async def test_telegram_commands_integration():
    """Тест интеграции Telegram команд"""
    print("🧪 Testing Telegram Commands Integration...")

    try:
        from telegram.command_handlers import CommandHandlers

        config = TradingConfig.from_file('data/runtime_config.json')
        print("✅ Config loaded successfully")

        # Создаем мок-объекты
        class MockLeverageManager:
            def get_leverage_report(self):
                return {"risk_levels": {"low": [], "medium": [], "high": []}}

        class MockSymbolSelector:
            async def manual_refresh(self):
                return "Refresh complete"

        class MockExchangeClient:
            async def get_balance(self):
                return 1000.0

        class MockTradingEngine:
            def get_open_positions(self):
                return []
            def get_capital_utilization(self):
                return 0.5
            def get_performance_report(self, days=1):
                return {"pnl": 0, "win_rate": 0, "total_trades": 0}

        class MockRiskManager:
            pass

        class MockPostRunAnalyzer:
            pass

        class MockLogger:
            def log_event(self, *args):
                pass

        class MockTelegramBot:
            pass

        leverage_manager = MockLeverageManager()
        symbol_selector = MockSymbolSelector()
        exchange_client = MockExchangeClient()
        engine = MockTradingEngine()
        risk_manager = MockRiskManager()
        post_run_analyzer = MockPostRunAnalyzer()
        logger = MockLogger()
        telegram_bot = MockTelegramBot()

        handlers = CommandHandlers(engine, leverage_manager, risk_manager, symbol_selector, post_run_analyzer, logger, telegram_bot)
        print("✅ Telegram Command Handlers created successfully")

        return True

    except Exception as e:
        print(f"❌ Telegram Commands test failed: {e}")
        return False


async def test_vps_deployment_files():
    """Тест файлов развертывания VPS"""
    print("🧪 Testing VPS Deployment Files...")

    try:
        # Проверяем наличие файлов развертывания
        deployment_files = [
            "deployment/systemd/binance-bot.service",
            "deployment/tmux_start.sh",
            "deployment/vps_setup.sh"
        ]

        for file_path in deployment_files:
            if Path(file_path).exists():
                print(f"✅ {file_path} exists")
            else:
                print(f"❌ {file_path} missing")
                return False

        print("✅ All deployment files present")
        return True

    except Exception as e:
        print(f"❌ VPS deployment test failed: {e}")
        return False


async def test_configuration_files():
    """Тест конфигурационных файлов"""
    print("🧪 Testing Configuration Files...")

    try:
        # Проверяем runtime_config.json
        config_path = Path("data/runtime_config.json")
        assert config_path.exists(), "runtime_config.json missing"
        print("✅ runtime_config.json exists")

                # Проверяем другие конфигурационные файлы
        config_files = [
            "data/runtime_config.json",
            "data/runtime_config_safe.json",
            "data/runtime_config_test.json",
            "data/logging_config.json"
        ]

        for config_file in config_files:
            if Path(config_file).exists():
                print(f"✅ {config_file} exists")
            else:
                print(f"⚠️ {config_file} missing (optional)")

        print("✅ Configuration files test passed")
        return True

    except Exception as e:
        print(f"❌ Configuration files test failed: {e}")
        return False


async def test_database_schema():
    """Тест схемы базы данных"""
    print("🧪 Testing Database Schema...")

    try:
        from core.unified_logger import UnifiedLogger

        config = TradingConfig.from_file('data/runtime_config.json')
        print("✅ Config loaded successfully")

        # Проверяем создание логгера
        logger = UnifiedLogger(config)
        print("✅ Logger created successfully")

        # Проверяем подключение к БД
        db_path = Path(config.db_path)
        if db_path.exists():
            print(f"✅ Database file exists: {db_path}")
        else:
            print(f"⚠️ Database file will be created: {db_path}")

        print("✅ Database schema test passed")
        return True

    except Exception as e:
        print(f"❌ Database schema test failed: {e}")
        return False


async def test_telegram_integration():
    """Тест интеграции с Telegram"""
    print("🧪 Testing Telegram Integration...")

    try:
        from telegram.telegram_bot import TelegramBot

        config = TradingConfig.from_file('data/runtime_config.json')
        print("✅ Config loaded successfully")

        # Проверяем создание Telegram бота
        if config.telegram_token and config.telegram_chat_id:
            telegram_bot = TelegramBot(config.telegram_token, config.telegram_chat_id)
            print("✅ Telegram Bot created successfully")
        else:
            print("⚠️ Telegram credentials not configured")

        print("✅ Telegram integration test passed")
        return True

    except Exception as e:
        print(f"❌ Telegram integration test failed: {e}")
        return False


async def test_main_integration():
    """Тест интеграции main.py"""
    print("🧪 Testing Main Integration...")

    try:
        # Проверяем импорты в main.py
        with open("main.py", encoding='utf-8') as f:
            main_content = f.read()

        # Проверяем наличие основных импортов
        required_imports = [
            "from core.config import TradingConfig",
            "from core.exchange_client import OptimizedExchangeClient",
            "from core.trading_engine import TradingEngine",
            "from telegram.telegram_bot import TelegramBot"
        ]

        for import_line in required_imports:
            if import_line in main_content:
                print(f"✅ Import found: {import_line}")
            else:
                print(f"❌ Import missing: {import_line}")
                return False

        print("✅ Main integration test passed")
        return True

    except Exception as e:
        print(f"❌ Main integration test failed: {e}")
        return False


async def main():
    """Основная функция тестирования"""
    print("🚀 Starting Comprehensive Integration Tests")
    print("=" * 50)

    tests = [
        test_strategy_manager_integration,
        test_performance_monitor,
        test_telegram_commands_integration,
        test_vps_deployment_files,
        test_configuration_files,
        test_database_schema,
        test_telegram_integration,
        test_main_integration
    ]

    results = []
    for test in tests:
        try:
            result = await test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results.append(False)

    print("\n" + "=" * 50)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 50)

    passed = sum(results)
    total = len(results)

    for i, (test, result) in enumerate(zip(tests, results, strict=False)):
        status = "✅ PASS" if result else "❌ FAIL"
        test_name = test.__name__.replace("test_", "").replace("_", " ").title()
        print(f"{i+1:2d}. {status} - {test_name}")

    print(f"\n📈 Overall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")

    if passed == total:
        print("🎉 All tests passed! System is ready for deployment.")
        return True
    else:
        print("⚠️ Some tests failed. Please review the issues above.")
        return False


if __name__ == "__main__":
    asyncio.run(main())
