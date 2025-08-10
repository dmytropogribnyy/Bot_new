#!/usr/bin/env python3
"""Stage D integration test - TP/SL configuration"""

import asyncio

from core.config import TradingConfig
from core.exchange_client import OptimizedExchangeClient
from core.unified_logger import UnifiedLogger


async def test_stage_d():
    """Test Stage D modifications"""

    # Test config has new fields
    config = TradingConfig()
    logger = UnifiedLogger(config)

    print("Stage D Configuration Test")
    print("=" * 40)
    print(f"Working Type: {getattr(config, 'working_type', 'NOT FOUND')}")
    print(f"TP Order Style: {getattr(config, 'tp_order_style', 'NOT FOUND')}")

    # Verify fields exist
    assert hasattr(config, "working_type"), "Missing working_type in config"
    assert hasattr(config, "tp_order_style"), "Missing tp_order_style in config"

    # Test client structure
    client = OptimizedExchangeClient(config, logger)
    assert hasattr(client, "create_stop_loss_order")
    assert hasattr(client, "create_take_profit_order")

    print("\n✅ Stage D structure test passed!")
    return True


if __name__ == "__main__":
    asyncio.run(test_stage_d())
