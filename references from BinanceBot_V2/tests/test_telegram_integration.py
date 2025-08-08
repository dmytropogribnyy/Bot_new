#!/usr/bin/env python3
"""
Comprehensive Telegram integration test for BinanceBot V2
Tests startup, runtime, and shutdown notifications
"""

import requests
import time
from datetime import datetime
from dotenv import load_dotenv
import os

def test_telegram_connection():
    """Test basic Telegram connection"""
    print("🔗 Testing Telegram connection...")

    load_dotenv()
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')

    if not token or not chat_id:
        print("❌ Telegram credentials not found")
        return False

    try:
        # Test bot info
        response = requests.get(f'https://api.telegram.org/bot{token}/getMe')
        if response.status_code == 200:
            bot_info = response.json()
            print(f"✅ Bot connected: {bot_info['result']['first_name']}")
            return True
        else:
            print(f"❌ Bot connection failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def test_startup_message():
    """Test startup message"""
    print("\n🚀 Testing startup message...")

    load_dotenv()
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')

    message = f"""
🚀 <b>BinanceBot V2 STARTED</b>

📊 <b>Configuration:</b>
• Target Profit: $0.7/hour
• Max Positions: 5
• Risk Level: HIGH
• Mode: PRODUCTION

⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message.strip(),
            "parse_mode": "HTML"
        }
        response = requests.post(url, json=data, timeout=10)

        if response.status_code == 200:
            print("✅ Startup message sent successfully")
            return True
        else:
            print(f"❌ Startup message failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Startup message error: {e}")
        return False

def test_runtime_status():
    """Test runtime status message"""
    print("\n📈 Testing runtime status...")

    load_dotenv()
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')

    message = f"""
📈 <b>Bot Status Update</b>

💰 <b>Performance:</b>
• Active Positions: 2
• Total PnL: $15.50
• Win Rate: 75.5%

⚙️ <b>System:</b>
• Uptime: Running
• Last Trade: BTCUSDT +$5.20

⏰ Update: {datetime.now().strftime('%H:%M:%S')}
    """

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message.strip(),
            "parse_mode": "HTML"
        }
        response = requests.post(url, json=data, timeout=10)

        if response.status_code == 200:
            print("✅ Runtime status sent successfully")
            return True
        else:
            print(f"❌ Runtime status failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Runtime status error: {e}")
        return False

def test_shutdown_message():
    """Test shutdown message"""
    print("\n🛑 Testing shutdown message...")

    load_dotenv()
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')

    message = f"""
🛑 <b>BinanceBot V2 STOPPED</b>

📊 <b>Final Statistics:</b>
• Total Trades: 12
• Total PnL: $45.30
• Win Rate: 83.3%
• Runtime: 3h 25m

⏰ Stopped: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message.strip(),
            "parse_mode": "HTML"
        }
        response = requests.post(url, json=data, timeout=10)

        if response.status_code == 200:
            print("✅ Shutdown message sent successfully")
            return True
        else:
            print(f"❌ Shutdown message failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Shutdown message error: {e}")
        return False

def test_error_message():
    """Test error notification"""
    print("\n❌ Testing error message...")

    load_dotenv()
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')

    message = f"""
❌ <b>Bot Error</b>

Error: Test error notification
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message.strip(),
            "parse_mode": "HTML"
        }
        response = requests.post(url, json=data, timeout=10)

        if response.status_code == 200:
            print("✅ Error message sent successfully")
            return True
        else:
            print(f"❌ Error message failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error message error: {e}")
        return False

def main():
    """Main test function"""
    print("🧪 TELEGRAM INTEGRATION TEST")
    print("=" * 50)

    # Test connection
    connection_ok = test_telegram_connection()

    if not connection_ok:
        print("\n❌ Telegram connection failed. Cannot proceed with tests.")
        return False

    # Test all message types
    startup_ok = test_startup_message()
    time.sleep(2)  # Wait between messages

    runtime_ok = test_runtime_status()
    time.sleep(2)

    shutdown_ok = test_shutdown_message()
    time.sleep(2)

    error_ok = test_error_message()

    # Summary
    print("\n" + "=" * 50)
    print("📊 TELEGRAM TEST RESULTS")
    print("=" * 50)

    print(f"Connection: {'✅ PASS' if connection_ok else '❌ FAIL'}")
    print(f"Startup Message: {'✅ PASS' if startup_ok else '❌ FAIL'}")
    print(f"Runtime Status: {'✅ PASS' if runtime_ok else '❌ FAIL'}")
    print(f"Shutdown Message: {'✅ PASS' if shutdown_ok else '❌ FAIL'}")
    print(f"Error Message: {'✅ PASS' if error_ok else '❌ FAIL'}")

    all_passed = all([connection_ok, startup_ok, runtime_ok, shutdown_ok, error_ok])

    if all_passed:
        print("\n🎉 ALL TELEGRAM TESTS PASSED!")
        print("✅ Telegram integration is working perfectly!")
    else:
        print("\n⚠️ SOME TELEGRAM TESTS FAILED")
        print("❌ Please check the issues above")

    return all_passed

if __name__ == "__main__":
    main()
