#!/usr/bin/env python3
"""
BinanceBot v2.3 - Main Entry Point
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

__version__ = "2.3.0"

from core.audit_logger import get_audit_logger
from core.config import TradingConfig
from core.exchange_client import OptimizedExchangeClient
from core.order_manager import OrderManager
from core.trade_engine_v2 import TradeEngineV2
from core.unified_logger import (
    UnifiedLogger,
    print_session_banner_end,
    print_session_banner_start,
)
from telegram.telegram_bot import TelegramBot
from tools.auto_monitor import AutoMonitor


class SimplifiedTradingBot:
    """Simplified trading bot based on old architecture with async improvements"""

    def __init__(self):
        self.config = TradingConfig()
        self.logger = UnifiedLogger(self.config)
        self.exchange = OptimizedExchangeClient(self.config, self.logger)
        self.order_manager = OrderManager(self.config, self.exchange, self.logger)
        # P-block: environment-scoped audit logger
        try:
            self.audit = get_audit_logger(testnet=self.config.testnet)
        except Exception:
            self.audit = None

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
        # Initialize auto monitor
        self.auto_monitor = None  # Will be initialized after OrderManager

    async def initialize(self):
        """Initialize all components"""
        try:
            # Versioned startup banner
            logger.info("Starting BinanceBot v%s", __version__)
            self.logger.log_event("MAIN", "INFO", f"🚀 Starting BinanceBot v{__version__}")

            # Initialize components
            self.logger.log_event("MAIN", "DEBUG", "🔧 Initializing Exchange...")
            await self.exchange.initialize()
            self.logger.log_event("MAIN", "DEBUG", "✅ Exchange initialized")

            # Fail-fast futures permissions check (Stage A4)
            # Fail-fast futures permissions check (Stage A4)
            try:
                await self.exchange.assert_futures_perms()
            except Exception:
                # Ensure resources are released on hard-fail
                try:
                    await self.exchange.close()
                except Exception:
                    pass
                raise
            else:
                # Duplicate success marker at MAIN level for visibility in logs
                self.logger.log_event("MAIN", "INFO", "[PERMS] Futures trading permissions OK")

            self.logger.log_event("MAIN", "DEBUG", "🔧 Initializing OrderManager...")
            await self.order_manager.initialize()
            self.logger.log_event("MAIN", "DEBUG", "✅ OrderManager initialized")

            # Initialize telegram bot (start later in run())
            self.logger.log_event("MAIN", "DEBUG", "🔧 Initializing TelegramBot...")
            if not self.telegram_bot:
                self.logger.log_event("MAIN", "WARNING", "⚠️ TelegramBot not configured")
            # Connect OrderManager to Telegram
            if self.telegram_bot:
                self.telegram_bot.set_order_manager(self.order_manager)
                self.logger.log_event("MAIN", "INFO", "Connected OrderManager to Telegram bot")

            # Initialize auto monitor with Telegram integration
            self.auto_monitor = AutoMonitor(telegram_bot=self.telegram_bot)
            self.logger.log_event("MAIN", "INFO", "Auto monitor initialized")

            # Start WebSocket streams with fallback
            if not self.config.dry_run and self.config.enable_websocket:
                try:
                    from core.ws_client import UserDataStreamManager

                    # URLs based on environment
                    if self.config.testnet:
                        # Testnet (USDⓈ-M): use binancefuture.com with /fapi paths
                        default_api = "https://testnet.binancefuture.com"
                        default_ws = "wss://stream.binancefuture.com"
                    else:
                        # Production: USDⓈ-M (USDT and USDC) use fapi/fstream
                        default_api = "https://fapi.binance.com"
                        default_ws = "wss://fstream.binance.com:9443"

                    api_base = getattr(self.exchange, "api_base", default_api)
                    ws_base = getattr(self.exchange, "ws_url", default_ws)

                    self.user_stream = UserDataStreamManager(
                        api_base=api_base,
                        ws_url=ws_base,
                        api_key=self.config.api_key,
                        on_event=lambda e: asyncio.create_task(self.order_manager.handle_ws_event(e)),
                        resolved_quote_coin=self.config.resolved_quote_coin,
                    )
                    await self.user_stream.start()
                    self.logger.log_event("MAIN", "INFO", "✅ WebSocket connected")
                except Exception as e:
                    self.logger.log_event("MAIN", "WARNING", f"⚠️ WebSocket failed: {e}, using REST polling")
                    self.config.enable_websocket = False
                    # Запускаем REST polling вместо WS
                    if not hasattr(self, "tasks"):
                        self.tasks = []
                    self.tasks.append(asyncio.create_task(self._rest_polling()))

            # Инициализируем tasks если нет
            if not hasattr(self, "tasks"):
                self.tasks = []

            # Запускаем синхронизацию независимо от WS
            self.tasks.append(asyncio.create_task(self._sync_loop()))

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

        # Generate post-run summary
        try:
            if self.auto_monitor and hasattr(self, "order_manager"):
                self.logger.log_event("MAIN", "INFO", "Generating post-run summary...")
                alerts, summary = await asyncio.wait_for(self.auto_monitor.run_once(self.order_manager), timeout=3.0)

                if alerts:
                    self.logger.log_event("MAIN", "WARNING", f"Post-run alerts: {len(alerts)} issues found")
                else:
                    self.logger.log_event("MAIN", "INFO", "Post-run check: All systems normal")
        except TimeoutError:
            self.logger.log_event("MAIN", "WARNING", "Post-run summary timed out")
        except Exception as e:
            self.logger.log_event("MAIN", "ERROR", f"Post-run summary failed: {e}")

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

            # Fetch open positions via exchange client with retry
            open_positions = []
            last_err = None
            for attempt in range(3):
                try:
                    positions = await self.exchange.get_all_positions()
                    open_positions = positions or []
                    break
                except Exception as e:
                    last_err = e
                    self.logger.log_event("MAIN", "WARNING", f"Position fetch attempt {attempt + 1} failed: {e}")
                    if attempt < 2:
                        await asyncio.sleep(1)

            if not open_positions and last_err is not None:
                self.logger.log_event("MAIN", "ERROR", "Failed to fetch positions after 3 attempts")
                return

            if open_positions:
                self.logger.log_event(
                    "MAIN", "WARNING", f"⚠️ EMERGENCY: Found {len(open_positions)} open position(s). Closing NOW..."
                )

                for pos in open_positions:
                    symbol = pos.get("symbol")
                    if not symbol:
                        continue
                    try:
                        contracts = float(pos.get("contracts", pos.get("size", 0)))
                    except Exception:
                        contracts = 0.0
                    if contracts <= 0:
                        continue
                    side_raw = str(pos.get("side", "long")).lower()
                    close_side = "sell" if side_raw in ("long", "buy") else "buy"
                    try:
                        amount = self.exchange.round_amount(symbol, abs(float(contracts)))
                    except Exception:
                        amount = abs(float(contracts))
                    unrealized_pnl = pos.get("unrealizedPnl", 0)

                    self.logger.log_event(
                        "MAIN",
                        "WARNING",
                        f"🚨 EMERGENCY CLOSE: {symbol} {side_raw} {contracts} contracts, PnL: ${float(unrealized_pnl):.2f}",
                    )

                    try:
                        # Cancel all orders first via client wrapper
                        try:
                            await self.exchange.cancel_all_orders(symbol)
                            self.logger.log_event("MAIN", "INFO", f"❌ Cancelled orders for {symbol}")
                        except Exception:
                            pass

                        # Market close the position using client wrapper
                        close_order = await self.exchange.create_order(
                            symbol=symbol,
                            order_type="market",
                            side=close_side,
                            amount=amount,
                            params={"reduceOnly": True},
                        )

                        self.logger.log_event(
                            "MAIN", "INFO", f"✅ EMERGENCY CLOSE EXECUTED: {symbol}, Order: {close_order.get('id')}"
                        )
                        # Record exit decision in audit (approx. PnL)
                        try:
                            if getattr(self, "audit", None):
                                self.audit.record_exit_decision(
                                    symbol=symbol,
                                    reason="EMERGENCY_CLOSE",
                                    pnl=float(unrealized_pnl) if isinstance(unrealized_pnl, int | float) else 0.0,
                                    exit_signals=None,
                                    metadata={"order_id": close_order.get("id"), "side": side_raw},
                                )
                        except Exception:
                            pass

                    except Exception as e:
                        self.logger.log_event("MAIN", "ERROR", f"❌ EMERGENCY CLOSE FAILED for {symbol}: {e}")

                # Verification loop with retries
                for attempt in range(3):
                    await asyncio.sleep(1)
                    try:
                        final_positions = await self.exchange.get_all_positions()
                    except Exception:
                        final_positions = []
                    open_count = 0
                    for p in final_positions or []:
                        try:
                            val = float(p.get("contracts", p.get("size", 0)))
                        except Exception:
                            val = 0.0
                        if val > 0.0001:
                            open_count += 1

                    if open_count == 0:
                        self.logger.log_event("SHUTDOWN", "INFO", "✅ All positions closed")
                        break
                    elif attempt < 2:
                        self.logger.log_event(
                            "SHUTDOWN", "WARNING", f"Attempt {attempt + 1}: Still {open_count} positions, retrying..."
                        )
                    else:
                        self.logger.log_event("SHUTDOWN", "ERROR", "Failed to close all positions after 3 attempts")

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

                    # Auto-profit check every 5 seconds
                    if self.config.auto_profit_enabled:
                        current_time = time.time()
                        if not hasattr(self, "_last_auto_profit_check"):
                            self._last_auto_profit_check = 0

                        if (current_time - self._last_auto_profit_check) >= 5.0:
                            try:
                                await self.order_manager.check_auto_profit()
                            except Exception as e:
                                self.logger.log_event("MAIN", "DEBUG", f"Auto-profit check error: {e}")
                            self._last_auto_profit_check = current_time

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

            # Get quote balance based on resolved quote coin
            balance = await self.exchange.get_quote_balance()

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
        try:
            print_session_banner_start(
                self.logger.logger,
                run_id=getattr(self, "run_id", "run"),
                mode=("TESTNET" if self.config.testnet else "PROD"),
            )
        except Exception:
            pass

        # Initialize components
        await self.initialize()

        # Log startup summary + explicit mode and quote coin
        config_summary = self.config.get_summary()
        self.logger.log_event("MAIN", "INFO", "📊 Configuration summary", config_summary)
        self.logger.log_event(
            "MAIN",
            "INFO",
            f"[CONFIG] Mode: {'TESTNET' if self.config.testnet else 'PRODUCTION'}",
        )
        self.logger.log_event("MAIN", "INFO", f"[CONFIG] Quote coin: {self.config.resolved_quote_coin}")

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

            # Cancel trade loop early to prevent new REST calls during shutdown
            try:
                trade_tasks = [t for t in list(self.tasks) if t and not t.done() and t.get_name() == "trade_loop"]
                for t in trade_tasks:
                    t.cancel()
                if trade_tasks:
                    try:
                        await asyncio.wait(trade_tasks, timeout=1.5)
                    except Exception:
                        pass
            except Exception:
                pass

            # Stop WebSocket streams FIRST to avoid leaking client sessions
            if hasattr(self, "user_stream"):
                try:
                    await self.user_stream.stop()
                    self.logger.log_event("MAIN", "INFO", "User data stream stopped")
                except Exception:
                    pass
            if hasattr(self, "market_stream"):
                try:
                    await self.market_stream.stop()
                    self.logger.log_event("MAIN", "INFO", "Market data stream stopped")
                except Exception:
                    pass

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
            try:
                elapsed = time.time() - self.start_time
                print_session_banner_end(
                    self.logger.logger, run_id=getattr(self, "run_id", "run"), status="OK", elapsed_sec=elapsed
                )
            except Exception:
                pass

    async def _rest_polling(self):
        """Fallback REST polling при отказе WebSocket"""
        while self.running:
            try:
                await self.order_manager.sync_with_exchange()
                await asyncio.sleep(5)
            except Exception as e:
                self.logger.log_event("REST_POLL", "ERROR", str(e))
                await asyncio.sleep(10)

    async def _sync_loop(self):
        """Регулярная синхронизация с биржей"""
        while self.running:
            await asyncio.sleep(30)
            try:
                await self.order_manager.sync_with_exchange()
            except Exception as e:
                self.logger.log_event("SYNC", "ERROR", str(e))


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
