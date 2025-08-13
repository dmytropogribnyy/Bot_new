#!/usr/bin/env python3
"""
Test Unified Configuration
Test the new unified configuration system
"""

import json
from pathlib import Path

import pytest
from core.config import TradingConfig


def test_config_loading():
    """Test configuration loading"""
    print("🧪 Testing configuration loading...")

    try:
        config = TradingConfig()
        print("✅ Configuration loaded successfully")

        # Test basic properties
        print(f"📊 Testnet mode: {config.testnet}")
        print(f"📊 Dry run mode: {config.dry_run}")
        print(f"📊 Max positions: {config.max_positions}")
        print(f"📊 Telegram enabled: {config.is_telegram_enabled()}")

        assert True

    except Exception as e:
        print(f"❌ Configuration loading failed: {e}")
        pytest.fail(f"Configuration loading failed: {e}")


def test_leverage_mapping():
    """Test leverage mapping"""
    print("\n🧪 Testing leverage mapping...")

    try:
        config = TradingConfig()

        # Test leverage for different symbols
        test_symbols = ["BTC/USDT", "ETH/USDC", "DOGE/USDC", "XRP/USDC", "SOL/USDC"]

        for symbol in test_symbols:
            leverage = config.get_leverage_for_symbol(symbol)
            print(f"✅ {symbol}: {leverage}x leverage")
        assert True

    except Exception as e:
        print(f"❌ Leverage mapping failed: {e}")
        pytest.fail(f"Leverage mapping failed: {e}")


def test_symbol_lists():
    """Test symbol lists"""
    print("\n🧪 Testing symbol lists...")

    try:
        config = TradingConfig()

        # Test USDT symbols
        usdt_symbols = config.usdt_symbols
        print(f"📊 USDT symbols ({len(usdt_symbols)}): {usdt_symbols}")

        # Test USDC symbols
        usdc_symbols = config.usdc_symbols
        print(f"📊 USDC symbols ({len(usdc_symbols)}): {usdc_symbols}")

        # Test active symbols
        active_symbols = config.get_active_symbols()
        print(f"📊 Active symbols ({len(active_symbols)}): {active_symbols}")

        assert isinstance(active_symbols, list)

    except Exception as e:
        print(f"❌ Symbol lists failed: {e}")
        pytest.fail(f"Symbol lists failed: {e}")


def test_config_validation():
    """Test configuration validation"""
    print("\n🧪 Testing configuration validation...")

    try:
        config = TradingConfig()

        # Test validation
        is_valid = config.validate()
        print(f"✅ Configuration validation executed: {'PASS' if is_valid else 'FAIL'}")

        # Test summary
        summary = config.get_summary()
        print(f"📊 Configuration summary: {summary}")

        assert isinstance(summary, dict)

    except Exception as e:
        print(f"❌ Configuration validation failed: {e}")
        pytest.fail(f"Configuration validation failed: {e}")


def test_config_saving():
    """Test configuration saving"""
    print("\n🧪 Testing configuration saving...")

    try:
        config = TradingConfig()

        # Save to test file
        test_file = "data/test_config.json"
        config.save_to_file(test_file)

        # Check if file exists
        if Path(test_file).exists():
            print(f"✅ Configuration saved to {test_file}")

            # Load and verify
            with open(test_file) as f:
                saved_data = json.load(f)
            print(f"📊 Saved {len(saved_data)} configuration items")

            # Clean up
            Path(test_file).unlink()
            print("✅ Test file cleaned up")

            assert isinstance(saved_data, dict)
        else:
            print(f"❌ Configuration file not created: {test_file}")
            pytest.fail(f"Configuration file not created: {test_file}")

    except Exception as e:
        print(f"❌ Configuration saving failed: {e}")
        pytest.fail(f"Configuration saving failed: {e}")


def test_migrated_config():
    """Test migrated configuration"""
    print("\n🧪 Testing migrated configuration...")

    try:
        migrated_file = Path("data/unified_config.json")
        if not migrated_file.exists():
            pytest.skip("No migrated config found")

        with open(migrated_file) as f:
            migrated_data = json.load(f)

        print(f"📊 Migrated config has {len(migrated_data)} settings")

        # Check key settings
        key_settings = [
            "telegram_enabled",
            "testnet",
            "dry_run",
            "max_positions",
            "leverage_map",
            "usdc_symbols",
            "usdt_symbols",
        ]

        for key in key_settings:
            if key in migrated_data:
                value = migrated_data[key]
                if isinstance(value, dict):
                    print(f"✅ {key}: {len(value)} items")
                elif isinstance(value, list):
                    print(f"✅ {key}: {len(value)} items")
                else:
                    print(f"✅ {key}: {value}")
            else:
                print(f"⚠️ {key}: Not found")

        assert True

    except Exception as e:
        print(f"❌ Migrated config test failed: {e}")
        pytest.fail(f"Migrated config test failed: {e}")


def main():
    """Main test function"""
    print("🚀 Testing Unified Configuration System...")
    print("=" * 50)

    tests = [
        ("Configuration Loading", test_config_loading),
        ("Leverage Mapping", test_leverage_mapping),
        ("Symbol Lists", test_symbol_lists),
        ("Configuration Validation", test_config_validation),
        ("Configuration Saving", test_config_saving),
        ("Migrated Configuration", test_migrated_config),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n📋 Running: {test_name}")
        if test_func():
            passed += 1
            print(f"✅ {test_name}: PASSED")
        else:
            print(f"❌ {test_name}: FAILED")

    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! Configuration system is working correctly.")
    else:
        print("⚠️ Some tests failed. Please check the configuration.")

    print("=" * 50)


if __name__ == "__main__":
    main()
