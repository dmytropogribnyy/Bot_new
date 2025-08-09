#!/usr/bin/env python3
"""Check and clean up orphaned orders"""

import asyncio
import os

from dotenv import load_dotenv

# Fix for Windows
if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()

import ccxt.async_support as ccxt


async def check_and_clean_orders():
    """Check for orphaned orders and clean them up"""

    API_KEY = os.getenv("BINANCE_API_KEY")
    API_SECRET = os.getenv("BINANCE_API_SECRET")

    exchange = ccxt.binance(
        {
            "apiKey": API_KEY,
            "secret": API_SECRET,
            "enableRateLimit": True,
            "options": {
                "defaultType": "future",
                "adjustForTimeDifference": True,
                "warnOnFetchOpenOrdersWithoutSymbol": False,  # Disable warning
            },
        }
    )

    exchange.set_sandbox_mode(True)

    try:
        await exchange.load_markets()

        print("=" * 60)
        print("🔍 CHECKING ORDERS AND POSITIONS")
        print("=" * 60)

        # Check positions
        positions = await exchange.fetch_positions()
        open_positions = [p for p in positions if p["contracts"] > 0]

        print(f"\n📊 Open positions: {len(open_positions)}")
        position_symbols = set()

        for pos in open_positions:
            symbol = pos["symbol"]
            position_symbols.add(symbol)
            print(f"  - {symbol}: {pos['contracts']} {pos['side']}, PnL: ${pos.get('unrealizedPnl', 0):.2f}")

        # Check all open orders
        print("\n📝 Checking open orders...")
        try:
            all_orders = await exchange.fetch_open_orders()
            print(f"Found {len(all_orders)} open order(s)")

            orphaned_orders = []

            for order in all_orders:
                symbol = order["symbol"]
                order_type = order["type"]
                side = order["side"]
                price = order["price"]
                amount = order["amount"]

                # Check if this order has a corresponding position
                has_position = symbol in position_symbols

                status = "ACTIVE" if has_position else "ORPHANED"

                print(f"  - {symbol}: {order_type} {side} @ ${price:.2f} ({amount}) - {status}")

                if not has_position:
                    orphaned_orders.append(order)

            # Cancel orphaned orders
            if orphaned_orders:
                print(f"\n🗑️ Found {len(orphaned_orders)} orphaned order(s). Cancelling...")

                for order in orphaned_orders:
                    try:
                        await exchange.cancel_order(order["id"], order["symbol"])
                        print(f"  ✅ Cancelled: {order['symbol']} {order['type']} {order['side']}")
                    except Exception as e:
                        print(f"  ❌ Failed to cancel {order['id']}: {e}")

                print("\n✅ Cleanup complete!")
            else:
                print("\n✅ No orphaned orders found")

        except Exception as e:
            print(f"Error checking orders: {e}")

        # Final status
        balance = await exchange.fetch_balance()
        usdt = balance["USDT"]["free"] if "USDT" in balance else 0
        print(f"\n💰 Balance: {usdt:.2f} USDT")

        print("\n" + "=" * 60)

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        await exchange.close()


if __name__ == "__main__":
    asyncio.run(check_and_clean_orders())
