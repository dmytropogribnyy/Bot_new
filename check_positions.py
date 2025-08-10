#!/usr/bin/env python3
"""Check current positions on testnet"""

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


async def check_positions():
    """Check current positions"""

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
        print("📊 CHECKING POSITIONS ON TESTNET")
        print("=" * 60)

        # Load markets
        await exchange.load_markets()

        # Get balance
        balance = await exchange.fetch_balance()
        usdt_balance = balance["USDT"]["free"] if "USDT" in balance else 0
        print(f"\n💰 Balance: {usdt_balance:.2f} USDT")

        # Get all positions
        positions = await exchange.fetch_positions()
        open_positions = [p for p in positions if p["contracts"] > 0]

        if open_positions:
            print(f"\n📈 Found {len(open_positions)} open position(s):")
            for pos in open_positions:
                symbol = pos["symbol"]
                contracts = pos["contracts"]
                side = pos["side"]
                unrealized_pnl = pos["unrealizedPnl"] or 0
                mark_price = pos["markPrice"] or 0
                entry_price = pos["entryPrice"] or 0

                print(f"\n  Symbol: {symbol}")
                print(f"  Size: {contracts} contracts")
                print(f"  Side: {side}")
                print(f"  Entry Price: ${entry_price:.2f}")
                print(f"  Mark Price: ${mark_price:.2f}")
                print(f"  Unrealized PnL: ${unrealized_pnl:.2f}")

            # Check open orders
            print("\n📝 Checking open orders...")
            all_orders = await exchange.fetch_open_orders()
            if all_orders:
                print(f"Found {len(all_orders)} open order(s):")
                for order in all_orders:
                    print(f"  - {order['symbol']}: {order['type']} {order['side']} @ {order['price']}")
            else:
                print("No open orders")
        else:
            print("\n✅ No open positions")

            # Check if there are any open orders without positions
            all_orders = await exchange.fetch_open_orders()
            if all_orders:
                print(f"\n⚠️ Found {len(all_orders)} orphaned order(s) (no position):")
                for order in all_orders:
                    print(f"  - {order['symbol']}: {order['type']} {order['side']} @ {order['price']}")

        print("\n" + "=" * 60)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        await exchange.close()


if __name__ == "__main__":
    asyncio.run(check_positions())
