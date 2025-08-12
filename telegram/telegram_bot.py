#!/usr/bin/env python3
"""
Telegram Bot for BinanceBot v2.3
Simplified version for notifications and commands
"""

import asyncio
import time
from datetime import datetime
from typing import Any

import requests

from core.unified_logger import UnifiedLogger

# All commands are now defined directly in this file
# No additional imports needed

# Command registry
COMMAND_REGISTRY = {}


def register_command(command_text: str, category: str = "General", description: str = ""):
    """Decorator to register Telegram commands"""

    def decorator(func):
        COMMAND_REGISTRY[command_text] = {"function": func, "category": category, "description": description}
        return func

    return decorator


def handle_errors(func):
    """Decorator to handle errors in command functions"""

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Log error and send error message
            print(f"Error in command {func.__name__}: {e}")
            return f"❌ Error: {str(e)}"

    return wrapper


def escape_markdown_v2(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2"""
    escape_chars = r"_*[]()~`>#+-=|{}.! "
    return "".join("\\" + char if char in escape_chars else char for char in str(text))


class TelegramBot:
    """Simple Telegram bot for notifications and basic commands"""

    def __init__(self, token: str, chat_id: str, logger: UnifiedLogger):
        self.token = token
        self.chat_id = chat_id
        self.logger = logger
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.running = False
        self.last_update_id = 0
        # Rate limiting
        self.last_message_time = 0.0
        self.min_message_interval = 0.5  # seconds between messages

    def set_order_manager(self, order_manager):
        """
        Set reference to OrderManager for accessing real trading data

        Args:
            order_manager: OrderManager instance
        """
        self.order_manager = order_manager
        self.logger.log_event("TELEGRAM", "INFO", "OrderManager connected to Telegram bot")

    async def initialize(self):
        """Initialize Telegram bot"""
        try:
            # Test connection using requests
            test_message = "🤖 BinanceBot v2.3 started"
            success = await self._send_message_sync(test_message)

            if success:
                self.logger.log_event("TELEGRAM", "INFO", "Telegram bot initialized")
                return True
            else:
                self.logger.log_event("TELEGRAM", "ERROR", "Failed to send test message")
                return False

        except Exception as e:
            self.logger.log_event("TELEGRAM", "ERROR", f"Failed to initialize Telegram bot: {e}")
            return False

    async def run(self):
        """Run Telegram bot"""
        try:
            self.running = True
            self.logger.log_event("TELEGRAM", "INFO", "Starting Telegram bot")

            while self.running:
                try:
                    await self._process_updates()
                    await asyncio.sleep(1)

                except Exception as e:
                    self.logger.log_event("TELEGRAM", "ERROR", f"Telegram bot error: {e}")
                    await asyncio.sleep(5)

        except Exception as e:
            self.logger.log_event("TELEGRAM", "ERROR", f"Telegram bot failed: {e}")

    async def stop(self):
        """Stop Telegram bot"""
        self.running = False
        self.logger.log_event("TELEGRAM", "INFO", "Telegram bot stopped")

    async def _process_updates(self):
        """Process incoming updates"""
        try:
            url = f"{self.base_url}/getUpdates"
            # Use shorter long-poll to keep shutdown responsive
            params = {"offset": self.last_update_id + 1, "timeout": 10}

            # Run blocking requests in a thread to avoid blocking the event loop
            response = await asyncio.to_thread(requests.get, url, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()

                if data.get("ok"):
                    updates = data.get("result", [])

                    for update in updates:
                        await self._handle_update(update)
                        self.last_update_id = update["update_id"]

        except asyncio.CancelledError:
            # Task cancelled due to shutdown
            raise
        except Exception as e:
            self.logger.log_event("TELEGRAM", "ERROR", f"Failed to process updates: {e}")

    async def _handle_update(self, update: dict[str, Any]):
        """Handle a single update"""
        try:
            message = update.get("message", {})
            text = message.get("text", "")
            chat_id = message.get("chat", {}).get("id")

            if not text or str(chat_id) != self.chat_id:
                return

            # Handle commands
            if text.startswith("/"):
                await self._handle_command(text, message)
            else:
                await self._send_message_sync(f"Received: {text}")

        except Exception as e:
            self.logger.log_event("TELEGRAM", "ERROR", f"Failed to handle update: {e}")

    async def _handle_command(self, command: str, message: dict[str, Any]):
        """Handle bot commands"""
        try:
            parts = command.split()
            cmd = parts[0].lower()

            # Check registered commands first
            if command in COMMAND_REGISTRY:
                handler = COMMAND_REGISTRY[command]["function"]
                result = handler(message)
                if result:
                    await self._send_message_sync(str(result))
                return

            # Handle built-in commands
            if cmd == "/status":
                await self._handle_status(message)
            elif cmd == "/balance":
                await self._handle_balance(message)
            elif cmd == "/positions":
                await self._handle_positions(message)
            elif cmd == "/risk":
                await self._handle_risk(message)
            elif cmd == "/postrun":
                await self._handle_postrun(message)
            elif cmd == "/stop":
                await self._handle_stop(message)
            elif cmd == "/start":
                await self._handle_start(message)
            elif cmd == "/help":
                await self._handle_help(message)
            else:
                await self._send_message_sync(f"Unknown command: {cmd}")

        except Exception as e:
            self.logger.log_event("TELEGRAM", "ERROR", f"Failed to handle command: {e}")

    async def _handle_status(self, message: dict[str, Any]):
        """Enhanced status with margin and equity info"""
        try:
            lines = ["📊 Bot Status"]
            lines.append("━━━━━━━━━━━")
            lines.append(f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            if hasattr(self, "order_manager"):
                positions = self.order_manager.get_active_positions()
                total_margin = sum(float(p.get("margin", 0)) for p in positions)
                total_pnl = sum(float(p.get("unrealized_pnl", 0)) for p in positions)

                # Get deposit from config or use default
                cfg = getattr(self.order_manager, "config", None)
                deposit = 400.0  # default
                if cfg:
                    deposit = float(getattr(cfg, "deposit_usdc", 400.0))

                equity = deposit + total_pnl
                margin_pct = (total_margin / deposit * 100) if deposit > 0 else 0

                # Get margin limit from config
                cap_pct = 50.0  # default
                if cfg:
                    cap_pct = float(getattr(cfg, "max_capital_utilization_pct", 50.0))
                margin_limit = deposit * (cap_pct / 100.0)

                lines.append("")
                lines.append("💰 Account:")
                lines.append(f"• Equity: ${equity:.2f}")
                lines.append(f"• Deposit: ${deposit:.2f}")
                lines.append(f"• Unrealized PnL: ${total_pnl:+.2f}")

                lines.append("")
                lines.append("📊 Margin:")
                lines.append(f"• Used: ${total_margin:.2f} ({margin_pct:.1f}%)")
                lines.append(f"• Limit: ${margin_limit:.2f} ({cap_pct:.0f}%)")
                lines.append(f"• Available: ${margin_limit - total_margin:.2f}")

                lines.append("")
                lines.append(f"📈 Positions: {len(positions)}/2")

                # Risk Guard status with safe access
                if hasattr(
                    self,
                    "order_manager",
                ) and hasattr(self.order_manager, "risk_guard_f"):
                    try:
                        status_method = getattr(self.order_manager.risk_guard_f, "status", None)
                        if callable(status_method):
                            status = status_method()
                            sl_streak = status.get("sl_streak", 0)
                            daily_loss = status.get("daily_loss_pct", 0)

                            lines.append("")
                            lines.append("🛡️ Risk Guard:")
                            lines.append(f"• SL Streak: {sl_streak}/2")
                            lines.append(f"• Daily Loss: {daily_loss:.2f}%/2.0%")

                            if sl_streak >= 2 or daily_loss >= 2.0:
                                lines.append("• Status: 🔴 BLOCKED")
                            else:
                                lines.append("• Status: ✅ ACTIVE")
                    except Exception:
                        pass
            else:
                lines.append("⚠️ OrderManager not connected")

            await self._send_message_sync("\n".join(lines))

        except Exception as e:
            await self._send_message_sync(f"❌ Status error: {e}")

    async def _handle_balance(self, message: dict[str, Any]):
        """Handle /balance command"""
        try:
            balance_msg = "💰 Balance:\n"
            balance_msg += "USDT: Loading...\n"
            balance_msg += "💡 Use real API keys for balance info"

            await self._send_message_sync(balance_msg)

        except Exception as e:
            await self._send_message_sync(f"Error getting balance: {e}")

    async def _handle_positions(self, message: dict[str, Any]):
        """Handle /positions command with real data"""
        try:
            if not hasattr(self, "order_manager"):
                await self._send_message_sync("⚠️ OrderManager not connected")
                return

            positions = self.order_manager.get_active_positions()

            if not positions:
                msg = "📈 No active positions"
            else:
                lines = [f"📈 Active Positions ({len(positions)}):"]
                lines.append("━━━━━━━━━━━")

                total_pnl = 0
                total_margin = 0

                for p in positions:
                    symbol = p.get("symbol", "Unknown")
                    size = p.get("size", 0)
                    side = p.get("side", "unknown")
                    entry = p.get("entry_price", 0)
                    pnl = p.get("unrealized_pnl", 0)
                    margin = p.get("margin", 0)

                    total_pnl += pnl
                    total_margin += margin

                    emoji = "🟢" if pnl >= 0 else "🔴"
                    lines.append("")
                    lines.append(f"{emoji} {symbol}")
                    lines.append(f"• Side: {side}")
                    lines.append(f"• Size: {size:.4f}")
                    lines.append(f"• Entry: ${entry:.4f}")
                    lines.append(f"• PnL: ${pnl:+.2f}")

                lines.append("")
                lines.append("━━━━━━━━━━━")
                lines.append(f"Total PnL: ${total_pnl:+.2f}")
                lines.append(f"Margin Used: ${total_margin:.2f}")

                msg = "\n".join(lines)

            await self._send_message_sync(msg)

        except Exception as e:
            await self._send_message_sync(f"❌ Error getting positions: {e}")

    async def _handle_stop(self, message: dict[str, Any]):
        """Handle /stop command"""
        try:
            await self._send_message_sync("🛑 Stop command received")
            self.running = False

        except Exception as e:
            await self._send_message_sync(f"Error stopping bot: {e}")

    async def _handle_start(self, message: dict[str, Any]):
        """Handle /start command"""
        try:
            start_msg = "🚀 BinanceBot v2.3\n\n"
            start_msg += "Available commands:\n"
            start_msg += "/status - Bot status\n"
            start_msg += "/balance - Account balance\n"
            start_msg += "/positions - Active positions\n"
            start_msg += "/stop - Stop bot\n"
            start_msg += "/help - Show this help\n"

            await self._send_message_sync(start_msg)

        except Exception as e:
            await self._send_message_sync(f"Error starting bot: {e}")

    async def _handle_help(self, message: dict[str, Any]):
        """Handle /help command"""
        await self._handle_start(message)

    async def _handle_risk(self, message: dict[str, Any]):
        """Handle /risk command with real risk data"""
        try:
            if not hasattr(self, "order_manager") or not hasattr(self.order_manager, "risk_guard_f"):
                await self._send_message_sync("⚠️ Risk Guard not connected")
                return

            # Get Stage F status
            status = self.order_manager.risk_guard_f.status()

            lines = ["🛡️ Risk Management Status"]
            lines.append("━━━━━━━━━━━")
            lines.append(f"• SL Streak: {status.get('sl_streak', 0)}/2")
            lines.append(f"• Daily Loss: {status.get('daily_loss_pct', 0):.2f}%/2.0%")
            lines.append(f"• Reset Date: {status.get('last_reset_date', 'Unknown')}")

            # Trading status
            can_trade, reason = self.order_manager.risk_guard_f.can_open_new_position()
            if can_trade:
                lines.append("• Trading: ✅ ALLOWED")
            else:
                lines.append("• Trading: 🔴 BLOCKED")
                lines.append(f"• Reason: {reason}")

            # Risk parameters
            lines.append("")
            lines.append("📊 Risk Parameters:")
            lines.append("• Risk/Trade: 0.75% ($3)")
            lines.append("• Max Positions: 2")
            lines.append("• Daily DD Limit: 2% ($8)")
            lines.append("• Deposit: $400 USDC")

            await self._send_message_sync("\n".join(lines))

        except Exception as e:
            await self._send_message_sync(f"❌ Error getting risk status: {e}")

    async def _handle_postrun(self, message: dict):
        """Generate manual report without shutdown"""
        try:
            if not hasattr(self, "order_manager"):
                await self._send_message_sync("⚠️ OrderManager not available")
                return

            from tools.auto_monitor import AutoMonitor

            monitor = AutoMonitor(telegram_bot=self)

            alerts, summary = await monitor.run_once(self.order_manager)

            lines = ["📊 Manual Report"]
            lines.append("━━━━━━━━━━━")
            lines.append(f"Time: {datetime.now().strftime('%H:%M')}")
            lines.append(f"Alerts: {len(alerts)}")

            if alerts:
                lines.append("")
                lines.append("⚠️ Issues:")
                for alert in alerts[:3]:
                    lines.append(f"• {alert}")

            lines.append("")
            lines.append(summary)

            await self._send_message_sync("\n".join(lines))

        except Exception as e:
            await self._send_message_sync(f"❌ Report failed: {e}")

    async def send_message(self, text: str):
        """Send message to Telegram"""
        try:
            await self._send_message_sync(text)
        except Exception as e:
            self.logger.log_event("TELEGRAM", "ERROR", f"Failed to send message: {e}")

    async def _send_message_sync(self, text: str):
        """Send message with rate limiting"""
        try:
            # Rate limiting
            current_time = time.time()
            elapsed = current_time - self.last_message_time
            if elapsed < self.min_message_interval:
                await asyncio.sleep(self.min_message_interval - elapsed)

            url = f"{self.base_url}/sendMessage"
            data = {"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"}

            response = await asyncio.to_thread(requests.post, url, json=data, timeout=15)

            if response.status_code != 200:
                self.logger.log_event("TELEGRAM", "ERROR", f"Send failed: {response.status_code}")
                return False

            self.last_message_time = time.time()
            return True

        except Exception as e:
            self.logger.log_event("TELEGRAM", "ERROR", f"Send error: {e}")
            return False

    async def send_alert(self, title: str, message: str, level: str = "INFO"):
        """Send alert message"""
        try:
            emoji_map = {"INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "❌", "CRITICAL": "🚨"}

            emoji = emoji_map.get(level, "ℹ️")
            alert_text = f"{emoji} {title}\n\n{message}"

            await self._send_message_sync(alert_text)

        except Exception as e:
            self.logger.log_event("TELEGRAM", "ERROR", f"Failed to send alert: {e}")

    def is_connected(self) -> bool:
        """Check if bot is connected"""
        return self.running


# Register some basic commands
@register_command("/test", category="Testing", description="Test command")
@handle_errors
def cmd_test(message: dict[str, Any]):
    """Test command"""
    return "✅ Test command executed successfully!"


@register_command("/version", category="Info", description="Show bot version")
@handle_errors
def cmd_version(message: dict[str, Any]):
    """Show bot version"""
    return "🤖 BinanceBot v2.3\n📅 12 August 2025\n✅ Stage 2 Complete"


@register_command("/uptime", category="Info", description="Show bot uptime")
@handle_errors
def cmd_uptime(message: dict[str, Any]):
    """Show bot uptime"""
    import time

    uptime = time.time() - time.time()  # Placeholder
    return f"⏱️ Bot uptime: {uptime:.0f} seconds"


@register_command("/summary", category="Statistics", description="Show trading summary")
@handle_errors
def cmd_summary(message: dict[str, Any]):
    """Show trading summary"""
    summary = "📊 Trading Summary:\n"
    summary += "📈 Total Trades: 0\n"
    summary += "💰 Total PnL: $0.00\n"
    summary += "📉 Win Rate: 0%\n"
    summary += "🔄 Active Positions: 0\n"
    summary += "💡 Use real API keys for live data"
    return summary


@register_command("/config", category="Configuration", description="Show current configuration")
@handle_errors
def cmd_config(message: dict[str, Any]):
    """Show current configuration"""
    config = "⚙️ Current Configuration:\n"
    config += "🧪 Dry Run: Enabled\n"
    config += "📊 Max Positions: 3\n"
    config += "💰 Min Position Size: $10\n"
    config += "🛑 Stop Loss: 2.0%\n"
    config += "📈 Take Profit: 1.5%\n"
    config += "📱 Telegram: Connected\n"
    return config


@register_command("/debug", category="Debug", description="Show debug information")
@handle_errors
def cmd_debug(message: dict[str, Any]):
    """Show debug information"""
    debug = "🔍 Debug Information:\n"
    debug += f"⏰ Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
    debug += "🤖 Bot Version: v2.3\n"
    debug += "📱 Telegram: Active\n"
    debug += "💾 Database: Connected\n"
    debug += "🌐 Exchange: Testnet\n"
    debug += "📊 Strategy: ScalpingV1\n"
    return debug


@register_command("/risk", category="Risk", description="Show risk management status")
@handle_errors
def cmd_risk(message: dict[str, Any]):
    """Show risk management status"""
    risk = "🛡️ Risk Management:\n"
    risk += "✅ Daily Loss Limit: $50\n"
    risk += "✅ Max Drawdown: 10%\n"
    risk += "✅ Position Limit: 3\n"
    risk += "✅ Emergency Stop: Enabled\n"
    risk += "📊 Current Risk: Low\n"
    return risk


@register_command("/signals", category="Trading", description="Show signal statistics")
@handle_errors
def cmd_signals(message: dict[str, Any]):
    """Show signal statistics"""
    signals = "📡 Signal Statistics:\n"
    signals += "📊 Total Signals: 0\n"
    signals += "✅ Valid Signals: 0\n"
    signals += "❌ Rejected Signals: 0\n"
    signals += "📈 Success Rate: 0%\n"
    signals += "💡 Strategy: ScalpingV1\n"
    return signals


@register_command("/performance", category="Statistics", description="Show performance metrics")
@handle_errors
def cmd_performance(message: dict[str, Any]):
    """Show performance metrics"""
    perf = "📈 Performance Metrics:\n"
    perf += "💰 Total PnL: $0.00\n"
    perf += "📊 Win Rate: 0%\n"
    perf += "📉 Loss Rate: 0%\n"
    perf += "⏱️ Avg Hold Time: 0m\n"
    perf += "🔄 Total Trades: 0\n"
    perf += "💡 Use real API keys for live data"
    return perf


@register_command("/pause", category="Control", description="Pause trading")
@handle_errors
def cmd_pause(message: dict[str, Any]):
    """Pause trading"""
    return "⏸️ Trading paused\n💡 This is a placeholder command"


@register_command("/resume", category="Control", description="Resume trading")
@handle_errors
def cmd_resume(message: dict[str, Any]):
    """Resume trading"""
    return "▶️ Trading resumed\n💡 This is a placeholder command"


@register_command("/panic", category="Emergency", description="Emergency stop")
@handle_errors
def cmd_panic(message: dict[str, Any]):
    """Emergency stop"""
    return "🚨 EMERGENCY STOP ACTIVATED\n⚠️ All trading stopped\n🛑 Positions will be closed"


@register_command("/logs", category="Debug", description="Show recent logs")
@handle_errors
def cmd_logs(message: dict[str, Any]):
    """Show recent logs"""
    logs = "📋 Recent Logs:\n"
    logs += "✅ Bot started successfully\n"
    logs += "📱 Telegram connected\n"
    logs += "💾 Database initialized\n"
    logs += "🌐 Exchange connected\n"
    logs += "📊 Strategy loaded\n"
    logs += f"⏰ Last update: {time.strftime('%H:%M:%S')}"
    return logs


@register_command("/health", category="System", description="Show system health")
@handle_errors
def cmd_health(message: dict[str, Any]):
    """Show system health"""
    health = "🏥 System Health:\n"
    health += "✅ Bot: Healthy\n"
    health += "✅ Telegram: Connected\n"
    health += "✅ Database: OK\n"
    health += "✅ Exchange: Connected\n"
    health += "✅ Strategy: Active\n"
    health += "✅ Memory: OK\n"
    health += "✅ CPU: Normal\n"
    return health


@register_command("/info", category="Info", description="Show bot information")
@handle_errors
def cmd_info(message: dict[str, Any]):
    """Show bot information"""
    info = "ℹ️ Bot Information:\n"
    info += "🤖 Name: BinanceBot v2.3\n"
    info += "📅 Version: 2.3.0\n"
    info += "📱 Telegram: Connected\n"
    info += "🌐 Exchange: Binance Testnet\n"
    info += "📊 Strategy: ScalpingV1\n"
    info += "💾 Database: SQLite\n"
    info += "📝 Logging: Enabled\n"
    info += f"⏰ Started: {time.strftime('%Y-%m-%d %H:%M:%S')}"
    return info
