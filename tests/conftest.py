# tests/conftest.py
import sys
from pathlib import Path

# КРИТИЧНО: Сначала добавляем корень проекта в sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Теперь безопасно импортировать проект
import pytest
import pytest_asyncio

from core.config import TradingConfig
from core.exchange_client import OptimizedExchangeClient
from core.order_manager import OrderManager
from core.unified_logger import UnifiedLogger


@pytest.fixture
def symbol() -> str:
    """Дефолтный символ для тестов, где ожидается фикстура 'symbol'."""
    return "BTC/USDT:USDT"


@pytest_asyncio.fixture
async def exchange_client():
    """Создаёт exchange‑клиент и гарантированно закрывает его (без утечек сессий)."""
    config = TradingConfig()  # или TradingConfig.from_env() — если хочешь идти через маппинг .env
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
    """OrderManager, связанный с exchange_client, с реальным логгером."""
    config = exchange_client.config
    logger = UnifiedLogger(config)
    om = OrderManager(config, exchange_client, logger)
    yield om
