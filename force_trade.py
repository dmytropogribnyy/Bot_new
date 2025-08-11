#!/usr/bin/env python3
"""Force open a test position on testnet"""

import asyncio

from dotenv import load_dotenv

from core.config import TradingConfig

# Fix for Windows
if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()

import ccxt.async_support as ccxt

cfg = TradingConfig.from_env()
API_KEY = cfg.api_key
API_SECRET = cfg.api_secret


async def force_test_trade():
    """Force open a small test position"""

    exchange = ccxt.binance(
        {
            "apiKey": API_KEY,
            "secret": API_SECRET,
            "enableRateLimit": True,
            "options": {
                "defaultType": "future",
                "adjustForTimeDifference": True,
            },
        }
    )

    # Enable testnet
    exchange.set_sandbox_mode(True)

    try:
        print("=" * 60)
        print("🚀 FORCING TEST TRADE ON TESTNET")
        print("=" * 60)

        # Load markets
        await exchange.load_markets()

        # Get balance
        balance = await exchange.fetch_balance()
        usdt_balance = balance["USDT"]["free"] if "USDT" in balance else 0
        print(f"\n💰 Available balance: {usdt_balance:.2f} USDT")

        # Choose symbol
        symbol = "BTC/USDT:USDT"  # Bitcoin perpetual

        # Get current price
        ticker = await exchange.fetch_ticker(symbol)
        current_price = ticker["last"]
        print(f"\n📊 {symbol} current price: ${current_price:.2f}")

        # Calculate position size (minimum allowed for BTC is 0.001)
        contracts = 0.001  # Minimum BTC amount
        position_size_usdt = contracts * current_price

        print(f"\n⚠️ Minimum position size for BTC: 0.001 BTC = ${position_size_usdt:.2f}")

        # Set leverage
        leverage = 5
        await exchange.set_leverage(leverage, symbol)
        print(f"⚙️ Leverage set to {leverage}x")

        # Place market order
        side = "buy"  # Long position
        order_type = "market"

        print(f"\n📝 Placing {side.upper()} order:")
        print(f"   Size: {contracts:.6f} BTC (${position_size_usdt:.2f})")
        print(f"   Leverage: {leverage}x")

        # Create order
        order = await exchange.create_order(symbol=symbol, type=order_type, side=side, amount=contracts)

        print("\n✅ Order placed successfully!")
        print(f"   Order ID: {order['id']}")
        print(f"   Status: {order['status']}")

        # Wait a bit
        await asyncio.sleep(2)

        # Check position
        positions = await exchange.fetch_positions([symbol])
        if positions:
            pos = positions[0]
            print("\n📈 Position opened:")
            print(f"   Contracts: {pos['contracts']}")
            print(f"   Entry price: ${pos['markPrice']:.2f}")
            print(f"   Unrealized PnL: ${pos['unrealizedPnl']:.2f}")

            # Place TP and SL orders
            tp_price = current_price * 1.01  # 1% profit
            sl_price = current_price * 0.98  # 2% loss

            print("\n🎯 Setting TP/SL:")
            print(f"   Take Profit: ${tp_price:.2f} (+1%)")
            print(f"   Stop Loss: ${sl_price:.2f} (-2%)")

            # TP order
            tp_order = await exchange.create_order(
                symbol=symbol, type="limit", side="sell", amount=contracts, price=tp_price, params={"reduceOnly": True}
            )
            print(f"   ✅ TP order placed: {tp_order['id']}")

            # SL order
            sl_order = await exchange.create_order(
                symbol=symbol,
                type="stop_market",
                side="sell",
                amount=contracts,
                params={"stopPrice": sl_price, "reduceOnly": True},
            )
            print(f"   ✅ SL order placed: {sl_order['id']}")

        print("\n" + "=" * 60)
        print("✅ TEST TRADE COMPLETED SUCCESSFULLY!")
        print("Check your bot logs to see if it's tracking this position")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        await exchange.close()


if __name__ == "__main__":
    asyncio.run(force_test_trade())
