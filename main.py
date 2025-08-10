#!/usr/bin/env python3
"""
BinanceBot v2.1 - Main Entry Point
Simplified OptiFlow HFT Bot based on v1 logic and v2 infrastructure
"""

import asyncio
import logging
import os
import signal
import sys
import time
from pathlib import Path

# Minimal platform policy + logger at the very beginning
logger = logging.getLogger(__name__)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

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
        # Unified stop event; keep backward-compat alias
        self._stop = asyncio.Event()
        self.stop_event = self._stop
        # Track background tasks we own
        self.tasks: list[asyncio.Task] = []

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

            # Initialize telegram bot (start later in run())
            self.logger.log_event("MAIN", "DEBUG", "🔧 Initializing TelegramBot...")
            if not self.telegram_bot:
                self.logger.log_event("MAIN", "WARNING", "⚠️ TelegramBot not configured")

            self.running = True
            self.logger.log_event("MAIN", "INFO", "✅ All components initialized")

        except Exception as e:
            self.logger.log_event("MAIN", "ERROR", f"❌ Initialization error: {e}")
            import traceback

            self.logger.log_event("MAIN", "ERROR", f"Traceback: {traceback.format_exc()}")
            raise

    async def cleanup_with_timeout(self, timeout: float = 5.0):
        """Save state (if available) and close resources in the correct order with timeouts."""
        # Optional runtime state save
        try:
            save_fn = getattr(self, "save_runtime_state", None)
            if callable(save_fn):
                await asyncio.wait_for(save_fn(), timeout=2.0)
                logger.info("Runtime state saved")
                try:
                    self.logger.log_event("MAIN", "INFO", "Runtime state saved")
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"State save failed: {e}")
            try:
                self.logger.log_event("MAIN", "ERROR", f"State save failed: {e}")
            except Exception:
                pass

        closers: list[tuple[str, object, str]] = [
            (
                "Telegram polling",
                getattr(self.telegram_bot, "stop", None) if self.telegram_bot else None,
                "SHUTDOWN_TG_POLL",
            ),
            (
                "Telegram session",
                getattr(getattr(self.telegram_bot, "session", None), "close", None) if self.telegram_bot else None,
                "SHUTDOWN_TG_SESSION",
            ),
            ("Exchange", getattr(self.exchange, "close", None), "SHUTDOWN_EXCHANGE"),
            (
                "Exchange (raw)",
                getattr(getattr(self, "exchange", None), "exchange", None).close
                if getattr(self, "exchange", None) and getattr(self.exchange, "exchange", None)
                else None,
                "SHUTDOWN_EXCHANGE_RAW",
            ),
            ("WebSocket", getattr(getattr(self, "ws_client", None), "close", None), "SHUTDOWN_WS"),
        ]

        for name, closer, component in closers:
            if closer and callable(closer):
                try:
                    await asyncio.wait_for(closer(), timeout=timeout)
                    logger.info(f"Closed: {name}")
                    try:
                        self.logger.log_event(component, "INFO", f"Closed: {name}")
                    except Exception:
                        pass
                except TimeoutError:
                    logger.error(f"Timeout closing: {name}")
                    try:
                        self.logger.log_event(component, "ERROR", f"Timeout closing: {name}")
                    except Exception:
                        pass
                except Exception as e:
                    logger.error(f"Error closing {name}: {e}")
                    try:
                        self.logger.log_event(component, "ERROR", f"Error closing {name}: {e}")
                    except Exception:
                        pass

        # Best-effort: explicitly close ccxt aiohttp session if still open
        try:
            raw_ex = getattr(self.exchange, "exchange", None)
            sess = getattr(raw_ex, "session", None)
            if sess and hasattr(sess, "close"):
                await asyncio.wait_for(sess.close(), timeout=1.0)
                logger.info("Closed: CCXT session")
                try:
                    self.logger.log_event("SHUTDOWN_CCXT_SESSION", "INFO", "Closed: CCXT session")
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Error closing CCXT session: {e}")
            try:
                self.logger.log_event("SHUTDOWN_CCXT_SESSION", "ERROR", f"Error closing CCXT session: {e}")
            except Exception:
                pass

        # Flush std logging handlers
        for h in logging.root.handlers:
            if hasattr(h, "flush"):
                try:
                    h.flush()
                except Exception:
                    pass
        # Yield to event loop to finalize aiohttp internals
        try:
            await asyncio.sleep(0)
        except Exception:
            pass

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

            while self.running and not self._stop.is_set():
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
        """Main run method with graceful shutdown and signal handling."""
        self.start_time = time.time()

        # Initialize components
        await self.initialize()

        # Log startup summary
        config_summary = self.config.get_summary()
        self.logger.log_event("MAIN", "INFO", "📊 Configuration summary", config_summary)

        # Announce start to Telegram
        try:
            if self.telegram_bot:
                env_name = "TESTNET" if self.config.testnet else "PROD"
                await self.telegram_bot.send_message(f"🚀 Bot started ({env_name})")
        except Exception:
            pass

        # Start background tasks
        self.running = True
        self.tasks.append(asyncio.create_task(self.trading_loop(), name="trade_loop"))
        if self.telegram_bot:
            try:
                self.tasks.append(asyncio.create_task(self.telegram_bot.run(), name="telegram_loop"))
            except Exception as e:
                self.logger.log_event("MAIN", "WARNING", f"Failed to start Telegram loop: {e}")

        # Install signal handlers
        loop = asyncio.get_running_loop()
        # Track shutdown reason
        self.shutdown_reason: str | None = None
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:

                def _on_signal(s=sig):
                    try:
                        self.shutdown_reason = f"signal {getattr(s, 'name', s)}"
                        self._stop.set()
                    except Exception:
                        self._stop.set()

                loop.add_signal_handler(sig, _on_signal)
            except NotImplementedError:
                # Not available on some platforms (e.g., Windows)
                pass

        # Fallback synchronous signal handlers (works on Windows)
        try:

            def _sync_sig_handler(signum, frame):
                try:
                    self.shutdown_reason = f"signal {signum}"
                    loop.call_soon_threadsafe(self._stop.set)
                except Exception:
                    self._stop.set()

            signal.signal(signal.SIGINT, _sync_sig_handler)
            signal.signal(signal.SIGTERM, _sync_sig_handler)
        except Exception:
            pass

        # Windows fallback: watch for KeyboardInterrupt
        async def keyboard_interrupt_handler():
            try:
                while not self._stop.is_set():
                    await asyncio.sleep(0.1)
            except KeyboardInterrupt:
                self.shutdown_reason = "KeyboardInterrupt"
                self._stop.set()

        self.tasks.append(asyncio.create_task(keyboard_interrupt_handler(), name="kb_interrupt"))

        try:
            await self._stop.wait()
        except asyncio.CancelledError:
            # Swallow cancellation (e.g., Ctrl+C) and proceed to graceful cleanup
            pass
        finally:
            logger.info("Shutting down gracefully...")
            try:
                self.logger.log_event("SHUTDOWN", "INFO", "Shutting down gracefully...")
            except Exception:
                pass
            # Stop main loop and perform cleanup
            self.running = False
            self._stop.set()

            # Notify Telegram about shutdown reason (before tearing down Telegram)
            try:
                if self.telegram_bot:
                    reason = self.shutdown_reason or "stop signal"
                    await self.telegram_bot.send_message(f"🛑 Shutting down: {reason}")
            except Exception:
                pass

            # Best-effort emergency close positions before resource teardown
            try:
                await asyncio.wait_for(self._emergency_close_positions(), timeout=5.0)
            except Exception:
                pass

            await self.cleanup_with_timeout(timeout=5.0)

            # Cancel remaining tasks
            for t in list(self.tasks):
                if t and not t.done():
                    t.cancel()
            if self.tasks:
                try:
                    done, pending = await asyncio.wait(self.tasks, timeout=2.0)
                    for t in pending:
                        t.cancel()
                except Exception:
                    pass
            logger.info("Shutdown complete")
            try:
                self.logger.log_event("SHUTDOWN", "INFO", "Shutdown complete")
                # Bypass rate limit by using a separate component key for the final line
                self.logger.log_event("SHUTDOWN_DONE", "INFO", "Shutdown complete")
            except Exception:
                pass


async def main():
    """Main entry point"""
    bot = SimplifiedTradingBot()
    await bot.run()


async def emergency_shutdown(bot):
    # Deprecated; retained for compatibility if referenced elsewhere.
    await bot.run()


if __name__ == "__main__":
    # Check if running in dry run mode
    if len(sys.argv) > 1 and sys.argv[1] == "--dry-run":
        print("🧪 Running in DRY RUN mode")
        os.environ["DRY_RUN"] = "true"

    asyncio.run(main())
