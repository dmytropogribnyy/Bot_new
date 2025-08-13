import sys
from pathlib import Path

import pytest
import pytest_asyncio

from core.config import TradingConfig
from core.exchange_client import OptimizedExchangeClient
from core.order_manager import OrderManager
from core.unified_logger import UnifiedLogger

# Ensure project root on sys.path for core imports when running from tests dir
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def symbol() -> str:
    """Provide a default symbol for tests expecting a 'symbol' fixture."""
    return "BTC/USDT:USDT"


@pytest_asyncio.fixture
async def exchange_client():
    """Create an exchange client and ensure it is closed to avoid session leaks."""
    config = TradingConfig()
    logger = UnifiedLogger(config)
    client = OptimizedExchangeClient(config, logger)
    try:
        yield client
    finally:
        try:
            await client.close()
        except Exception:
            pass


@pytest_asyncio.fixture
async def order_manager(exchange_client):
    """Provide an OrderManager wired to the exchange client, with a real logger."""
    config = exchange_client.config
    logger = UnifiedLogger(config)
    om = OrderManager(config, exchange_client, logger)
    yield om
