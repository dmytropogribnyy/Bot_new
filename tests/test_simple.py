#!/usr/bin/env python3
"""Simple test for Binance Futures Testnet"""

import asyncio
import os

# Fix for Windows
if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Load environment variables
from dotenv import load_dotenv

load_dotenv()

# Get API keys from environment
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

print(f"API Key present: {bool(API_KEY)}")
print(f"API Secret present: {bool(API_SECRET)}")
print(f"Testnet mode: {os.getenv('BINANCE_TESTNET')}")

import ccxt

# Create synchronous exchange for testing
exchange = ccxt.binance(
    {
        "apiKey": API_KEY,
        "secret": API_SECRET,
        "enableRateLimit": True,
        "options": {
            "defaultType": "future",  # USDT-M futures
            "adjustForTimeDifference": True,
            "recvWindow": 60000,
        },
    }
)

# Set testnet URLs
exchange.set_sandbox_mode(True)  # This enables testnet mode in ccxt

try:
    print("\n🔄 Testing connection to Binance Futures Testnet...")

    # Test 1: Load markets (public API)
    print("Loading markets...")
    markets = exchange.load_markets()
    print(f"✅ Loaded {len(markets)} markets")

    # Show some USDT futures
    usdt_futures = [s for s in markets if "USDT" in s and ":" in s]
    print(f"Found {len(usdt_futures)} USDT perpetual futures")
    if usdt_futures:
        print(f"Examples: {usdt_futures[:5]}")

    # Test 2: Fetch balance (private API)
    print("\n🔄 Testing private API...")
    try:
        balance = exchange.fetch_balance()
        usdt_balance = balance["USDT"]["free"] if "USDT" in balance else 0
        print(f"✅ USDT Balance: {usdt_balance}")
    except Exception as e:
        print(f"⚠️ Private API error (this is normal if you don't have testnet balance): {e}")

    # Test 3: Fetch ticker (public API)
    if usdt_futures:
        test_symbol = usdt_futures[0]
        print(f"\n🔄 Fetching ticker for {test_symbol}...")
        ticker = exchange.fetch_ticker(test_symbol)
        print(f"✅ Last price: {ticker['last']}")

    print("\n✅ Connection test successful!")
    print("\n📝 Next steps:")
    print("1. Make sure you have some USDT balance on testnet")
    print("2. The bot should work with these settings")

except Exception as e:
    print(f"\n❌ Error: {e}")
    print("\n📝 Troubleshooting:")
    print("1. Make sure your API keys are from https://testnet.binancefuture.com")
    print("2. Check that the keys have futures trading permissions")
    print("3. Try generating new testnet API keys")
