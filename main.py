#!/usr/bin/env python3
"""
BinanceBot v2.1 - Main Entry Point
Simplified OptiFlow HFT Bot based on v1 logic and v2 infrastructure
"""

import asyncio
import os
import signal
import sys
import time
from pathlib import Path

# Load .env early (before config-dependent imports)
try:
    from dotenv import load_dotenv

    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        print(f"Loaded .env from {env_path}")
    else:
        print(f"Warning: .env not found at {env_path}")
        example_path = Path(__file__).parent / ".env.example"
        if example_path.exists():
            import shutil

            shutil.copy(example_path, env_path)
            print("Created .env from .env.example")
            load_dotenv(dotenv_path=env_path)
except Exception:
    pass

from core.config import TradingConfig
from core.exchange_client import OptimizedExchangeClient
from core.order_manager import OrderManager
from core.trade_engine_v2 import TradeEngineV2
from core.unified_logger import UnifiedLogger
from telegram.telegram_bot import TelegramBot

# FIX для Windows - ДОЛЖНО БЫТЬ ПЕРЕД ВСЕМИ ИМПОРТАМИ!
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


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
        # Attach Telegram to logger for runtime alerts
        try:
            self.logger.attach_telegram(self.telegram_bot)
        except Exception:
            pass

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
        """Graceful shutdown with position and order cleanup"""
        self.logger.log_event("MAIN", "INFO", "🛑 Shutting down bot...")

        try:
            # Stop main loop first
            self.running = False
            self.stop_event.set()

            # Check and close all open positions before shutdown
            await self._emergency_close_positions()

            # Shutdown order manager (emergency mode to ensure cleanup)
            await self.order_manager.shutdown(emergency=True)

            # Close exchange connection
            await self.exchange.close()

            # Stop telegram bot
            if self.telegram_bot:
                await self.telegram_bot.stop()

            self.logger.log_event("MAIN", "INFO", "✅ Shutdown complete")

        except Exception as e:
            self.logger.log_event("MAIN", "ERROR", f"❌ Shutdown error: {e}")

    async def _emergency_close_positions(self):
        """Emergency position closing during shutdown"""
        try:
            self.logger.log_event("MAIN", "INFO", "🔍 Emergency position check...")

            # Direct API call to get positions with retry
            open_positions = []
            for attempt in range(3):
                try:
                    positions = await self.exchange.exchange.fetch_positions()
                    # Tolerate schema: use size or contracts, allow both long/short
                    open_positions = []
                    for p in positions:
                        try:
                            size_val = float(p.get("contracts", p.get("size", 0)))
                        except Exception:
                            size_val = 0.0
                        if size_val != 0:
                            # Also normalize a derived side if missing
                            if "side" not in p or not p.get("side"):
                                p["side"] = "long" if size_val > 0 else "short"
                            open_positions.append(p)
                    break
                except Exception as e:
                    self.logger.log_event("MAIN", "WARNING", f"Position fetch attempt {attempt + 1} failed: {e}")
                    if attempt < 2:
                        await asyncio.sleep(1)

            if not open_positions and attempt == 2:
                self.logger.log_event("MAIN", "ERROR", "Failed to fetch positions after 3 attempts")
                return

            if open_positions:
                self.logger.log_event(
                    "MAIN", "WARNING", f"⚠️ EMERGENCY: Found {len(open_positions)} open position(s). Closing NOW..."
                )

                for pos in open_positions:
                    symbol = pos["symbol"]
                    side = pos.get("side", "long")
                    try:
                        contracts = float(pos.get("contracts", pos.get("size", 0)))
                    except Exception:
                        contracts = 0.0
                    unrealized_pnl = pos.get("unrealizedPnl", 0)

                    self.logger.log_event(
                        "MAIN",
                        "WARNING",
                        f"🚨 EMERGENCY CLOSE: {symbol} {side} {contracts} contracts, PnL: ${unrealized_pnl:.2f}",
                    )

                    try:
                        # Cancel orders first
                        try:
                            open_orders = await self.exchange.exchange.fetch_open_orders(symbol)
                            for order in open_orders:
                                await self.exchange.exchange.cancel_order(order["id"], symbol)
                                self.logger.log_event("MAIN", "INFO", f"❌ Cancelled order {order['id']}")
                        except Exception:
                            pass

                        # Close position immediately
                        close_side = "sell" if side == "long" else "buy"
                        close_order = await self.exchange.exchange.create_order(
                            symbol=symbol, type="market", side=close_side, amount=contracts, params={"reduceOnly": True}
                        )

                        self.logger.log_event(
                            "MAIN", "INFO", f"✅ EMERGENCY CLOSE EXECUTED: {symbol}, Order: {close_order.get('id')}"
                        )

                    except Exception as e:
                        self.logger.log_event("MAIN", "ERROR", f"❌ EMERGENCY CLOSE FAILED for {symbol}: {e}")

                # Wait and verify
                await asyncio.sleep(3)

                try:
                    final_positions = await self.exchange.exchange.fetch_positions()
                    still_open = []
                    for p in final_positions:
                        try:
                            val = float(p.get("contracts", p.get("size", 0)))
                        except Exception:
                            val = 0.0
                        if val != 0:
                            still_open.append(p)

                    if still_open:
                        self.logger.log_event(
                            "MAIN",
                            "ERROR",
                            f"🚨 CRITICAL: {len(still_open)} position(s) STILL OPEN after emergency close!",
                        )
                        # Send urgent telegram
                        if self.telegram_bot:
                            await self.telegram_bot.send_message(
                                f"🚨 CRITICAL: {len(still_open)} positions still open after bot shutdown!\n"
                                f"Please close manually on Binance!"
                            )
                    else:
                        self.logger.log_event("MAIN", "INFO", "✅ All positions emergency closed successfully")
                except:
                    pass

            else:
                self.logger.log_event("MAIN", "INFO", "✅ No open positions found")

        except Exception as e:
            self.logger.log_event("MAIN", "ERROR", f"❌ Emergency close failed: {e}")

    async def trading_loop(self):
        """Main trading loop"""
        try:
            self.logger.log_event("MAIN", "INFO", "🔄 Starting trading loop")

            engine = TradeEngineV2(self.config, self.exchange, self.order_manager, self.logger)

            while self.running and not self.stop_event.is_set():
                try:
                    # Health checks
                    if not await self.exchange.health_check():
                        self.logger.log_event("MAIN", "WARNING", "⚠️ Exchange health check failed")
                        await asyncio.sleep(5)
                        continue

                    # Scan/evaluate/execute cycle
                    await engine.run_cycle()

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
            total_pnl = sum(pos.get("unrealized_pnl", 0) for pos in positions)

            # Get quote balance: USDT on testnet, USDC on prod
            if self.config.testnet:
                balance = await self.exchange.get_usdt_balance()
            else:
                balance = await self.exchange.get_usdc_balance()

            status = {
                "positions": position_count,
                "total_pnl": round(total_pnl, 2),
                "balance": round(balance, 2),
                "uptime": time.time() - self.start_time,
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
            self.logger.log_event("MAIN", "INFO", "🛑 Received interrupt signal (Ctrl+C)")
        except asyncio.CancelledError:
            self.logger.log_event("MAIN", "INFO", "🛑 Task cancelled - shutting down")
        except Exception as e:
            self.logger.log_event("MAIN", "ERROR", f"❌ Runtime error: {e}")
            import traceback

            self.logger.log_event("MAIN", "ERROR", f"Traceback: {traceback.format_exc()}")
        finally:
            await self.shutdown()


async def main():
    """Main entry point"""
    bot = SimplifiedTradingBot()

    # Simple signal handler that directly calls shutdown
    def signal_handler(signum, frame):
        print(f"\n🛑 Received signal {signum} (Ctrl+C)")
        print("⏳ Emergency shutdown - closing all positions...")

        # Force shutdown in separate task
        asyncio.create_task(emergency_shutdown(bot))

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        await bot.run()
    except KeyboardInterrupt:
        print("\n🛑 KeyboardInterrupt - Emergency shutdown")
        await emergency_shutdown(bot)
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        await emergency_shutdown(bot)
        sys.exit(1)


async def emergency_shutdown(bot):
    """Emergency shutdown with position closing"""
    try:
        print("🚨 EMERGENCY SHUTDOWN INITIATED")

        # Force stop the bot
        bot.running = False
        bot.stop_event.set()

        # Emergency close positions
        await bot._emergency_close_positions()

        # Shutdown components
        await bot.order_manager.shutdown(emergency=True)
        await bot.exchange.close()
        if bot.telegram_bot:
            await bot.telegram_bot.stop()

        print("✅ Emergency shutdown complete")

    except Exception as e:
        print(f"❌ Emergency shutdown error: {e}")
    finally:
        os._exit(0)  # Force exit


if __name__ == "__main__":
    # Fix for Windows - use SelectorEventLoop
    if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Check if running in dry run mode
    if len(sys.argv) > 1 and sys.argv[1] == "--dry-run":
        print("🧪 Running in DRY RUN mode")
        os.environ["DRY_RUN"] = "true"

    # Run the bot
    asyncio.run(main())
