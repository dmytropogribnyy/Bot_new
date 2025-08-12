#!/usr/bin/env python3
"""
Standalone monitor runner
Run this in parallel with the main bot for continuous monitoring
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import TradingConfig
from core.unified_logger import UnifiedLogger
from telegram.telegram_bot import TelegramBot
from tools.auto_monitor import AutoMonitor


async def main():
    """Run standalone monitor"""
    print("🤖 Starting standalone monitor...")
    # Load config
    config = TradingConfig()
    logger = UnifiedLogger(config)
    # Initialize Telegram if configured
    telegram_bot = None
    if (
        getattr(config, "telegram_enabled", False)
        and getattr(config, "telegram_token", None)
        and getattr(config, "telegram_chat_id", None)
    ):
        telegram_bot = TelegramBot(config.telegram_token, config.telegram_chat_id, logger)
        print("✅ Telegram connected")
    else:
        print("⚠️ Telegram not configured - reports will be saved to file only")
    # Create monitor with 1-hour interval for active monitoring
    monitor = AutoMonitor(telegram_bot=telegram_bot, check_interval_hours=1)
    # Run continuous monitoring
    try:
        await monitor.run()
    except KeyboardInterrupt:
        print("\n🛑 Monitor stopped by user")
    except Exception as e:
        print(f"❌ Monitor error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
