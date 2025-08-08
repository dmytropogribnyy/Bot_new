#!/usr/bin/env python3
"""
Test script for dry-run strategy testing with simulated signals
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
from core.exchange_client import OptimizedExchangeClient
from core.symbol_manager import SymbolManager
from core.strategy_manager import StrategyManager
from core.order_manager import OrderManager


async def test_dry_run_strategy():
    """Test the strategy in dry-run mode with simulated signals"""
    print("🧪 Testing Dry-Run Strategy...")

    try:
        # Initialize components
        config = TradingConfig()
        config.dry_run = True
        config.testnet = True

        logger = UnifiedLogger(config)
        logger.log_event("TEST", "INFO", "Starting dry-run strategy test")

        # Initialize exchange client (will use testnet)
        exchange = OptimizedExchangeClient(config, logger)
        await exchange.initialize()

        # Initialize managers
        symbol_manager = SymbolManager(config, exchange, logger)
        strategy_manager = StrategyManager(config, exchange, symbol_manager, logger)
        order_manager = OrderManager(config, exchange, logger)

        print("✅ Components initialized successfully")

        # Test 1: Get available symbols
        print("\n📊 Testing Symbol Management...")
        symbols = await symbol_manager.get_available_symbols()
        print(f"   Available symbols: {len(symbols)}")
        for i, symbol in enumerate(symbols[:3]):
            print(f"   {i+1}. {symbol}")

        # Test 2: Create mock OHLCV data for testing
        print("\n📈 Creating mock market data...")
        mock_data = create_realistic_mock_data()
        print(f"   Created mock data: {mock_data.shape}")

        # Test 3: Test strategy evaluation with mock data
        print("\n🔍 Testing Strategy Evaluation...")
        strategy = strategy_manager.get_active_strategy()

        # Test with different symbols
        test_symbols = ["BTC/USDC:USDC", "ETH/USDC:USDC", "SOL/USDC:USDC"]

        for symbol in test_symbols:
            print(f"\n   Testing {symbol}...")

            # Evaluate symbol
            direction, breakdown = await strategy.should_enter_trade(symbol, mock_data)

            if direction:
                print(f"     ✅ Signal generated: {direction}")
                print(f"     📊 Breakdown: {len(breakdown)} components")

                # Test order placement simulation
                print(f"     🎯 Simulating order placement...")

                # Calculate position size
                entry_price = breakdown.get('entry_price', 50000)
                position_size_usdc = config.position_size_usdc

                # Calculate TP/SL prices
                if direction == "buy":
                    tp_price = entry_price * (1 + config.target_profit_percent / 100)
                    sl_price = entry_price * (1 - config.stop_loss_percent / 100)
                else:
                    tp_price = entry_price * (1 - config.target_profit_percent / 100)
                    sl_price = entry_price * (1 + config.stop_loss_percent / 100)

                print(f"       Entry: {entry_price:.2f}")
                print(f"       TP: {tp_price:.2f} ({config.target_profit_percent}%)")
                print(f"       SL: {sl_price:.2f} ({config.stop_loss_percent}%)")
                print(f"       Size: {position_size_usdc} USDC")

                # Simulate order placement
                order_result = await order_manager.place_position_with_tp_sl(
                    symbol, direction, position_size_usdc, entry_price, tp_price, sl_price
                )

                if order_result.get('success'):
                    print(f"     ✅ Order simulation successful")
                    print(f"       Order ID: {order_result.get('order_id', 'SIMULATED')}")
                    print(f"       TP Order: {order_result.get('tp_order_id', 'SIMULATED')}")
                    print(f"       SL Order: {order_result.get('sl_order_id', 'SIMULATED')}")
                else:
                    print(f"     ❌ Order simulation failed: {order_result.get('error', 'Unknown error')}")

            else:
                print(f"     ⚠️ No signal generated")
                if 'reason' in breakdown:
                    print(f"       Reason: {breakdown['reason']}")

        # Test 4: Scan for opportunities
        print("\n🔍 Testing Opportunity Scanning...")
        opportunities = await strategy_manager.scan_for_opportunities()
        print(f"   Found opportunities: {len(opportunities)}")

        for symbol, direction, breakdown in opportunities[:2]:
            print(f"     - {symbol}: {direction}")

        # Test 5: Runtime status logging
        print("\n📊 Testing Runtime Status...")
        await log_runtime_status(exchange, order_manager, logger)

        print("\n✅ Dry-run strategy test completed successfully!")

    except Exception as e:
        print(f"❌ Error in dry-run strategy test: {e}")
        import traceback
        traceback.print_exc()


def create_realistic_mock_data(periods: int = 100) -> pd.DataFrame:
    """Create realistic mock OHLCV data for testing"""
    np.random.seed(42)  # For reproducible results

    # Generate realistic price data with trends
    base_price = 50000
    returns = np.random.normal(0, 0.02, periods)  # 2% daily volatility

    # Add some trend
    trend = np.linspace(0, 0.1, periods)  # 10% upward trend
    returns += trend

    prices = [base_price]

    for ret in returns[1:]:
        new_price = prices[-1] * (1 + ret)
        prices.append(new_price)

    # Create OHLCV data
    data = []
    for i in range(periods):
        price = prices[i]

        # Generate realistic OHLC
        volatility = abs(np.random.normal(0, 0.01))
        high = price * (1 + volatility)
        low = price * (1 - volatility)
        open_price = price * (1 + np.random.normal(0, 0.005))
        close = price

        # Generate realistic volume
        base_volume = 1000
        volume_spike = np.random.choice([1, 2, 3], p=[0.7, 0.2, 0.1])  # 30% chance of volume spike
        volume = base_volume * volume_spike * np.random.uniform(0.8, 1.2)

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


async def log_runtime_status(exchange, order_manager, logger):
    """Log runtime status for testing"""
    try:
        # Get balance
        balance = await exchange.get_balance()
        print(f"   💰 Balance: {balance.get('USDC', 0):.2f} USDC")

        # Get active positions
        positions = await order_manager.get_active_positions()
        print(f"   📈 Active positions: {len(positions)}")

        # Get pending orders
        pending_orders = await order_manager.get_pending_orders()
        print(f"   ⏳ Pending orders: {len(pending_orders)}")

        # Calculate PnL
        total_pnl = sum(pos.get('unrealized_pnl', 0) for pos in positions.values())
        print(f"   📊 Total PnL: {total_pnl:.2f} USDC")

    except Exception as e:
        print(f"   ❌ Error getting runtime status: {e}")


async def main():
    """Main test function"""
    print("🚀 Starting Dry-Run Strategy Tests...")
    print("=" * 50)

    await test_dry_run_strategy()

    print("\n" + "=" * 50)
    print("🎉 Dry-run strategy tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
