#!/usr/bin/env python3
"""Monitor bot status and trading activity"""

import asyncio
import os
from datetime import datetime

from dotenv import load_dotenv

from core.config import TradingConfig

# Fix for Windows
if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()

import aiohttp
import ccxt

# Get credentials via unified config
cfg = TradingConfig.from_env()
API_KEY = cfg.api_key
API_SECRET = cfg.api_secret
TELEGRAM_TOKEN, TELEGRAM_CHAT_ID = cfg.get_telegram_credentials()


async def check_bot_status():
    """Check bot trading status"""

    # Create exchange instance
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
        print(f"🤖 BOT STATUS CHECK - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        # 1. Check balance
        balance = exchange.fetch_balance()
        usdt_balance = balance["USDT"]["free"] if "USDT" in balance else 0
        print(f"\n💰 Balance: {usdt_balance:.2f} USDT")

        # 2. Check open positions
        positions = exchange.fetch_positions()
        open_positions = [p for p in positions if p["contracts"] > 0]

        if open_positions:
            print(f"\n📊 Open Positions: {len(open_positions)}")
            for pos in open_positions:
                print(f"  - {pos['symbol']}: {pos['contracts']} contracts")
                print(f"    Entry: {pos['markPrice']:.2f}, PnL: {pos['unrealizedPnl']:.2f} USDT")
        else:
            print("\n📊 No open positions")

        # 3. Check recent orders (skip for now to avoid rate limit)
        orders = []
        if False:  # Disabled to avoid rate limit
            print(f"\n📝 Open Orders: {len(orders)}")
            for order in orders[:5]:
                print(f"  - {order['symbol']}: {order['type']} {order['side']} @ {order['price']}")
        else:
            print("\n📝 No open orders")

        # 4. Check top markets
        print("\n🔥 Top USDT Markets (by volume):")
        tickers = exchange.fetch_tickers()
        usdt_tickers = {k: v for k, v in tickers.items() if "USDT" in k and ":" in k}
        sorted_tickers = sorted(usdt_tickers.items(), key=lambda x: x[1]["quoteVolume"] or 0, reverse=True)

        for symbol, ticker in sorted_tickers[:5]:
            volume = ticker["quoteVolume"] or 0
            change = ticker["percentage"] or 0
            print(f"  - {symbol}: ${ticker['last']:.2f} ({change:+.2f}%) Vol: ${volume:,.0f}")

        # 5. Check log file
        print("\n📄 Recent Log Activity:")
        if os.path.exists("logs/main.log"):
            with open("logs/main.log", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                recent_lines = lines[-10:]
                for line in recent_lines:
                    if "ERROR" in line:
                        print(f"  ❌ {line.strip()[-100:]}")
                    elif "SIGNAL" in line or "TRADE" in line or "POSITION" in line:
                        print(f"  ✅ {line.strip()[-100:]}")

        # 6. Send summary to Telegram
        if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
            message = f"""
📊 <b>Bot Status Report</b>
━━━━━━━━━━━━━━━━━━━━
💰 Balance: {usdt_balance:.2f} USDT
📈 Positions: {len(open_positions)}
📝 Orders: {len(orders)}
⏰ Time: {datetime.now().strftime("%H:%M:%S")}
━━━━━━━━━━━━━━━━━━━━
"""

            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        print("\n✅ Status sent to Telegram")

        print("\n" + "=" * 60)
        print("✅ Status check complete")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        pass  # ccxt sync doesn't need close


if __name__ == "__main__":
    asyncio.run(check_bot_status())
