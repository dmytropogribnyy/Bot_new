#!/usr/bin/env python3
"""
BinanceBot v2.1 - Main Entry Point
Simplified OptiFlow HFT Bot based on v1 logic and v2 infrastructure
"""

import asyncio
import json
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from core.config import TradingConfig
from core.exchange_client import OptimizedExchangeClient
from core.order_manager import OrderManager
from core.unified_logger import UnifiedLogger
from telegram.telegram_bot import TelegramBot


class SimplifiedTradingBot:
    """Simplified trading bot based on old architecture with async improvements"""

    def __init__(self):
        self.config = TradingConfig()
        self.logger = UnifiedLogger(self.config)
        self.exchange = OptimizedExchangeClient(self.config, self.logger)
        self.order_manager = OrderManager(self.config, self.exchange, self.logger)

        # Get Telegram credentials
        telegram_token, telegram_chat_id = self.config.get_telegram_credentials()
        # Initialize Telegram Bot
        self.telegram_bot = TelegramBot(telegram_token, telegram_chat_id, self.logger)

        self.running = False
        self.stop_event = asyncio.Event()

    async def initialize(self):
        """Initialize all components"""
        try:
            self.logger.log_event("MAIN", "INFO", "🚀 Starting BinanceBot v2.1")

            # Initialize components
            self.logger.log_event("MAIN", "DEBUG", "🔧 Initializing Exchange...")
            await self.exchange.initialize()
            self.logger.log_event("MAIN", "DEBUG", "✅ Exchange initialized")

            self.logger.log_event("MAIN", "DEBUG", "🔧 Initializing OrderManager...")
            await self.order_manager.initialize()
            self.logger.log_event("MAIN", "DEBUG", "✅ OrderManager initialized")

            # Initialize telegram bot
            self.logger.log_event("MAIN", "DEBUG", "🔧 Initializing TelegramBot...")
            if self.telegram_bot:
                try:
                    # Start Telegram Bot in background task
                    asyncio.create_task(self.telegram_bot.run())
                    self.logger.log_event("MAIN", "DEBUG", "✅ TelegramBot started in background")
                except Exception as e:
                    self.logger.log_event("MAIN", "WARNING", f"⚠️ Failed to start TelegramBot: {e}")
                    self.telegram_bot = None
            else:
                self.logger.log_event("MAIN", "WARNING", "⚠️ TelegramBot not configured")

            self.running = True
            self.logger.log_event("MAIN", "INFO", "✅ All components initialized")

        except Exception as e:
            self.logger.log_event("MAIN", "ERROR", f"❌ Initialization error: {e}")
            import traceback
            self.logger.log_event("MAIN", "ERROR", f"Traceback: {traceback.format_exc()}")
            raise

    async def shutdown(self):
        """Graceful shutdown"""
        self.logger.log_event("MAIN", "INFO", "🛑 Shutting down bot...")

        try:
            # Stop main loop
            self.running = False
            self.stop_event.set()

            # Shutdown order manager
            await self.order_manager.shutdown()

            # Close exchange connection
            await self.exchange.close()

            # Stop telegram bot
            if self.telegram_bot:
                await self.telegram_bot.stop()

            self.logger.log_event("MAIN", "INFO", "✅ Shutdown complete")

        except Exception as e:
            self.logger.log_event("MAIN", "ERROR", f"❌ Shutdown error: {e}")

    async def trading_loop(self):
        """Main trading loop"""
        try:
            self.logger.log_event("MAIN", "INFO", "🔄 Starting trading loop")

            while self.running and not self.stop_event.is_set():
                try:
                    # Health checks
                    if not await self.exchange.health_check():
                        self.logger.log_event("MAIN", "WARNING", "⚠️ Exchange health check failed")
                        await asyncio.sleep(5)
                        continue

                    # Monitor positions
                    await self.order_manager.monitor_positions()

                    # Check order executions
                    await self.order_manager.check_order_executions()

                    # Check timeouts
                    await self.order_manager.check_timeouts()

                    # Log runtime status
                    await self._log_runtime_status()

                    # Wait for next iteration
                    await asyncio.sleep(self.config.update_interval)

                except Exception as e:
                    self.logger.log_event("MAIN", "ERROR", f"❌ Trading loop error: {e}")
                    await asyncio.sleep(5)

        except Exception as e:
            self.logger.log_event("MAIN", "ERROR", f"❌ Trading loop failed: {e}")
            raise

    async def _log_runtime_status(self):
        """Log runtime status periodically"""
        try:
            positions = self.order_manager.get_active_positions()
            position_count = len(positions)

            # Calculate total PnL
            total_pnl = sum(pos.get('unrealized_pnl', 0) for pos in positions)

            # Get balance
            balance = await self.exchange.get_usdt_balance()

            status = {
                "positions": position_count,
                "total_pnl": round(total_pnl, 2),
                "balance": round(balance, 2),
                "uptime": time.time() - self.start_time
            }

            self.logger.log_runtime_status("RUNNING", status)

        except Exception as e:
            self.logger.log_event("MAIN", "ERROR", f"Failed to log runtime status: {e}")

    async def run(self):
        """Main run method"""
        try:
            self.start_time = time.time()

            # Initialize
            await self.initialize()

            # Log startup summary
            config_summary = self.config.get_summary()
            self.logger.log_event("MAIN", "INFO", "📊 Configuration summary", config_summary)

            # Start trading loop
            await self.trading_loop()

        except KeyboardInterrupt:
            self.logger.log_event("MAIN", "INFO", "🛑 Received interrupt signal")
        except Exception as e:
            self.logger.log_event("MAIN", "ERROR", f"❌ Runtime error: {e}")
            import traceback
            self.logger.log_event("MAIN", "ERROR", f"Traceback: {traceback.format_exc()}")
        finally:
            await self.shutdown()


async def main():
    """Main entry point"""
    bot = SimplifiedTradingBot()

    # Setup signal handlers
    def signal_handler(signum, frame):
        print(f"\n🛑 Received signal {signum}")
        asyncio.create_task(bot.shutdown())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        await bot.run()
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Check if running in dry run mode
    if len(sys.argv) > 1 and sys.argv[1] == "--dry-run":
        print("🧪 Running in DRY RUN mode")
        os.environ["DRY_RUN"] = "true"

    # Run the bot
    asyncio.run(main())
