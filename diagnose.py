import asyncio
import os
import sys

from core.config import TradingConfig
from core.unified_logger import UnifiedLogger

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Отключить Telegram для теста
os.environ["TELEGRAM_ENABLED"] = "false"


async def test_exchange():
    """Test exchange connection"""
    config = TradingConfig()
    logger = UnifiedLogger(config)

    print(f"🔧 Config: testnet={config.testnet}, api_key={'✓' if config.api_key else '✗'}")

    from core.exchange_client import OptimizedExchangeClient

    exchange = OptimizedExchangeClient(config, logger)
    print("📡 Before init: exchange object created")

    try:
        await exchange.initialize()
        print("✅ Exchange initialized!")

        if hasattr(exchange.exchange, "urls"):
            api_url = exchange.exchange.urls.get("api", "unknown")
            print(f"📡 After init: API URL={api_url}")
    except Exception as e:
        print(f"❌ Init error: {e}")
        return

    # Тест простого запроса
    try:
        ticker = await exchange.exchange.fetch_ticker("BTC/USDT")
        print(f"✅ BTC/USDT price: {ticker['last']}")
    except Exception as e:
        print(f"❌ Ticker error: {e}")

    # Тест баланса
    try:
        balance = await exchange.exchange.fetch_balance()
        usdt_balance = balance.get("USDT", {}).get("free", 0)
        print(f"✅ Balance: {usdt_balance} USDT")
    except Exception as e:
        print(f"❌ Balance error: {e}")


# Запустить
asyncio.run(test_exchange())
