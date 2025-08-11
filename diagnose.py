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
        from core.symbol_utils import normalize_symbol

        symbol = normalize_symbol(f"BTC/{config.resolved_quote_coin}:{config.resolved_quote_coin}")
        ticker = await exchange.exchange.fetch_ticker(symbol)
        print(f"✅ {symbol} price: {ticker['last']}")
    except Exception as e:
        print(f"❌ Ticker error: {e}")

    # Тест баланса
    try:
        from core.balance_utils import free

        balance = await exchange.exchange.fetch_balance()
        quote_balance = free(balance, config.resolved_quote_coin)
        print(f"✅ Balance: {quote_balance} {config.resolved_quote_coin}")
    except Exception as e:
        print(f"❌ Balance error: {e}")


# Запустить
asyncio.run(test_exchange())
