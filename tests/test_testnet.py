#!/usr/bin/env python3
"""Test Binance Futures Testnet connection"""

import asyncio

import ccxt.async_support as ccxt


async def test_testnet_connection():
    """Test connection to Binance Futures testnet"""

    # Create exchange instance with testnet configuration
    exchange = ccxt.binance(
        {
            "apiKey": "your_testnet_api_key",  # Will be replaced with actual key
            "secret": "your_testnet_api_secret",  # Will be replaced with actual secret
            "options": {
                "defaultType": "future",  # USDT-M futures
                "fetchCurrencies": False,  # Skip fetching currencies on testnet
                "adjustForTimeDifference": True,
                "recvWindow": 60000,
            },
            "sandbox": False,  # Important: disable sandbox mode
            "urls": {
                "api": {
                    "public": "https://testnet.binancefuture.com",
                    "private": "https://testnet.binancefuture.com",
                    "fapiPublic": "https://testnet.binancefuture.com/fapi/v1",
                    "fapiPrivate": "https://testnet.binancefuture.com/fapi/v1",
                }
            },
        }
    )

    try:
        print("🔄 Loading markets from testnet...")
        await exchange.load_markets()
        print(f"✅ Successfully loaded {len(exchange.markets)} markets")

        # Show some USDT pairs
        usdt_pairs = [s for s in exchange.markets if "USDT" in s and ":" in s]
        print(f"\n📊 Found {len(usdt_pairs)} USDT perpetual pairs")
        print(f"First 10 USDT pairs: {usdt_pairs[:10]}")

        # Test public API - fetch ticker
        if usdt_pairs:
            test_symbol = usdt_pairs[0]
            print(f"\n🔍 Testing ticker for {test_symbol}...")
            ticker = await exchange.fetch_ticker(test_symbol)
            print(f"✅ Ticker fetched - Last price: {ticker['last']}")

        print("\n✅ Testnet connection successful!")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await exchange.close()


if __name__ == "__main__":
    # Fix for Windows - use SelectorEventLoop
    if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_testnet_connection())
