#!/usr/bin/env python3
"""Test Telegram bot connection"""

import asyncio
import os

from dotenv import load_dotenv

# Fix for Windows
if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()

# Get Telegram credentials
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

print(f"Token present: {bool(TELEGRAM_TOKEN)}")
print(f"Chat ID: {TELEGRAM_CHAT_ID}")

import aiohttp


async def send_test_message():
    """Send a test message to Telegram"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Missing Telegram credentials")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    messages = [
        "🚀 BinanceBot Testnet Connected!",
        "✅ Balance: 15000 USDT",
        "📊 Markets loaded successfully",
        "🔄 Bot is running on testnet",
    ]

    async with aiohttp.ClientSession() as session:
        for msg in messages:
            payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}

            try:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        print(f"✅ Sent: {msg}")
                    else:
                        text = await response.text()
                        print(f"❌ Failed: {text}")
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(send_test_message())
