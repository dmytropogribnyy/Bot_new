#!/usr/bin/env python3
"""
Test Telegram Bot
"""

import asyncio
from core.config import TradingConfig
from telegram.telegram_bot import TelegramBot

async def test_telegram():
    """Test Telegram bot functionality"""
    print("🔧 Testing Telegram bot...")
    
    try:
        # Load configuration
        config = TradingConfig()
        print(f"✅ Configuration loaded")
        print(f"   • Telegram token: {bool(config.telegram_token)}")
        print(f"   • Telegram chat_id: {bool(config.telegram_chat_id)}")
        
        if not config.telegram_token:
            print("❌ No Telegram token found!")
            return False
            
        # Create Telegram bot
        telegram_bot = TelegramBot(
            token=config.telegram_token,
            chat_id=config.telegram_chat_id
        )
        print("✅ Telegram bot created")
        
        # Test sending message
        if config.telegram_chat_id:
            print("🔄 Testing message sending...")
            await telegram_bot.send_notification("🤖 Test message from OptiFlow HFT Bot")
            print("✅ Test message sent successfully!")
        else:
            print("⚠️ No chat_id configured, skipping message test")
            
        return True
        
    except Exception as e:
        print(f"❌ Telegram test error: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_telegram()) 