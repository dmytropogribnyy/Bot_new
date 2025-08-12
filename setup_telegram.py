#!/usr/bin/env python3
"""
Setup Telegram Credentials
Helper script to configure Telegram bot credentials
"""

from pathlib import Path

from core.config import TradingConfig


def setup_telegram_credentials():
    """Interactive setup for Telegram credentials"""
    print("🔧 Telegram Bot Setup")
    print("=" * 50)

    print("\n📱 To get Telegram bot credentials:")
    print("1. Open Telegram and search for @BotFather")
    print("2. Send /newbot command")
    print("3. Follow instructions to create a bot")
    print("4. Copy the bot token")
    print("5. Send a message to your bot")
    print("6. Get your chat ID from: https://api.telegram.org/bot<TOKEN>/getUpdates")

    print("\n" + "=" * 50)

    # Get bot token
    bot_token = input("🤖 Enter your bot token: ").strip()
    if not bot_token:
        print("❌ Bot token is required")
        return False

    # Get chat ID
    chat_id = input("💬 Enter your chat ID: ").strip()
    if not chat_id:
        print("❌ Chat ID is required")
        return False

    # Validate format
    if not bot_token.count(":") == 1:
        print("❌ Invalid bot token format. Should be like: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz")
        return False

    if not chat_id.isdigit() and not chat_id.startswith("-"):
        print("❌ Invalid chat ID format. Should be a number like: 123456789 or -123456789")
        return False

    # Add to .env file
    env_file = Path(".env")

    # Read existing content
    if env_file.exists():
        with open(env_file, encoding="utf-8") as f:
            content = f.read()
    else:
        content = ""

    # Add Telegram credentials
    telegram_section = f"""

# ========== Telegram Bot Credentials ==========
TELEGRAM_TOKEN={bot_token}
TELEGRAM_CHAT_ID={chat_id}
"""

    # Check if Telegram section already exists
    if "TELEGRAM_TOKEN=" in content:
        print("⚠️  Telegram credentials already exist in .env file")
        replace = input("Replace existing credentials? (y/n): ").lower().strip()
        if replace == "y":
            # Remove existing Telegram section
            lines = content.split("\n")
            new_lines = []
            skip_telegram = False
            for line in lines:
                if line.startswith("TELEGRAM_TOKEN=") or line.startswith("TELEGRAM_CHAT_ID="):
                    skip_telegram = True
                    continue
                if skip_telegram and line.strip() == "":
                    skip_telegram = False
                    continue
                if skip_telegram and line.startswith("#"):
                    skip_telegram = False
                if not skip_telegram:
                    new_lines.append(line)
            content = "\n".join(new_lines)
        else:
            print("❌ Setup cancelled")
            return False

    # Add new credentials
    content += telegram_section

    # Write back to file
    with open(env_file, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\n✅ Telegram credentials added to {env_file}")
    print(f"🤖 Bot Token: {bot_token[:10]}...")
    print(f"💬 Chat ID: {chat_id}")

    # Test the credentials
    print("\n🧪 Testing credentials...")
    test_url = f"https://api.telegram.org/bot{bot_token}/getMe"
    print(f"Test URL: {test_url}")

    return True


def test_telegram_connection():
    """Test Telegram connection"""
    print("\n🧪 Testing Telegram Connection...")

    # Check if credentials are set
    cfg = TradingConfig.from_env()
    token, chat_id = cfg.get_telegram_credentials()

    if not token or not chat_id:
        print("❌ Telegram credentials not found in environment")
        return False

    print(f"✅ Token found: {token[:10]}...")
    print(f"✅ Chat ID found: {chat_id}")

    # Test with a simple message
    try:
        import requests

        test_message = "🤖 BinanceBot v2.3 - Connection Test"
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {"chat_id": chat_id, "text": test_message}

        response = requests.post(url, data=data, timeout=10)

        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                print("✅ Telegram connection successful!")
                print("📱 Check your Telegram for the test message")
                return True
            else:
                print(f"❌ Telegram API error: {result.get('description', 'Unknown error')}")
                return False
        else:
            print(f"❌ HTTP error: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False


def main():
    """Main setup function"""
    print("🚀 Telegram Bot Setup for BinanceBot v2.3")
    print("=" * 60)

    # Check if credentials already exist
    cfg = TradingConfig.from_env()
    token, chat_id = cfg.get_telegram_credentials()

    if token and chat_id:
        print("✅ Telegram credentials found!")
        print(f"🤖 Bot Token: {token[:10]}...")
        print(f"💬 Chat ID: {chat_id}")

        test = input("\n🧪 Test connection? (y/n): ").lower().strip()
        if test == "y":
            test_telegram_connection()
    else:
        print("⚠️  Telegram credentials not found")
        setup = input("\n🔧 Setup Telegram credentials? (y/n): ").lower().strip()
        if setup == "y":
            if setup_telegram_credentials():
                print("\n🎉 Setup completed!")
                test = input("🧪 Test connection now? (y/n): ").lower().strip()
                if test == "y":
                    test_telegram_connection()
            else:
                print("\n❌ Setup failed")
        else:
            print("\n❌ Setup cancelled")


if __name__ == "__main__":
    main()
