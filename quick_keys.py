#!/usr/bin/env python3
"""
Quick Key Management for BinanceBot v2.3
Simple commands to manage API keys and settings
"""

import sys

from simple_env_manager import SimpleEnvManager


def show_help():
    """Show help information"""
    print("🔑 Quick Key Management")
    print("=" * 30)
    print("Usage: python quick_keys.py [command]")
    print("\nCommands:")
    print("  status          - Show current .env status")
    print("  set-api         - Set Binance API keys")
    print("  set-telegram    - Set Telegram credentials")
    print("  template        - Create .env template")
    print("  help            - Show this help")
    print("\nExamples:")
    print("  python quick_keys.py status")
    print("  python quick_keys.py set-api")
    print("  python quick_keys.py set-telegram")


def set_api_keys():
    """Set Binance API keys interactively"""
    print("🔑 Setting Binance API Keys")
    print("=" * 30)

    api_key = input("Enter your Binance API Key: ").strip()
    api_secret = input("Enter your Binance API Secret: ").strip()

    if not api_key or not api_secret:
        print("❌ API key and secret are required!")
        return

    manager = SimpleEnvManager()
    manager.set_api_keys(api_key, api_secret)

    print("✅ API keys set successfully!")


def set_telegram_credentials():
    """Set Telegram credentials interactively"""
    print("📱 Setting Telegram Credentials")
    print("=" * 30)

    token = input("Enter your Telegram Bot Token: ").strip()
    chat_id = input("Enter your Telegram Chat ID: ").strip()

    if not token or not chat_id:
        print("❌ Token and Chat ID are required!")
        return

    manager = SimpleEnvManager()
    manager.set_telegram_credentials(token, chat_id)

    print("✅ Telegram credentials set successfully!")


def show_status():
    """Show current status"""
    manager = SimpleEnvManager()
    manager.show_env_status()


def create_template():
    """Create .env template"""
    manager = SimpleEnvManager()
    manager.create_env_template()


def main():
    """Main function"""
    if len(sys.argv) < 2:
        show_help()
        return

    command = sys.argv[1].lower()

    if command == "help":
        show_help()
    elif command == "status":
        show_status()
    elif command == "set-api":
        set_api_keys()
    elif command == "set-telegram":
        set_telegram_credentials()
    elif command == "template":
        create_template()
    else:
        print(f"❌ Unknown command: {command}")
        show_help()


if __name__ == "__main__":
    main()
