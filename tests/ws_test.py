#!/usr/bin/env python3
"""
Stage E: WebSocket test tool - demonstrates User Data Stream integration.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import aiohttp

from core.config import TradingConfig
from core.ws_client import UserDataStreamManager, get_listen_key, stream_user_data

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger(__name__)


class WebSocketTester:
    """Test WebSocket User Data Stream functionality."""

    def __init__(self):
        # Load configuration
        self.config = TradingConfig.from_env()

        # Set up API URLs based on testnet setting
        if self.config.testnet:
            self.api_base = "https://testnet.binancefuture.com"
            self.ws_url = "wss://stream.binancefuture.com"
        else:
            self.api_base = "https://fapi.binance.com"
            self.ws_url = "wss://fstream.binance.com"

        self.running = False
        self.stream_manager = None

    def handle_event(self, event: dict) -> None:
        """Handle incoming WebSocket events."""
        event_type = event.get("e", "unknown")

        logger.info(f"📥 Event received: {event_type}")

        if event_type == "ACCOUNT_UPDATE":
            # Account update event
            data = event.get("a", {})
            if "B" in data:  # Balances
                balances = data["B"]
                for balance in balances:
                    asset = balance.get("a")
                    wallet_balance = balance.get("wb")
                    cross_wallet = balance.get("cw")
                    logger.info(f"  💰 {asset}: wallet={wallet_balance}, cross={cross_wallet}")

            if "P" in data:  # Positions
                positions = data["P"]
                for pos in positions:
                    symbol = pos.get("s")
                    amount = pos.get("pa")
                    entry_price = pos.get("ep")
                    unrealized_pnl = pos.get("up")
                    if amount != "0":
                        logger.info(f"  📊 {symbol}: amt={amount}, entry={entry_price}, pnl={unrealized_pnl}")

        elif event_type == "ORDER_TRADE_UPDATE":
            # Order update event
            order = event.get("o", {})
            symbol = order.get("s", "")
            side = order.get("S", "")
            order_type = order.get("o", "")
            status = order.get("X", "")
            order_id = order.get("i", "")
            price = order.get("p", "")
            quantity = order.get("q", "")

            logger.info(f"  📝 Order Update: {symbol} {side} {order_type}")
            logger.info(f"     Status: {status}, ID: {order_id}")
            logger.info(f"     Price: {price}, Qty: {quantity}")

            # Check if it's a fill
            if status == "FILLED":
                logger.info("  ✅ Order FILLED!")

        elif event_type == "listenKeyExpired":
            logger.error("❌ Listen key expired! Need to reconnect.")

        else:
            logger.debug(f"  ℹ️ Full event data: {event}")

    async def test_basic_connection(self) -> None:
        """Test basic WebSocket connection and listen key retrieval."""
        logger.info("=" * 50)
        logger.info("Testing basic WebSocket connection...")
        logger.info(f"Testnet: {self.config.testnet}")
        logger.info(f"API Base: {self.api_base}")
        logger.info(f"WS URL: {self.ws_url}")

        headers = {"X-MBX-APIKEY": self.config.api_key}

        async with aiohttp.ClientSession() as session:
            try:
                # Get listen key
                listen_key = await get_listen_key(session, self.api_base, headers)
                logger.info(f"✅ Successfully got listen key: {listen_key[:8]}...")

                # Test streaming for 10 seconds
                logger.info("Starting 10-second stream test...")

                # Create a task for streaming
                stream_task = asyncio.create_task(
                    stream_user_data(
                        self.ws_url,
                        listen_key,
                        self.handle_event,
                        self.config.ws_reconnect_interval,
                        self.config.ws_heartbeat_interval,
                    )
                )

                # Wait for 10 seconds
                await asyncio.sleep(10)

                # Cancel the stream
                stream_task.cancel()

                logger.info("✅ Basic connection test completed!")

            except Exception as e:
                logger.error(f"❌ Connection test failed: {e}")
                raise

    async def test_managed_stream(self) -> None:
        """Test UserDataStreamManager with automatic keepalive."""
        logger.info("=" * 50)
        logger.info("Testing managed User Data Stream...")

        # Create manager
        self.stream_manager = UserDataStreamManager(
            api_base=self.api_base,
            ws_url=self.ws_url,
            api_key=self.config.api_key,
            on_event=self.handle_event,
            ws_reconnect_interval=self.config.ws_reconnect_interval,
            ws_heartbeat_interval=self.config.ws_heartbeat_interval,
        )

        try:
            # Start the stream
            await self.stream_manager.start()
            logger.info("✅ Managed stream started successfully!")

            # Keep running until interrupted
            self.running = True
            logger.info("Stream is running. Press Ctrl+C to stop...")

            while self.running:
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            logger.info("Received interrupt signal...")
        finally:
            # Stop the stream
            await self.stream_manager.stop()
            logger.info("✅ Managed stream stopped.")

    def handle_shutdown(self, signum, frame) -> None:
        """Handle shutdown signal."""
        logger.info("\n🛑 Shutting down...")
        self.running = False


async def main():
    """Main function to run WebSocket tests."""
    tester = WebSocketTester()

    # Check if API key is configured
    if not tester.config.api_key:
        logger.error("❌ No API key configured! Set BINANCE_API_KEY in .env file.")
        return

    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, tester.handle_shutdown)

    try:
        # Run basic connection test
        await tester.test_basic_connection()

        logger.info("\n" + "=" * 50)
        logger.info("Basic test passed! Starting continuous stream...")
        logger.info("This will show real-time account updates.")
        logger.info("Try placing orders on testnet to see events.")
        logger.info("=" * 50 + "\n")

        # Run managed stream (continuous)
        await tester.test_managed_stream()

    except Exception as e:
        logger.error(f"Test failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    # Fix for Windows
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Run the test
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
