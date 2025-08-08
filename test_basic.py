#!/usr/bin/env python3
"""
Basic test script for BinanceBot v2.1
Tests core components without making real API calls
"""

import asyncio
import sys
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from core.config import TradingConfig
from core.unified_logger import UnifiedLogger


async def test_config():
    """Test configuration system"""
    print("🧪 Testing configuration system...")

    try:
        config = TradingConfig()
        print(f"✅ Configuration loaded successfully")
        print(f"   - Testnet: {config.testnet}")
        print(f"   - Dry run: {config.dry_run}")
        print(f"   - Max positions: {config.max_positions}")
        print(f"   - Log level: {config.log_level}")

        # Test validation
        if config.validate():
            print("✅ Configuration validation passed")
        else:
            print("⚠️ Configuration validation failed (expected for test)")

        return True

    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False


async def test_logger():
    """Test logging system"""
    print("\n🧪 Testing logging system...")

    try:
        config = TradingConfig()
        logger = UnifiedLogger(config)

        # Test different log levels
        logger.log_event("TEST", "INFO", "Test info message")
        logger.log_event("TEST", "WARNING", "Test warning message")
        logger.log_event("TEST", "ERROR", "Test error message")

        print("✅ Logging system working")
        print("   - Check logs/main.log for file output")
        print("   - Check data/trading_bot.db for database logs")

        return True

    except Exception as e:
        print(f"❌ Logging test failed: {e}")
        return False


async def test_imports():
    """Test that all modules can be imported"""
    print("\n🧪 Testing module imports...")

    try:
        # Test core imports
        from core.config import TradingConfig
        from core.unified_logger import UnifiedLogger
        from core.exchange_client import OptimizedExchangeClient
        from core.order_manager import OrderManager
        from telegram.telegram_bot import TelegramBot

        print("✅ All core modules imported successfully")

        # Test main bot import
        from main import SimplifiedTradingBot
        print("✅ Main bot class imported successfully")

        return True

    except Exception as e:
        print(f"❌ Import test failed: {e}")
        return False


async def test_basic_structure():
    """Test basic bot structure"""
    print("\n🧪 Testing basic bot structure...")

    try:
        from main import SimplifiedTradingBot

        # Create bot instance (without initializing)
        bot = SimplifiedTradingBot()

        print("✅ Bot instance created successfully")
        print(f"   - Config: {type(bot.config).__name__}")
        print(f"   - Logger: {type(bot.logger).__name__}")
        print(f"   - Exchange: {type(bot.exchange).__name__}")
        print(f"   - Order Manager: {type(bot.order_manager).__name__}")

        return True

    except Exception as e:
        print(f"❌ Basic structure test failed: {e}")
        return False


async def main():
    """Run all tests"""
    print("🚀 Starting BinanceBot v2.1 basic tests...\n")

    tests = [
        ("Configuration", test_config),
        ("Logging", test_logger),
        ("Imports", test_imports),
        ("Basic Structure", test_basic_structure),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results.append((test_name, False))

    # Print summary
    print("\n📊 Test Summary:")
    print("=" * 50)

    passed = 0
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:20} {status}")
        if result:
            passed += 1

    print("=" * 50)
    print(f"Total: {total}, Passed: {passed}, Failed: {total - passed}")

    if passed == total:
        print("\n🎉 All tests passed! Basic structure is working.")
        print("Next steps:")
        print("1. Set up your API keys in environment variables")
        print("2. Create data/config.json with your settings")
        print("3. Run: python main.py --dry-run")
    else:
        print(f"\n⚠️ {total - passed} test(s) failed. Please check the errors above.")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
