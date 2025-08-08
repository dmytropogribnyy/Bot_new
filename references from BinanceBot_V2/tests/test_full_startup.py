#!/usr/bin/env python3
"""
Test Full Bot Startup
"""

import asyncio
from core.config import TradingConfig
from core.exchange_client import ExchangeClient
from core.unified_logger import UnifiedLogger
from core.order_manager import OrderManager
from telegram.telegram_bot import TelegramBot

async def test_full_startup():
    """Test full bot startup sequence"""
    print("🔧 Testing full bot startup...")
    
    try:
        # 1. Load configuration
        config = TradingConfig()
        print("✅ 1. Configuration loaded")
        
        # 2. Create logger
        logger = UnifiedLogger(config)
        print("✅ 2. Logger created")
        
        # 3. Test exchange client
        print("🔄 3. Testing exchange client...")
        exchange_client = ExchangeClient(config, logger)
        success = await exchange_client.initialize()
        if success:
            print("✅ 3. Exchange client initialized")
        else:
            print("❌ 3. Exchange client failed")
            return False
            
        # 4. Test order manager
        print("🔄 4. Testing order manager...")
        order_manager = OrderManager(config, logger, exchange_client)
        print("✅ 4. Order manager initialized")
        
        # 5. Test Telegram bot
        print("🔄 5. Testing Telegram bot...")
        telegram_bot = TelegramBot(
            token=config.telegram_token,
            chat_id=config.telegram_chat_id,
            logger=logger
        )
        print("✅ 5. Telegram bot created")
        
        # 6. Test sending startup message
        print("🔄 6. Testing startup message...")
        await telegram_bot.send_notification("🤖 OptiFlow HFT Bot запущен успешно!")
        print("✅ 6. Startup message sent")
        
        print("🎉 All components initialized successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Startup error: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_full_startup()) 