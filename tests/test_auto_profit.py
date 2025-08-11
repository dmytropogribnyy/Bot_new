import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock
from core.config import TradingConfig
from core.order_manager import OrderManager


@pytest.mark.asyncio
async def test_auto_profit_bonus_threshold():
    """Test auto-profit triggers at bonus threshold"""
    config = TradingConfig()
    config.auto_profit_enabled = True
    config.auto_profit_threshold = 0.5
    config.bonus_profit_threshold = 2.0

    mock_exchange = MagicMock()
    mock_logger = MagicMock()

    manager = OrderManager(config, mock_exchange, mock_logger)

    # Mock position with 2.5% profit
    manager.active_positions = {"BTC/USDT:USDT": {"entry_price": 50000, "side": "buy", "size": 0.001, "timestamp": 0}}

    # Mock price with 2.5% gain
    mock_exchange.get_ticker = AsyncMock(return_value={"last": 51250})
    manager.close_position_market = AsyncMock(return_value=True)

    await manager.check_auto_profit()

    # Should trigger bonus profit close
    manager.close_position_market.assert_called_once_with("BTC/USDT:USDT")


@pytest.mark.asyncio
async def test_auto_profit_disabled():
    """Test auto-profit does nothing when disabled"""
    config = TradingConfig()
    config.auto_profit_enabled = False

    mock_exchange = MagicMock()
    mock_logger = MagicMock()

    manager = OrderManager(config, mock_exchange, mock_logger)
    manager.active_positions = {"BTC/USDT:USDT": {}}

    await manager.check_auto_profit()

    # Should not access exchange
    mock_exchange.get_ticker.assert_not_called()


def test_risk_reward_ratio():
    """Test R:R ratio is correct"""
    config = TradingConfig()
    ratio = config.take_profit_percent / config.stop_loss_percent
    assert ratio >= 1.5, f"R:R ratio {ratio:.2f} is less than 1.5"
    print(f"✅ R:R ratio: {ratio:.2f}:1")
