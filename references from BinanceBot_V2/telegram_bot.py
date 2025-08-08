#!/usr/bin/env python3
"""
Enhanced BinanceBot V2 with full Telegram integration
Includes startup, runtime monitoring, and shutdown notifications
"""

import asyncio
import signal
import sys
import requests
from datetime import datetime
from dotenv import load_dotenv
import os

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


class TelegramNotifier:
    """Telegram notification system for the bot"""

    def __init__(self, config):
        self.config = config
        self.token = config.get_telegram_credentials()[0]
        self.chat_id = config.get_telegram_credentials()[1]
        self.enabled = config.telegram_enabled

    def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """Send message to Telegram"""
        if not self.enabled or not self.token or not self.chat_id:
            return False

        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode
            }
            response = requests.post(url, json=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Telegram send error: {e}")
            return False

    def send_startup_message(self, config_info: dict):
        """Send startup notification"""
        message = f"""
🚀 <b>BinanceBot V2 STARTED</b>

📊 <b>Configuration:</b>
• Target Profit: ${config_info['profit_target_hourly']}/hour
• Max Positions: {config_info['max_positions']}
• Risk Level: {config_info['risk_level']}
• Mode: {config_info['mode']}

⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        return self.send_message(message.strip())

    def send_runtime_status(self, status: dict):
        """Send runtime status update"""
        message = f"""
📈 <b>Bot Status Update</b>

💰 <b>Performance:</b>
• Active Positions: {status.get('active_positions', 0)}
• Total PnL: ${status.get('total_pnl', 0):.2f}
• Win Rate: {status.get('win_rate', 0):.1f}%

⚙️ <b>System:</b>
• Uptime: {status.get('uptime', 'N/A')}
• Last Trade: {status.get('last_trade', 'N/A')}

⏰ Update: {datetime.now().strftime('%H:%M:%S')}
        """
        return self.send_message(message.strip())

    def send_shutdown_message(self, final_stats: dict):
        """Send shutdown notification"""
        message = f"""
🛑 <b>BinanceBot V2 STOPPED</b>

📊 <b>Final Statistics:</b>
• Total Trades: {final_stats.get('total_trades', 0)}
• Total PnL: ${final_stats.get('total_pnl', 0):.2f}
• Win Rate: {final_stats.get('win_rate', 0):.1f}%
• Runtime: {final_stats.get('runtime', 'N/A')}

⏰ Stopped: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        return self.send_message(message.strip())


async def main():
    """Enhanced main function with Telegram integration"""

    print("🚀 Starting Enhanced BinanceBot V2 with Telegram...")

    # Load configuration
    config = TradingConfig.load_optimized_for_profit_target(0.7)
    print(f"✅ Config loaded for ${config.profit_target_hourly}/hour target")

    # Initialize logger
    logger = UnifiedLogger(config)
    logger.log_event("MAIN", "INFO", f"🚀 Enhanced Bot started with ${config.profit_target_hourly}/hour target")

    # Initialize Telegram notifier
    telegram = TelegramNotifier(config)

    # Send startup message
    config_info = {
        'profit_target_hourly': config.profit_target_hourly,
        'max_positions': config.max_concurrent_positions,
        'risk_level': 'HIGH' if config.base_risk_pct > 0.1 else 'MEDIUM' if config.base_risk_pct > 0.05 else 'LOW',
        'mode': 'PRODUCTION' if config.is_production_mode() else 'TESTNET'
    }

    if telegram.send_startup_message(config_info):
        print("✅ Startup message sent to Telegram")
    else:
        print("⚠️ Failed to send startup message to Telegram")

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
        symbol_manager = SymbolManager(exchange, telegram)
        await symbol_manager.update_available_symbols()  # Инициализируем символы

        # Symbol selector
        symbol_selector = SymbolSelector(config, symbol_manager, exchange, logger)
        await symbol_selector.update_selected_symbols()  # Инициализируем выбранные символы

        # Risk manager
        risk_manager = RiskManager(config, logger)

        # Strategy manager
        strategy_manager = StrategyManager(config, exchange, symbol_manager, logger)

        # Order manager
        order_manager = OrderManager(config, exchange, logger)
        await order_manager.initialize()

        logger.log_event("MAIN", "INFO", "✅ Core components initialized")

        # Initialize leverage manager
        from core.leverage_manager import LeverageManager
        leverage_manager = LeverageManager(config, logger)

        # Initialize trading engine
        logger.log_event("MAIN", "INFO", "⚙️ Initializing trading engine...")
        trading_engine = TradingEngine(
            config, exchange, symbol_selector, leverage_manager, risk_manager, logger,
            order_manager=order_manager, strategy_manager=strategy_manager
        )

        logger.log_event("MAIN", "INFO", "✅ Trading engine initialized")

        # Initialize WebSocket manager
        logger.log_event("MAIN", "INFO", "📡 Initializing WebSocket manager...")
        ws_manager = WebSocketManager(exchange, logger=logger)

        logger.log_event("MAIN", "INFO", "✅ WebSocket manager initialized")

        # Send runtime status every 5 minutes
        async def send_periodic_status():
            while True:
                try:
                    # Get current status
                    status = {
                        'active_positions': len(order_manager.active_positions),
                        'total_pnl': 0.0,  # Will be calculated from positions
                        'win_rate': 0.0,   # Will be calculated from history
                        'uptime': 'Running',
                        'last_trade': 'N/A'
                    }

                    # Calculate total PnL from active positions
                    total_pnl = 0.0
                    for symbol, position in order_manager.active_positions.items():
                        if 'unrealized_pnl' in position:
                            total_pnl += position['unrealized_pnl']
                    status['total_pnl'] = total_pnl

                    telegram.send_runtime_status(status)
                    await asyncio.sleep(300)  # 5 minutes
                except Exception as e:
                    logger.log_event("TELEGRAM", "ERROR", f"Status update failed: {e}")
                    await asyncio.sleep(60)

        # Start periodic status updates
        status_task = asyncio.create_task(send_periodic_status())

        # Start trading
        logger.log_event("MAIN", "INFO", "🎯 Starting trading cycle...")

        # Run trading cycle
        await trading_engine.run_trading_cycle()

    except Exception as e:
        logger.log_event("MAIN", "CRITICAL", f"❌ Critical error: {e}")

        # Send error notification
        error_message = f"""
❌ <b>Bot Error</b>

Error: {str(e)}
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        telegram.send_message(error_message.strip())
        raise


async def graceful_shutdown(telegram=None):
    """Graceful shutdown with Telegram notification"""
    print("\n🛑 Graceful shutdown initiated...")

    if telegram:
        final_stats = {
            'total_trades': 0,
            'total_pnl': 0.0,
            'win_rate': 0.0,
            'runtime': 'N/A'
        }
        telegram.send_shutdown_message(final_stats)

    print("✅ Bot shutdown complete")


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print("\n🛑 Shutdown signal received. Stopping bot...")
    # Note: We can't access telegram here easily, so we'll handle it in main
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
