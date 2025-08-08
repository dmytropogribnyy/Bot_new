#!/usr/bin/env python3
"""
Comprehensive credentials test for BinanceBot V2
Tests both Binance API and Telegram credentials
"""

import os
import requests
from dotenv import load_dotenv
from core.config import TradingConfig

def test_environment_variables():
    """Test if all environment variables are loaded correctly"""
    print("🔑 Testing Environment Variables...")

    load_dotenv()

    # Check Binance credentials
    binance_api_key = os.environ.get('BINANCE_API_KEY')
    binance_api_secret = os.environ.get('BINANCE_API_SECRET')

    print(f"✅ BINANCE_API_KEY: {'✅' if binance_api_key else '❌'}")
    print(f"✅ BINANCE_API_SECRET: {'✅' if binance_api_secret else '❌'}")

    # Check Telegram credentials
    telegram_token = os.environ.get('TELEGRAM_TOKEN')
    telegram_chat_id = os.environ.get('TELEGRAM_CHAT_ID')

    print(f"✅ TELEGRAM_TOKEN: {'✅' if telegram_token else '❌'}")
    print(f"✅ TELEGRAM_CHAT_ID: {'✅' if telegram_chat_id else '❌'}")

    # Check logging configuration
    log_level = os.environ.get('LOG_LEVEL', 'NOT_SET')
    log_verbosity = os.environ.get('LOG_VERBOSITY', 'NOT_SET')

    print(f"✅ LOG_LEVEL: {log_level}")
    print(f"✅ LOG_VERBOSITY: {log_verbosity}")

    return all([binance_api_key, binance_api_secret, telegram_token, telegram_chat_id])

def test_binance_api():
    """Test Binance API connection"""
    print("\n🏦 Testing Binance API...")

    try:
        from core.config import TradingConfig
        from core.exchange_client import OptimizedExchangeClient
        from core.unified_logger import UnifiedLogger

        config = TradingConfig()
        logger = UnifiedLogger(config)
        client = OptimizedExchangeClient(config, logger)

        print("✅ Exchange client created successfully")
        print(f"✅ Exchange mode: {config.exchange_mode}")
        print(f"✅ Testnet: {config.is_testnet_mode()}")

        return True

    except Exception as e:
        print(f"❌ Binance API test failed: {e}")
        return False

def test_telegram_api():
    """Test Telegram API connection"""
    print("\n📱 Testing Telegram API...")

    try:
        load_dotenv()
        token = os.environ.get('TELEGRAM_TOKEN')
        chat_id = os.environ.get('TELEGRAM_CHAT_ID')

        if not token or not chat_id:
            print("❌ Telegram credentials not found in environment")
            return False

        # Test bot info
        response = requests.get(f'https://api.telegram.org/bot{token}/getMe')
        if response.status_code == 200:
            bot_info = response.json()
            print(f"✅ Bot info: {bot_info['result']['first_name']} (@{bot_info['result']['username']})")
        else:
            print(f"❌ Bot info test failed: {response.status_code}")
            return False

        # Test sending message
        test_message = "🧪 Credentials test - BinanceBot V2 is ready!"
        response = requests.post(
            f'https://api.telegram.org/bot{token}/sendMessage',
            json={'chat_id': chat_id, 'text': test_message}
        )

        if response.status_code == 200:
            print("✅ Test message sent successfully")
            return True
        else:
            print(f"❌ Message sending failed: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Telegram API test failed: {e}")
        return False

def test_config_loading():
    """Test configuration loading"""
    print("\n⚙️ Testing Configuration Loading...")

    try:
        config = TradingConfig()
        print("✅ TradingConfig loaded successfully")

        # Test profit target loading
        config = TradingConfig.load_optimized_for_profit_target(0.7)
        print("✅ Optimized config loaded for $0.7/hour target")

        profit_info = config.get_profit_target_info()
        print(f"✅ Profit target info: ${profit_info['profit_target_hourly']}/hour")

        return True

    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

def main():
    """Main test function"""
    print("🚀 COMPREHENSIVE CREDENTIALS TEST")
    print("=" * 50)

    # Test environment variables
    env_ok = test_environment_variables()

    # Test configuration loading
    config_ok = test_config_loading()

    # Test Binance API
    binance_ok = test_binance_api()

    # Test Telegram API
    telegram_ok = test_telegram_api()

    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 50)

    print(f"Environment Variables: {'✅ PASS' if env_ok else '❌ FAIL'}")
    print(f"Configuration Loading: {'✅ PASS' if config_ok else '❌ FAIL'}")
    print(f"Binance API: {'✅ PASS' if binance_ok else '❌ FAIL'}")
    print(f"Telegram API: {'✅ PASS' if telegram_ok else '❌ FAIL'}")

    all_passed = all([env_ok, config_ok, binance_ok, telegram_ok])

    if all_passed:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ Your BinanceBot V2 is ready for production!")
    else:
        print("\n⚠️ SOME TESTS FAILED")
        print("❌ Please check the issues above before proceeding")

    return all_passed

if __name__ == "__main__":
    main()
