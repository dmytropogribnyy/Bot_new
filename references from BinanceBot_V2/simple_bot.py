#!/usr/bin/env python3
"""
Simplified BinanceBot V2 for production deployment
Focuses on core trading functionality without complex components
"""

import asyncio
import signal
import sys
from datetime import datetime

from core.config import TradingConfig
from core.exchange_client import OptimizedExchangeClient
from core.order_manager import OrderManager
from core.risk_manager import RiskManager
from core.symbol_manager import SymbolManager
from core.trading_engine import TradingEngine
from core.unified_logger import UnifiedLogger
from core.websocket_manager import WebSocketManager
from strategies.symbol_selector import SymbolSelector
from strategies.strategy_manager import StrategyManager


async def main():
    """Simplified main function focusing on core trading"""

    print("🚀 Starting Simplified BinanceBot V2...")

    # Load optimized configuration
    config = TradingConfig.load_optimized_for_profit_target(0.7)
    print(f"✅ Config loaded for ${config.profit_target_hourly}/hour target")

    # Initialize logger
    logger = UnifiedLogger(config)
    logger.log_event("MAIN", "INFO", f"🚀 Simplified Bot started with ${config.profit_target_hourly}/hour target")

    try:
        # Initialize exchange client
        logger.log_event("MAIN", "INFO", "🏦 Initializing exchange client...")
        exchange = OptimizedExchangeClient(config, logger)
        if not await exchange.initialize():
            logger.log_event("MAIN", "CRITICAL", "❌ Failed to initialize exchange client")
            return

        logger.log_event("MAIN", "INFO", "✅ Exchange client initialized")

        # Initialize core components
        logger.log_event("MAIN", "INFO", "🔧 Initializing core components...")

        # Symbol manager
        symbol_manager = SymbolManager(exchange, logger)

        # Symbol selector
        symbol_selector = SymbolSelector(config, symbol_manager, exchange, logger)

        # Risk manager
        risk_manager = RiskManager(config, logger)

        # Strategy manager
        strategy_manager = StrategyManager(config, exchange, symbol_manager, logger)

        # Order manager
        order_manager = OrderManager(config, exchange, logger)
        await order_manager.initialize()

        logger.log_event("MAIN", "INFO", "✅ Core components initialized")

        # Initialize trading engine
        logger.log_event("MAIN", "INFO", "⚙️ Initializing trading engine...")
        trading_engine = TradingEngine(
            config, exchange, symbol_selector, None, risk_manager, logger,
            order_manager=order_manager, strategy_manager=strategy_manager
        )

        logger.log_event("MAIN", "INFO", "✅ Trading engine initialized")

        # Initialize WebSocket manager
        logger.log_event("MAIN", "INFO", "📡 Initializing WebSocket manager...")
        ws_manager = WebSocketManager(exchange, logger=logger)

        logger.log_event("MAIN", "INFO", "✅ WebSocket manager initialized")

        # Start trading
        logger.log_event("MAIN", "INFO", "🎯 Starting trading cycle...")

        # Run trading cycle
        await trading_engine.run_trading_cycle()

    except Exception as e:
        logger.log_event("MAIN", "CRITICAL", f"❌ Critical error: {e}")
        raise


async def graceful_shutdown():
    """Graceful shutdown function"""
    print("\n🛑 Graceful shutdown initiated...")
    # Здесь можно добавить закрытие сессий, сохранение состояния и т.д.
    print("✅ Bot shutdown complete")

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print("\n🛑 Shutdown signal received. Stopping bot...")
    # Запускаем graceful shutdown
    try:
        asyncio.run(graceful_shutdown())
    except:
        pass
    sys.exit(0)


if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run the bot
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Bot crashed: {e}")
        sys.exit(1)
