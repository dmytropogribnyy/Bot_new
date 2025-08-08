#!/usr/bin/env python3
"""
Test script for strategy simulation without real exchange connection
"""
import asyncio
import sys
import platform

# Fix for Windows event loop
if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from core.config import TradingConfig
from core.unified_logger import UnifiedLogger
from strategies.scalping_v1 import ScalpingV1


async def test_strategy_simulation():
    """Test the strategy with full simulation"""
    print("🧪 Testing Strategy Simulation...")

    try:
        # Initialize components
        config = TradingConfig()
        config.dry_run = True
        config.testnet = True

        # Adjust strategy parameters for testing
        config.volume_threshold = 1.5     # Lower volume threshold (1.5 instead of 1.6)
        config.signal_threshold = 0.3     # Lower signal threshold

        logger = UnifiedLogger(config)
        logger.log_event("TEST", "INFO", "Starting strategy simulation test")

        # Initialize strategy directly
        strategy = ScalpingV1(config, logger)

        print("✅ Strategy initialized successfully")

        # Test 1: Create different types of mock data
        print("\n📈 Creating different market scenarios...")

        # Scenario 1: Bullish trend
        bullish_data = create_bullish_mock_data()
        print(f"   Bullish scenario: {bullish_data.shape}")

        # Scenario 2: Bearish trend
        bearish_data = create_bearish_mock_data()
        print(f"   Bearish scenario: {bearish_data.shape}")

        # Scenario 3: Sideways market
        sideways_data = create_sideways_mock_data()
        print(f"   Sideways scenario: {sideways_data.shape}")

        # Test 2: Test strategy with different scenarios
        print("\n🔍 Testing Strategy with Different Scenarios...")

        scenarios = [
            ("Bullish", bullish_data),
            ("Bearish", bearish_data),
            ("Sideways", sideways_data)
        ]

        for scenario_name, data in scenarios:
            print(f"\n   Testing {scenario_name} scenario...")

            # Calculate indicators
            data_with_indicators = await strategy.calculate_indicators(data)

            # Test signal generation
            direction, breakdown = await strategy.should_enter_trade("BTC/USDC:USDC", data_with_indicators)

            if direction:
                print(f"     ✅ Signal generated: {direction}")
                print(f"     📊 Entry price: {breakdown.get('entry_price', 'N/A')}")
                print(f"     📈 MACD strength: {breakdown.get('macd_strength', 'N/A')}")
                print(f"     📉 RSI strength: {breakdown.get('rsi_strength', 'N/A')}")
                print(f"     📊 Volume ratio: {breakdown.get('volume_ratio', 'N/A')}")
                print(f"     📈 ATR percent: {breakdown.get('atr_percent', 'N/A')}")

                # Test 1+1 logic
                passes_1plus1 = strategy.passes_1plus1(breakdown)
                print(f"     ✅ Passes 1+1 logic: {passes_1plus1}")

                # Simulate order placement
                if passes_1plus1:
                    print(f"     🎯 Would place {direction} order")

                    # Calculate TP/SL
                    entry_price = breakdown.get('entry_price', 50000)
                    if direction == "buy":
                        tp_price = entry_price * (1 + config.take_profit_percent / 100)
                        sl_price = entry_price * (1 - config.stop_loss_percent / 100)
                    else:
                        tp_price = entry_price * (1 - config.take_profit_percent / 100)
                        sl_price = entry_price * (1 + config.stop_loss_percent / 100)

                    print(f"       Entry: {entry_price:.2f}")
                    print(f"       TP: {tp_price:.2f} ({config.take_profit_percent}%)")
                    print(f"       SL: {sl_price:.2f} ({config.stop_loss_percent}%)")
                    print(f"       Size: {config.min_position_size_usdt} USDT")
                else:
                    print(f"     ❌ Signal rejected by 1+1 logic")
            else:
                print(f"     ⚠️ No signal generated")
                if 'reason' in breakdown:
                    print(f"       Reason: {breakdown['reason']}")

        # Test 3: Test with different symbols
        print("\n🔍 Testing Different Symbols...")

        symbols = ["BTC/USDC:USDC", "ETH/USDC:USDC", "SOL/USDC:USDC", "BNB/USDC:USDC"]

        for symbol in symbols:
            print(f"\n   Testing {symbol}...")

            # Use bullish data for all symbols (just for testing)
            direction, breakdown = await strategy.should_enter_trade(symbol, data_with_indicators)

            if direction:
                print(f"     ✅ Signal: {direction}")
                print(f"     📊 Price: {breakdown.get('entry_price', 'N/A')}")
            else:
                print(f"     ⚠️ No signal")

        # Test 4: Test market conditions validation
        print("\n🔍 Testing Market Conditions Validation...")

        current_data = data_with_indicators.iloc[-1]
        is_valid, reason = strategy.validate_market_conditions(current_data)

        print(f"   Market conditions valid: {is_valid}")
        if not is_valid:
            print(f"   Reason: {reason}")

        # Test 5: Test signal breakdown
        print("\n🔍 Testing Signal Breakdown...")

        if len(data_with_indicators) >= 2:
            current = data_with_indicators.iloc[-1]
            prev = data_with_indicators.iloc[-2]

            breakdown = strategy.get_signal_breakdown(current, prev)
            print(f"   Signal breakdown components: {len(breakdown)}")

            for key, value in breakdown.items():
                if isinstance(value, (int, float)) and value > 0:
                    print(f"     {key}: {value}")

        print("\n✅ Strategy simulation test completed successfully!")

    except Exception as e:
        print(f"❌ Error in strategy simulation test: {e}")
        import traceback
        traceback.print_exc()


def create_bullish_mock_data(periods: int = 100) -> pd.DataFrame:
    """Create bullish trend mock data"""
    np.random.seed(42)

    # Generate bullish trend
    base_price = 50000
    trend = np.linspace(0, 0.15, periods)  # 15% upward trend
    noise = np.random.normal(0, 0.02, periods)
    returns = trend + noise

    prices = [base_price]
    for ret in returns[1:]:
        new_price = prices[-1] * (1 + ret)
        prices.append(new_price)

    # Create OHLCV data
    data = []
    for i in range(periods):
        price = prices[i]
        volatility = abs(np.random.normal(0, 0.01))
        high = price * (1 + volatility)
        low = price * (1 - volatility)
        open_price = price * (1 + np.random.normal(0, 0.005))
        close = price
        volume = 1000 * np.random.uniform(2.0, 4.0)  # Higher volume for bullish trend

        data.append({
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        })

    df = pd.DataFrame(data)
    df.index = pd.date_range(start='2024-01-01', periods=periods, freq='5min')

    return df


def create_bearish_mock_data(periods: int = 100) -> pd.DataFrame:
    """Create bearish trend mock data"""
    np.random.seed(43)

    # Generate bearish trend
    base_price = 50000
    trend = np.linspace(0, -0.12, periods)  # 12% downward trend
    noise = np.random.normal(0, 0.02, periods)
    returns = trend + noise

    prices = [base_price]
    for ret in returns[1:]:
        new_price = prices[-1] * (1 + ret)
        prices.append(new_price)

    # Create OHLCV data
    data = []
    for i in range(periods):
        price = prices[i]
        volatility = abs(np.random.normal(0, 0.015))  # Higher volatility for bearish
        high = price * (1 + volatility)
        low = price * (1 - volatility)
        open_price = price * (1 + np.random.normal(0, 0.005))
        close = price
        volume = 1000 * np.random.uniform(1.8, 3.5)  # Higher volume for bearish

        data.append({
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        })

    df = pd.DataFrame(data)
    df.index = pd.date_range(start='2024-01-01', periods=periods, freq='5min')

    return df


def create_sideways_mock_data(periods: int = 100) -> pd.DataFrame:
    """Create sideways market mock data"""
    np.random.seed(44)

    # Generate sideways movement
    base_price = 50000
    noise = np.random.normal(0, 0.015, periods)  # Moderate volatility
    returns = noise

    prices = [base_price]
    for ret in returns[1:]:
        new_price = prices[-1] * (1 + ret)
        prices.append(new_price)

    # Create OHLCV data
    data = []
    for i in range(periods):
        price = prices[i]
        volatility = abs(np.random.normal(0, 0.008))  # Lower volatility
        high = price * (1 + volatility)
        low = price * (1 - volatility)
        open_price = price * (1 + np.random.normal(0, 0.003))
        close = price
        volume = 1000 * np.random.uniform(1.5, 2.5)  # Moderate volume for sideways

        data.append({
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        })

    df = pd.DataFrame(data)
    df.index = pd.date_range(start='2024-01-01', periods=periods, freq='5min')

    return df


async def main():
    """Main test function"""
    print("🚀 Starting Strategy Simulation Tests...")
    print("=" * 50)

    await test_strategy_simulation()

    print("\n" + "=" * 50)
    print("🎉 Strategy simulation tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
