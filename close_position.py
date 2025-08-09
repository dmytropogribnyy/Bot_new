#!/usr/bin/env python3
"""Close test position on testnet"""

import asyncio
import os
from datetime import datetime

from dotenv import load_dotenv

# Fix for Windows
if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()

import aiohttp
import ccxt.async_support as ccxt

API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


async def send_telegram(message):
    """Send message to Telegram"""
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(url, json=payload)
        except:
            pass


async def close_test_position():
    """Close the test position"""

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
        print("🔄 CLOSING TEST POSITION ON TESTNET")
        print("=" * 60)

        # Load markets
        await exchange.load_markets()

        # Get all positions
        positions = await exchange.fetch_positions()
        open_positions = [p for p in positions if p["contracts"] > 0]

        if not open_positions:
            print("\n❌ No open positions to close")
            return

        for pos in open_positions:
            symbol = pos["symbol"]
            contracts = pos["contracts"]
            side = pos["side"]
            unrealized_pnl = pos["unrealizedPnl"] or 0
            mark_price = pos["markPrice"] or 0

            print("\n📊 Found position:")
            print(f"   Symbol: {symbol}")
            print(f"   Size: {contracts} contracts")
            print(f"   Side: {side}")
            print(f"   Mark Price: ${mark_price:.2f}")
            print(f"   Unrealized PnL: ${unrealized_pnl:.2f}")

            # Determine closing side (opposite of position side)
            close_side = "sell" if side == "long" else "buy"

            print(f"\n📝 Closing position with MARKET {close_side.upper()} order...")

            # Cancel existing orders first
            try:
                open_orders = await exchange.fetch_open_orders(symbol)
                for order in open_orders:
                    await exchange.cancel_order(order["id"], symbol)
                    print(f"   ❌ Cancelled order: {order['id']}")
            except:
                pass

            # Place market order to close
            close_order = await exchange.create_order(
                symbol=symbol, type="market", side=close_side, amount=contracts, params={"reduceOnly": True}
            )

            print("\n✅ Close order placed!")
            print(f"   Order ID: {close_order['id']}")
            print(f"   Status: {close_order['status']}")

            # Wait for position to close
            await asyncio.sleep(2)

            # Check if closed
            new_positions = await exchange.fetch_positions([symbol])
            if new_positions and new_positions[0]["contracts"] == 0:
                print("\n✅ Position CLOSED successfully!")
                print(f"   Final PnL: ${unrealized_pnl:.2f}")

                # Send Telegram notification
                msg = f"""
🔴 <b>Position Closed (Manual)</b>
━━━━━━━━━━━━━━━━━━
📊 {symbol}
💰 PnL: ${unrealized_pnl:.2f}
⏰ {datetime.now().strftime("%H:%M:%S")}
━━━━━━━━━━━━━━━━━━
"""
                await send_telegram(msg)
            else:
                print("\n⚠️ Position may still be open, check manually")

        # Final balance check
        balance = await exchange.fetch_balance()
        usdt_balance = balance["USDT"]["free"] if "USDT" in balance else 0
        print(f"\n💰 Final Balance: {usdt_balance:.2f} USDT")

        print("\n" + "=" * 60)
        print("✅ CLOSE OPERATION COMPLETED!")
        print("Check your bot logs to see if it detected the closure")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        await exchange.close()


if __name__ == "__main__":
    asyncio.run(close_test_position())
