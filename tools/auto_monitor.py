#!/usr/bin/env python3
"""
Auto-monitor for Binance Futures Bot
Checks bot health, sends alerts to Telegram, generates reports
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path


class AutoMonitor:
    def __init__(self, telegram_bot=None, check_interval_hours: float = 6):
        """
        Initialize auto monitor

        Args:
            telegram_bot: Optional TelegramBot instance for notifications
            check_interval_hours: Hours between checks
        """
        self.check_interval = check_interval_hours * 3600
        self.telegram_bot = telegram_bot
        self.alert_thresholds = {
            "daily_loss_pct": 1.5,  # Alert at -1.5% daily loss
            "sl_streak": 2,  # Alert at 2 consecutive stop losses
            "positions_stuck_min": 60,  # Alert if position open > 60 minutes
            "error_count": 5,  # Alert if > 5 errors in logs
        }

    async def check_stage_f(self) -> list[str]:
        """Check Stage F risk guard state"""
        alerts: list[str] = []
        stage_f_path = Path("data/runtime/stage_f_state.json")

        if stage_f_path.exists():
            try:
                with open(stage_f_path) as f:
                    state = json.load(f)

                sl_streak = state.get("sl_streak", 0)
                daily_loss = state.get("daily_loss_pct", 0.0)

                # Check thresholds
                if sl_streak >= self.alert_thresholds["sl_streak"]:
                    alerts.append(f"⚠️ SL Streak: {sl_streak} (limit: {self.alert_thresholds['sl_streak']})")

                if daily_loss >= self.alert_thresholds["daily_loss_pct"]:
                    alerts.append(
                        f"🔴 Daily Loss: {daily_loss:.2f}% (limit: {self.alert_thresholds['daily_loss_pct']}%)"
                    )

            except Exception as e:
                alerts.append(f"❌ Failed to read Stage F state: {e}")

        return alerts

    async def check_logs(self) -> list[str]:
        """Check multiple log sources for errors"""
        alerts: list[str] = []
        today = datetime.now().strftime("%Y%m%d")

        log_candidates = [
            Path(f"logs/bot_{today}.log"),
            Path("logs/main.log"),
        ]

        all_lines: list[str] = []
        for log_path in log_candidates:
            if log_path.exists():
                try:
                    with open(log_path, encoding="utf-8") as f:
                        all_lines.extend(f.readlines()[-100:])
                except Exception:
                    pass

        if all_lines:
            errors = [l for l in all_lines if "ERROR" in l or "CRITICAL" in l]
            if len(errors) > self.alert_thresholds.get("error_count", 5):
                alerts.append(f"❌ Errors detected: {len(errors)} in recent logs")
                if errors:
                    last_error = errors[-1].strip()[:160]
                    alerts.append(f"Last: {last_error}...")

        return alerts

    async def check_positions(self, order_manager: object | None = None) -> list[str]:
        """Check positions for stuck or problematic trades"""
        alerts: list[str] = []

        if not order_manager:
            return alerts

        try:
            positions = order_manager.get_active_positions()

            for pos in positions:
                # Check position age
                pos_age_min = (datetime.now().timestamp() - pos.get("timestamp", 0)) / 60

                if pos_age_min > self.alert_thresholds["positions_stuck_min"]:
                    symbol = pos.get("symbol", "Unknown")
                    pnl = pos.get("unrealized_pnl", 0)
                    alerts.append(f"⏰ Stuck position: {symbol} open for {pos_age_min:.0f} min, PnL: ${pnl:.2f}")

        except Exception as e:
            alerts.append(f"❌ Failed to check positions: {e}")

        return alerts

    async def generate_summary(self, order_manager: object | None = None) -> str:
        """Generate comprehensive trading summary"""
        lines = ["📊 Trading Summary", f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}", "━━━━━━━━━━━━━━━━"]

        # Stage F status
        stage_f_path = Path("data/runtime/stage_f_state.json")
        if stage_f_path.exists():
            try:
                with open(stage_f_path) as f:
                    state = json.load(f)
                lines.append("")
                lines.append("🛡️ Risk Status:")
                lines.append(f"• SL Streak: {state.get('sl_streak', 0)}")
                lines.append(f"• Daily Loss: {state.get('daily_loss_pct', 0):.2f}%")
                lines.append("• Status: 🔴 BLOCKED" if state.get("sl_streak", 0) >= 2 else "• Status: ✅ ACTIVE")
            except Exception:
                logging.exception("Failed to read Stage F state", exc_info=True)

        # Position summary
        if order_manager:
            try:
                positions = order_manager.get_active_positions()
                lines.append("")
                lines.append("📈 Positions:")
                lines.append(f"• Active: {len(positions)}")

                if positions:
                    total_pnl = sum(p.get("unrealized_pnl", 0) for p in positions)
                    total_margin = sum(p.get("margin", 0) for p in positions)
                    lines.append(f"• Total PnL: ${total_pnl:.2f}")
                    lines.append(f"• Margin Used: ${total_margin:.2f}")

                    # List positions
                    for p in positions[:3]:  # Max 3 positions in summary
                        symbol = p.get("symbol", "Unknown")
                        pnl = p.get("unrealized_pnl", 0)
                        lines.append(f"  {symbol}: ${pnl:+.2f}")
            except Exception:
                logging.exception("Failed to summarize positions", exc_info=True)

        return "\n".join(lines)

    async def send_report(self, alerts: list[str], summary: str = ""):
        """Send report to file and Telegram"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Always save to file
        report_file = Path("logs/monitor_report.txt")
        try:
            with open(report_file, "a") as f:
                f.write(f"\n{'=' * 50}\n")
                f.write(f"Monitor Report - {timestamp}\n")
                f.write(f"{'=' * 50}\n")

                if alerts:
                    f.write("ALERTS:\n")
                    for alert in alerts:
                        f.write(f"  {alert}\n")
                else:
                    f.write("✅ No alerts\n")

                if summary:
                    f.write("\nSUMMARY:\n")
                    f.write(summary + "\n")

        except Exception as e:
            print(f"Failed to write report file: {e}")

        # Send to Telegram if available
        if self.telegram_bot and (alerts or summary):
            try:
                message_parts = []

                if alerts:
                    message_parts.append("🚨 ALERTS:")
                    message_parts.extend(alerts)

                if summary:
                    if alerts:
                        message_parts.append("")  # Empty line
                    message_parts.append(summary)

                full_message = "\n".join(message_parts)
                await self.telegram_bot.send_message(full_message)

            except Exception as e:
                print(f"Failed to send Telegram report: {e}")

    async def run_once(self, order_manager=None) -> tuple[list[str], str]:
        """
        Single-cycle monitor for post-run or manual (/postrun).
        Returns: (alerts, summary_text)
        """
        alerts: list[str] = []

        # Collect all checks
        alerts.extend(await self.check_stage_f())
        alerts.extend(await self.check_logs())

        if order_manager:
            alerts.extend(await self.check_positions(order_manager))

        # Generate summary
        summary = await self.generate_summary(order_manager)

        # Send report
        await self.send_report(alerts, summary)

        return alerts, summary

    async def run(self, order_manager=None):
        """Run continuous monitoring loop"""
        print(f"🤖 Auto Monitor started (checks every {self.check_interval / 3600:.1f} hours)")

        while True:
            try:
                await self.run_once(order_manager)

                # Console output
                print(f"✅ Monitor check completed at {datetime.now().strftime('%H:%M:%S')}")

            except Exception:
                logging.exception("Monitor error", exc_info=True)

            # Wait for next check
            await asyncio.sleep(self.check_interval)


# Standalone execution support
if __name__ == "__main__":
    monitor = AutoMonitor(check_interval_hours=1)  # Check every hour for testing
    asyncio.run(monitor.run())
