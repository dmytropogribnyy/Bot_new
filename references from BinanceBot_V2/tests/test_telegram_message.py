#!/usr/bin/env python3
"""
Test Telegram Message Sending
"""

import asyncio
from core.config import TradingConfig
from telegram.telegram_bot import TelegramBot

async def test_telegram_message():
    """Test sending Telegram message"""
    print("🔧 Testing Telegram message sending...")
    
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
        
        # Test sending startup message
        startup_message = f"🤖 OptiFlow HFT Bot запущен!\n\n📊 Цель: $0.7/час\n⚡ Режим: {'TESTNET' if config.is_testnet_mode() else 'PRODUCTION'}"
        
        print("🔄 Sending startup message...")
        print(f"Message: {startup_message}")
        
        await telegram_bot.send_notification(startup_message)
        print("✅ Startup message sent successfully!")
        
        return True
        
    except Exception as e:
        print(f"❌ Telegram message test error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(test_telegram_message()) 