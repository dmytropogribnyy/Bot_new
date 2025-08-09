import asyncio
import os

from dotenv import load_dotenv

if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()

import ccxt.async_support as ccxt


async def quick_check():
    API_KEY = os.getenv("BINANCE_API_KEY")
    API_SECRET = os.getenv("BINANCE_API_SECRET")

    exchange = ccxt.binance(
        {"apiKey": API_KEY, "secret": API_SECRET, "enableRateLimit": True, "options": {"defaultType": "future"}}
    )

    exchange.set_sandbox_mode(True)

    try:
        await exchange.load_markets()

        # Balance
        balance = await exchange.fetch_balance()
        usdt = balance["USDT"]["free"] if "USDT" in balance else 0
        print(f"Balance: {usdt:.2f} USDT")

        # Positions
        positions = await exchange.fetch_positions()
        open_pos = [p for p in positions if p["contracts"] > 0]

        if open_pos:
            print(f"Open positions: {len(open_pos)}")
            for p in open_pos:
                print(f"  - {p['symbol']}: {p['contracts']} contracts, PnL: ${p.get('unrealizedPnl', 0):.2f}")
        else:
            print("No open positions")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await exchange.close()


if __name__ == "__main__":
    asyncio.run(quick_check())
