#!/usr/bin/env python3
"""
Test script for strategy and symbol manager integration
"""

import asyncio

import numpy as np
import pandas as pd

from core.config import TradingConfig
from core.exchange_client import OptimizedExchangeClient
from core.strategy_manager import StrategyManager
from core.symbol_manager import SymbolManager
from core.unified_logger import UnifiedLogger


async def test_strategy_integration():
    """Test the strategy and symbol manager integration"""
    print("🧪 Testing Strategy Integration...")

    try:
        # Initialize components
        config = TradingConfig()
        logger = UnifiedLogger(config)

        # Create mock exchange client for testing
        exchange = OptimizedExchangeClient(config, logger)

        # Initialize symbol manager
        symbol_manager = SymbolManager(config, exchange, logger)

        # Initialize strategy manager
        strategy_manager = StrategyManager(config, exchange, symbol_manager, logger)

        print("✅ Components initialized successfully")

        # Test symbol manager
        print("\n📊 Testing Symbol Manager...")
        symbols = await symbol_manager.get_available_symbols()
        print(f"   Available symbols: {len(symbols)}")
        for i, symbol in enumerate(symbols[:3]):
            print(f"   {i + 1}. {symbol}")

        # Test strategy initialization
        print("\n🎯 Testing Strategy Initialization...")
        strategy = strategy_manager.get_active_strategy()
        if strategy:
            print(f"   Active strategy: {strategy.name}")
            print(f"   RSI oversold: {strategy.rsi_oversold}")
            print(f"   RSI overbought: {strategy.rsi_overbought}")
            print(f"   Volume threshold: {strategy.volume_threshold}")
        else:
            print("   ❌ No active strategy found")
            return

        # Test indicator calculation with mock data
        print("\n📈 Testing Indicator Calculation...")
        mock_data = create_mock_ohlcv_data()
        df_with_indicators = await strategy.calculate_indicators(mock_data)

        print(f"   Original data shape: {mock_data.shape}")
        print(f"   Data with indicators shape: {df_with_indicators.shape}")

        # Check if indicators were added
        indicator_columns = [
            "ema_fast",
            "ema_slow",
            "rsi",
            "macd",
            "macd_signal",
            "macd_histogram",
            "atr_percent",
            "volume_ratio",
        ]
        added_indicators = [col for col in indicator_columns if col in df_with_indicators.columns]
        print(f"   Added indicators: {len(added_indicators)}/{len(indicator_columns)}")
        for indicator in added_indicators:
            print(f"     - {indicator}")

        # Test signal generation
        print("\n🔍 Testing Signal Generation...")
        direction, breakdown = await strategy.should_enter_trade("BTC/USDC:USDC", df_with_indicators)

        if direction:
            print(f"   Signal generated: {direction}")
            print(f"   Breakdown keys: {list(breakdown.keys())}")
            print(f"   Entry price: {breakdown.get('entry_price', 'N/A')}")
            print(f"   MACD strength: {breakdown.get('macd_strength', 'N/A')}")
            print(f"   RSI strength: {breakdown.get('rsi_strength', 'N/A')}")
        else:
            print("   No signal generated")
            if "reason" in breakdown:
                print(f"   Reason: {breakdown['reason']}")

        # Test 1+1 logic
        print("\n✅ Testing 1+1 Logic...")
        if direction:
            passes = strategy.passes_1plus1(breakdown)
            print(f"   Passes 1+1: {passes}")
        else:
            print("   Skipping 1+1 test (no signal)")

        # Test strategy manager scanning
        print("\n🔍 Testing Strategy Manager Scanning...")
        opportunities = await strategy_manager.scan_for_opportunities()
        print(f"   Found opportunities: {len(opportunities)}")

        for symbol, direction, breakdown in opportunities[:2]:  # Show first 2
            print(f"     - {symbol}: {direction}")

        print("\n✅ Strategy integration test completed successfully!")

    except Exception as e:
        print(f"❌ Error in strategy integration test: {e}")
        import traceback

        traceback.print_exc()


def create_mock_ohlcv_data(periods: int = 100) -> pd.DataFrame:
    """Create mock OHLCV data for testing"""
    np.random.seed(42)  # For reproducible results

    # Generate realistic price data
    base_price = 50000
    returns = np.random.normal(0, 0.02, periods)  # 2% daily volatility
    prices = [base_price]

    for ret in returns[1:]:
        new_price = prices[-1] * (1 + ret)
        prices.append(new_price)

    # Create OHLCV data
    data = []
    for i in range(periods):
        price = prices[i]
        high = price * (1 + abs(np.random.normal(0, 0.01)))
        low = price * (1 - abs(np.random.normal(0, 0.01)))
        open_price = price * (1 + np.random.normal(0, 0.005))
        close = price
        volume = np.random.uniform(1000, 10000)

        data.append({"open": open_price, "high": high, "low": low, "close": close, "volume": volume})

    df = pd.DataFrame(data)
    df.index = pd.date_range(start="2024-01-01", periods=periods, freq="5min")

    return df


async def main():
    """Main test function"""
    print("🚀 Starting Strategy Integration Tests...")
    print("=" * 50)

    await test_strategy_integration()

    print("\n" + "=" * 50)
    print("🎉 Strategy integration tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
