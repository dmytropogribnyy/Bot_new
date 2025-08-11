import asyncio

from dotenv import load_dotenv

from core.config import TradingConfig

if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()

import ccxt.async_support as ccxt


async def quick_check():
    cfg = TradingConfig.from_env()
    API_KEY = cfg.api_key
    API_SECRET = cfg.api_secret

    exchange = ccxt.binance(
        {"apiKey": API_KEY, "secret": API_SECRET, "enableRateLimit": True, "options": {"defaultType": "future"}}
    )

    exchange.set_sandbox_mode(True)

    try:
        await exchange.load_markets()

        # Balance
        balance = await exchange.fetch_balance()
        from core.balance_utils import free

        q = cfg.resolved_quote_coin
        qbal = free(balance, q)
        print(f"Balance: {qbal:.2f} {q}")

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
