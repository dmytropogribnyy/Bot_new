#!/usr/bin/env python3
"""
Unified Logger for BinanceBot v2.1
Simplified version based on v2 structure
"""

import asyncio
import json
import logging
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from core.config import TradingConfig


class LogLevel:
    """Log levels for different channels"""

    TERMINAL = "TERMINAL"  # Console - important events only
    FILE = "FILE"  # File - detailed information
    DATABASE = "DATABASE"  # SQLite - key events only
    TELEGRAM = "TELEGRAM"  # Telegram - alerts and important notifications


class UnifiedLogger:
    def __init__(self, config: TradingConfig):
        self.config = config
        self.db_path = Path(config.db_path)
        self.lock = threading.Lock()
        self.telegram = None

        # Logging settings from config
        self.max_log_size_mb = config.max_log_size_mb
        self.log_retention_days = config.log_retention_days
        self.log_level = config.log_level.upper()

        # Rate limiting to prevent spam
        self.log_rate_limit = {}  # {component: last_log_time}
        self.min_log_interval = 60  # Minimum interval between logs in seconds

        # Verbosity settings
        self.verbosity_settings = {
            "CLEAN": {
                "terminal_interval": 300,  # 5 minutes
                "telegram_interval": 600,  # 10 minutes
                "show_ws_updates": False,
                "show_ping_pong": False,
            },
            "VERBOSE": {
                "terminal_interval": 60,  # 1 minute
                "telegram_interval": 300,  # 5 minutes
                "show_ws_updates": True,
                "show_ping_pong": False,
            },
            "DEBUG": {
                "terminal_interval": 10,  # 10 seconds
                "telegram_interval": 60,  # 1 minute
                "show_ws_updates": True,
                "show_ping_pong": True,
            },
        }

        self.current_verbosity = self.verbosity_settings.get(self.log_level, self.verbosity_settings["CLEAN"])

        # Create directories if they don't exist
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        Path("logs").mkdir(exist_ok=True)

        # Setup logging
        self._setup_file_logging()
        self._init_db()
        self._setup_console_logging()
        self._cleanup_old_logs()

    def _setup_file_logging(self):
        """Setup file logging with improved structure"""
        self.file_logger = logging.getLogger("binance_bot")
        self.file_logger.setLevel(logging.INFO)

        # Create formatter with improved structure
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)-15s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )

        # File handler with rotation
        file_handler = logging.FileHandler("logs/main.log", encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)

        self.file_logger.addHandler(file_handler)
        self.file_logger.propagate = False

    def _setup_console_logging(self):
        """Setup console logging"""
        self.console_logger = logging.getLogger("binance_bot_console")
        self.console_logger.setLevel(logging.INFO)

        formatter = logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S")

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)

        self.console_logger.addHandler(console_handler)
        self.console_logger.propagate = False

    def _init_db(self):
        """Initialize SQLite database for logging"""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Create logs table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        level TEXT NOT NULL,
                        component TEXT NOT NULL,
                        message TEXT NOT NULL,
                        details TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Create trades table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS trades (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        side TEXT NOT NULL,
                        quantity REAL NOT NULL,
                        price REAL NOT NULL,
                        pnl REAL DEFAULT 0,
                        win BOOLEAN DEFAULT FALSE,
                        reason TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Create runtime_status table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS runtime_status (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        status TEXT NOT NULL,
                        details TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                conn.commit()

        except Exception as e:
            print(f"Failed to initialize database: {e}")

    def _cleanup_old_logs(self):
        """Clean up old log files"""
        try:
            log_dir = Path("logs")
            if not log_dir.exists():
                return

            cutoff_date = datetime.now() - timedelta(days=self.log_retention_days)

            for log_file in log_dir.glob("*.log"):
                if log_file.stat().st_mtime < cutoff_date.timestamp():
                    log_file.unlink()

        except Exception as e:
            print(f"Failed to cleanup old logs: {e}")

    def _rotate_logs(self):
        """Rotate log files if they exceed size limit"""
        try:
            log_file = Path("logs/main.log")
            if log_file.exists() and log_file.stat().st_size > self.max_log_size_mb * 1024 * 1024:
                # Create backup
                backup_name = f"logs/main_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
                log_file.rename(backup_name)

                # Create new log file
                log_file.touch()

        except Exception as e:
            print(f"Failed to rotate logs: {e}")

    def _should_log(self, component: str, level: str) -> bool:
        """Check if we should log this message based on rate limiting"""
        current_time = datetime.now()

        # Check rate limiting
        if component in self.log_rate_limit:
            last_time = self.log_rate_limit[component]
            if (current_time - last_time).total_seconds() < self.min_log_interval:
                return False

        self.log_rate_limit[component] = current_time
        return True

    def log_event(self, component: str, level: str, message: str, details: Any = None, channels: list = None):
        """Log an event to specified channels"""
        if not self._should_log(component, level):
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Default channels
        if channels is None:
            channels = ["terminal", "file"]
            if level in ["ERROR", "CRITICAL"]:
                channels.append("telegram")
            if level in ["INFO", "WARNING", "ERROR", "CRITICAL"]:
                channels.append("database")

        # Format message
        formatted_message = f"[{component}] {message}"
        if details:
            if isinstance(details, dict):
                details_str = json.dumps(details, indent=2)
            else:
                details_str = str(details)
            formatted_message += f"\nDetails: {details_str}"

        # Log to different channels
        if "terminal" in channels and self.config.log_to_console:
            self._log_to_console(level, formatted_message)

        if "file" in channels and self.config.log_to_file:
            self._log_to_file(level, formatted_message)

        if "database" in channels:
            self._log_to_database(timestamp, level, component, message, details)

        if "telegram" in channels and self.config.log_to_telegram and self.telegram:
            self._log_to_telegram(level, formatted_message)

    def _log_to_console(self, level: str, message: str):
        """Log to console"""
        try:
            if level == "DEBUG":
                self.console_logger.debug(message)
            elif level == "INFO":
                self.console_logger.info(message)
            elif level == "WARNING":
                self.console_logger.warning(message)
            elif level == "ERROR":
                self.console_logger.error(message)
            elif level == "CRITICAL":
                self.console_logger.critical(message)
        except Exception as e:
            print(f"Console logging error: {e}")

    def _log_to_file(self, level: str, message: str):
        """Log to file"""
        try:
            if level == "DEBUG":
                self.file_logger.debug(message)
            elif level == "INFO":
                self.file_logger.info(message)
            elif level == "WARNING":
                self.file_logger.warning(message)
            elif level == "ERROR":
                self.file_logger.error(message)
            elif level == "CRITICAL":
                self.file_logger.critical(message)
        except Exception as e:
            print(f"File logging error: {e}")

    def _log_to_database(self, timestamp: str, level: str, component: str, message: str, details: Any = None):
        """Log to SQLite database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO logs (timestamp, level, component, message, details)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (timestamp, level, component, message, json.dumps(details) if details else None),
                )
                conn.commit()
        except Exception as e:
            print(f"Database logging error: {e}")

    def _log_to_telegram(self, level: str, message: str):
        """Log to Telegram"""
        if self.telegram:
            try:
                # Truncate long messages
                if len(message) > 4000:
                    message = message[:4000] + "..."

                asyncio.create_task(self.telegram.send_message(message))
            except Exception as e:
                print(f"Telegram logging error: {e}")

    def log_trade(
        self, symbol: str, side: str, qty: float, price: float, reason: str, pnl: float = 0, win: bool = False
    ):
        """Log a trade event"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO trades (symbol, side, quantity, price, pnl, win, reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (symbol, side, qty, price, pnl, win, reason),
                )
                conn.commit()

            # Also log as event
            self.log_event(
                "TRADE",
                "INFO",
                f"Trade: {symbol} {side} {qty} @ {price} | PnL: {pnl} | Win: {win}",
                {"reason": reason, "pnl": pnl, "win": win},
            )

        except Exception as e:
            print(f"Trade logging error: {e}")

    def log_runtime_status(self, status: str, details: dict[str, Any] = None):
        """Log runtime status"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO runtime_status (status, details)
                    VALUES (?, ?)
                """,
                    (status, json.dumps(details) if details else None),
                )
                conn.commit()

            self.log_event("RUNTIME", "INFO", f"Status: {status}", details)

        except Exception as e:
            print(f"Runtime status logging error: {e}")

    def attach_telegram(self, telegram_bot):
        """Attach Telegram bot for logging"""
        self.telegram = telegram_bot

    def get_recent_logs(self, hours: int = 24) -> list:
        """Get recent logs from database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(f"""
                    SELECT timestamp, level, component, message, details
                    FROM logs
                    WHERE timestamp >= datetime('now', '-{hours} hours')
                    ORDER BY timestamp DESC
                    LIMIT 100
                """)

                return cursor.fetchall()
        except Exception as e:
            print(f"Failed to get recent logs: {e}")
            return []

    def get_trade_summary(self, hours: int = 24) -> dict[str, Any]:
        """Get trade summary from database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Get total trades
                cursor.execute(f"""
                    SELECT COUNT(*), SUM(CASE WHEN win THEN 1 ELSE 0 END), SUM(pnl)
                    FROM trades
                    WHERE timestamp >= datetime('now', '-{hours} hours')
                """)

                total, wins, total_pnl = cursor.fetchone()

                if total is None:
                    return {"total": 0, "wins": 0, "win_rate": 0, "total_pnl": 0}

                win_rate = (wins / total * 100) if total > 0 else 0

                return {
                    "total": total,
                    "wins": wins,
                    "win_rate": round(win_rate, 2),
                    "total_pnl": round(total_pnl or 0, 2),
                }

        except Exception as e:
            print(f"Failed to get trade summary: {e}")
            return {"total": 0, "wins": 0, "win_rate": 0, "total_pnl": 0}

    def send_alert(self, message: str, level: str = "INFO", details: Any = None):
        """Send alert to Telegram"""
        if self.telegram and self.config.log_to_telegram:
            try:
                alert_message = f"🚨 ALERT [{level}]: {message}"
                if details:
                    alert_message += f"\nDetails: {json.dumps(details, indent=2)}"

                asyncio.create_task(self.telegram.send_message(alert_message))
            except Exception as e:
                print(f"Failed to send alert: {e}")

    def send_message(self, message: str, level: str = "INFO", details: Any = None):
        """Send message to Telegram"""
        if self.telegram and self.config.log_to_telegram:
            try:
                formatted_message = f"[{level}] {message}"
                if details:
                    formatted_message += f"\nDetails: {json.dumps(details, indent=2)}"

                asyncio.create_task(self.telegram.send_message(formatted_message))
            except Exception as e:
                print(f"Failed to send message: {e}")
