#!/usr/bin/env python3
"""Test graceful shutdown with position closing"""

import asyncio
import os
import sys

from dotenv import load_dotenv

# Fix for Windows
if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ccxt.async_support as ccxt


async def test_shutdown():
    """Test shutdown procedure"""

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
            },
        }
    )

    # Enable testnet
    exchange.set_sandbox_mode(True)

    try:
        print("=" * 60)
        print("🧪 TESTING SHUTDOWN WITH POSITION CLOSING")
        print("=" * 60)

        # Load markets
        await exchange.load_markets()

        # Check current positions
        print("\n📊 Checking current positions...")
        positions = await exchange.fetch_positions()
        open_positions = [p for p in positions if p["contracts"] > 0]

        if open_positions:
            print(f"Found {len(open_positions)} open position(s)")

            for pos in open_positions:
                symbol = pos["symbol"]
                contracts = pos["contracts"]
                side = pos["side"]
                unrealized_pnl = pos["unrealizedPnl"] or 0

                print(f"\n📈 Position: {symbol}")
                print(f"   Size: {contracts} contracts")
                print(f"   Side: {side}")
                print(f"   PnL: ${unrealized_pnl:.2f}")

                # Close position
                print("\n🔄 Closing position...")
                close_side = "sell" if side == "long" else "buy"

                # Cancel orders first
                try:
                    open_orders = await exchange.fetch_open_orders(symbol)
                    for order in open_orders:
                        await exchange.cancel_order(order["id"], symbol)
                        print(f"   ❌ Cancelled order {order['id']}")
                except Exception:
                    import logging

                    logging.getLogger(__name__).exception("shutdown test failed", exc_info=True)
                    raise

                # Place close order
                close_order = await exchange.create_order(
                    symbol=symbol, type="market", side=close_side, amount=contracts, params={"reduceOnly": True}
                )

                print(f"   ✅ Close order placed: {close_order['id']}")

            # Wait and verify
            await asyncio.sleep(2)

            final_positions = await exchange.fetch_positions()
            still_open = [p for p in final_positions if p["contracts"] > 0]

            if still_open:
                print(f"\n⚠️ {len(still_open)} position(s) still open")
            else:
                print("\n✅ All positions closed successfully!")

        else:
            print("No open positions found")

        # Check final balance
        balance = await exchange.fetch_balance()
        usdt_balance = balance["USDT"]["free"] if "USDT" in balance else 0
        print(f"\n💰 Final balance: {usdt_balance:.2f} USDT")

        print("\n" + "=" * 60)
        print("✅ SHUTDOWN TEST COMPLETE")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        await exchange.close()


if __name__ == "__main__":
    print("This simulates what happens when you press Ctrl+C")
    print("The bot should close all positions before shutting down\n")
    asyncio.run(test_shutdown())
