import asyncio
import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Optional external logging services
# These are only imported if the corresponding environment variables are set
BOTO3_AVAILABLE = False
GOOGLE_CLOUD_AVAILABLE = False
OPENCENSUS_AVAILABLE = False

try:
    import boto3  # type: ignore

    BOTO3_AVAILABLE = True
except ImportError:
    pass

try:
    from google.cloud import logging as gcp_logging  # type: ignore

    GOOGLE_CLOUD_AVAILABLE = True
except ImportError:
    pass

try:
    from opencensus.ext.azure.log_exporter import AzureLogHandler  # type: ignore

    OPENCENSUS_AVAILABLE = True
except ImportError:
    pass


class LogLevel:
    """Уровни логирования для разных каналов"""

    TERMINAL = "TERMINAL"  # Консоль - только важные события
    FILE = "FILE"  # Файл - подробная информация
    DATABASE = "DATABASE"  # SQLite - только ключевые события
    TELEGRAM = "TELEGRAM"  # Telegram - алерты и важные уведомления


class UnifiedLogger:
    def __init__(self, config):
        self.config = config
        self.db_path = Path(config.db_path)
        self.lock = threading.Lock()
        self.telegram = None

        # Настройки логирования из конфига
        self.max_log_size_mb = getattr(config, "max_log_size_mb", 100)
        self.log_retention_days = getattr(config, "log_retention_days", 30)
        self.log_level = getattr(config, "log_level", "INFO").upper()  # CLEAN, VERBOSE, DEBUG

        # Ограничение частоты логирования для предотвращения спама
        self.log_rate_limit = {}  # {component: last_log_time}
        self.min_log_interval = 60  # Минимальный интервал между логами в секундах

        # Настройки для разных уровней verbosity
        self.verbosity_settings = {
            "CLEAN": {
                "terminal_interval": 300,  # 5 минут
                "telegram_interval": 600,  # 10 минут
                "show_ws_updates": False,
                "show_ping_pong": False,
            },
            "VERBOSE": {
                "terminal_interval": 60,  # 1 минута
                "telegram_interval": 300,  # 5 минут
                "show_ws_updates": True,
                "show_ping_pong": False,
            },
            "DEBUG": {
                "terminal_interval": 10,  # 10 секунд
                "telegram_interval": 60,  # 1 минута
                "show_ws_updates": True,
                "show_ping_pong": True,
            },
        }

        self.current_verbosity = self.verbosity_settings.get(
            self.log_level, self.verbosity_settings["CLEAN"]
        )

        # Создаем директории для логов если не существуют
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        Path("logs").mkdir(exist_ok=True)

        # Настройка файлового логирования
        self._setup_file_logging()
        self._init_db()
        self._setup_console_logging()
        self._cleanup_old_logs()

    def _setup_file_logging(self):
        """Настраивает файловое логирование с улучшенной структурой"""
        self.file_logger = logging.getLogger("binance_bot")
        self.file_logger.setLevel(logging.INFO)

        # Создаем форматтер с улучшенной структурой
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)-15s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )

        # Хендлер для main.log - основные события
        main_log_handler = logging.FileHandler("logs/main.log", encoding="utf-8")
        main_log_handler.setLevel(logging.INFO)
        main_log_handler.setFormatter(formatter)

        # Хендлер для error.log - только ошибки
        error_log_handler = logging.FileHandler("logs/error.log", encoding="utf-8")
        error_log_handler.setLevel(logging.ERROR)
        error_log_handler.setFormatter(formatter)

        # Хендлер для analysis.log - аналитика и рекомендации
        analysis_log_handler = logging.FileHandler("logs/analysis.log", encoding="utf-8")
        analysis_log_handler.setLevel(logging.INFO)
        analysis_log_handler.setFormatter(formatter)

        # Хендлер для runtime.log - runtime события (новый)
        runtime_log_handler = logging.FileHandler("logs/runtime.log", encoding="utf-8")
        runtime_log_handler.setLevel(logging.INFO)
        runtime_log_handler.setFormatter(formatter)

        # Добавляем хендлеры
        self.file_logger.addHandler(main_log_handler)
        self.file_logger.addHandler(error_log_handler)
        self.file_logger.addHandler(analysis_log_handler)
        self.file_logger.addHandler(runtime_log_handler)

        # Отключаем дублирование в консоль
        self.file_logger.propagate = False

        # Настройка внешних лог-сервисов
        self._setup_external_logging()

    def _setup_external_logging(self):
        """Настраивает внешние лог-сервисы"""
        # Проверяем переменные окружения для внешних сервисов
        self.external_loggers = {}

        # CloudWatch (AWS)
        if os.getenv("AWS_CLOUDWATCH_ENABLED", "false").lower() == "true":
            if BOTO3_AVAILABLE:
                self.external_loggers["cloudwatch"] = self._setup_cloudwatch()
            else:
                print("Warning: boto3 not installed, CloudWatch logging disabled")

        # Stackdriver (GCP)
        if os.getenv("GCP_STACKDRIVER_ENABLED", "false").lower() == "true":
            if GOOGLE_CLOUD_AVAILABLE:
                self.external_loggers["stackdriver"] = self._setup_stackdriver()
            else:
                print("Warning: google-cloud-logging not installed, StackDriver logging disabled")

        # Azure Monitor
        if os.getenv("AZURE_MONITOR_ENABLED", "false").lower() == "true":
            if OPENCENSUS_AVAILABLE:
                self.external_loggers["azure"] = self._setup_azure_monitor()
            else:
                print("Warning: opencensus not installed, Azure Monitor logging disabled")

    def _setup_cloudwatch(self):
        """Настройка AWS CloudWatch"""
        if not BOTO3_AVAILABLE:
            return None
        try:
            client = boto3.client("logs")
            return {
                "client": client,
                "log_group": os.getenv("AWS_CLOUDWATCH_LOG_GROUP", "binance-bot"),
                "log_stream": f"bot-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            }
        except Exception as e:
            print(f"Warning: CloudWatch setup failed: {e}")
            return None

    def _setup_stackdriver(self):
        """Настройка GCP StackDriver"""
        if not GOOGLE_CLOUD_AVAILABLE:
            return None
        try:
            client = gcp_logging.Client()
            return {
                "client": client,
                "logger": client.logger(os.getenv("GCP_STACKDRIVER_LOG_NAME", "binance-bot")),
            }
        except Exception as e:
            print(f"Warning: StackDriver setup failed: {e}")
            return None

    def _setup_azure_monitor(self):
        """Настройка Azure Monitor"""
        if not OPENCENSUS_AVAILABLE:
            return None
        try:
            connection_string = os.getenv("AZURE_MONITOR_CONNECTION_STRING")
            if connection_string:
                return {"handler": AzureLogHandler(connection_string=connection_string)}
        except Exception as e:
            print(f"Warning: Azure Monitor setup failed: {e}")
            return None

    def _send_to_external_loggers(self, level: str, message: str, details: Any = None):
        """Отправляет логи во внешние сервисы"""
        for service_name, logger_config in self.external_loggers.items():
            try:
                if service_name == "cloudwatch" and logger_config:
                    self._send_to_cloudwatch(logger_config, level, message, details)
                elif service_name == "stackdriver" and logger_config:
                    self._send_to_stackdriver(logger_config, level, message, details)
                elif service_name == "azure" and logger_config:
                    self._send_to_azure(logger_config, level, message, details)
            except Exception as e:
                print(f"Warning: Failed to send to {service_name}: {e}")

    def _send_to_cloudwatch(self, config, level: str, message: str, details: Any = None):
        """Отправка в AWS CloudWatch"""
        try:
            log_event = {
                "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                "message": f"{level}: {message}",
                "level": level,
            }
            if details:
                log_event["details"] = json.dumps(details)

            config["client"].put_log_events(
                logGroupName=config["log_group"],
                logStreamName=config["log_stream"],
                logEvents=[log_event],
            )
        except Exception as e:
            print(f"CloudWatch error: {e}")

    def _send_to_stackdriver(self, config, level: str, message: str, details: Any = None):
        """Отправка в GCP StackDriver"""
        try:
            log_entry = {"severity": level.upper(), "message": message}
            if details:
                log_entry["details"] = details

            config["logger"].log_struct(log_entry)
        except Exception as e:
            print(f"StackDriver error: {e}")

    def _send_to_azure(self, config, level: str, message: str, details: Any = None):
        """Отправка в Azure Monitor"""
        try:
            log_record = {"level": level.upper(), "message": message}
            if details:
                log_record["details"] = details

            config["handler"].emit(log_record)
        except Exception as e:
            print(f"Azure Monitor error: {e}")

    def _setup_console_logging(self):
        """Настраивает консольное логирование с цветами"""
        # Цвета для разных уровней
        self.level_colors = {
            "DEBUG": "\033[36m",  # Cyan
            "INFO": "\033[32m",  # Green
            "WARNING": "\033[33m",  # Yellow
            "ERROR": "\033[31m",  # Red
            "CRITICAL": "\033[35m",  # Magenta
        }
        self.reset_color = "\033[0m"

        # Эмодзи для разных типов событий
        self.event_emojis = {
            "TRADE": "💰",
            "SIGNAL": "📡",
            "RISK": "⚠️",
            "SYSTEM": "⚙️",
            "TELEGRAM": "📱",
            "WEBSOCKET": "🔌",
            "API": "🌐",
            "PERFORMANCE": "📊",
            "ORDER": "📋",
            "POSITION": "📈",
            "TP_SL": "🎯",
            "TIMEOUT": "⏰",
            "EMERGENCY": "🚨",
            "SHUTDOWN": "🛑",
            "STARTUP": "🚀",
            "CONFIG": "⚙️",
            "STRATEGY": "🧠",
            "EXCHANGE": "🏦",
            "POST_RUN_ANALYZER": "📈",
            "TEST": "🧪",
        }

        # Специальные цвета для важных событий
        self.special_colors = {
            "PROFIT": "\033[32m",  # Green
            "LOSS": "\033[31m",  # Red
            "BREAK_EVEN": "\033[33m",  # Yellow
            "HIGH_PROFIT": "\033[92m",  # Bright Green
            "HIGH_LOSS": "\033[91m",  # Bright Red
            "SUCCESS": "\033[92m",  # Bright Green
            "FAILURE": "\033[91m",  # Bright Red
            "INFO_BLUE": "\033[94m",  # Blue
            "INFO_CYAN": "\033[96m",  # Bright Cyan
        }

    def _cleanup_old_logs(self):
        """Очищает старые логи"""
        try:
            if self.db_path.exists():
                # Проверяем размер файла
                size_mb = self.db_path.stat().st_size / (1024 * 1024)
                if size_mb > self.max_log_size_mb:
                    self._rotate_logs()

                # Удаляем старые записи
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.log_retention_days)
                with self.lock, sqlite3.connect(self.db_path) as conn:
                    c = conn.cursor()
                    # Удаляем старые записи из всех таблиц
                    for table in ["trades", "entry_attempts", "tp_sl_events", "events"]:
                        c.execute(
                            f"DELETE FROM {table} WHERE timestamp < ?", (cutoff_date.isoformat(),)
                        )
                    conn.commit()

                    deleted_count = c.rowcount
                    if deleted_count > 0:
                        print(f"🧹 Cleaned up {deleted_count} old log entries")

        except Exception as e:
            print(f"⚠️ Log cleanup error: {e}")

    def _rotate_logs(self):
        """Ротация логов при превышении размера"""
        try:
            backup_path = self.db_path.with_suffix(
                f".backup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.db"
            )

            # Создаем резервную копию
            import shutil

            shutil.copy2(self.db_path, backup_path)

            # Очищаем основную БД, оставляя только последние записи
            with self.lock, sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                for table in ["trades", "entry_attempts", "tp_sl_events", "events"]:
                    # Оставляем только последние 1000 записей
                    c.execute(
                        f"DELETE FROM {table} WHERE id NOT IN (SELECT id FROM {table} ORDER BY id DESC LIMIT 1000)"
                    )
                conn.commit()

            print(f"🔄 Log rotated: {backup_path.name}")

        except Exception as e:
            print(f"⚠️ Log rotation error: {e}")

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            # Таблица сделок
            c.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    symbol TEXT,
                    side TEXT,
                    qty REAL,
                    entry_price REAL,
                    reason TEXT,
                    pnl REAL DEFAULT 0,
                    win INTEGER DEFAULT 0
                )
            """)
            # Таблица попыток входа
            c.execute("""
                CREATE TABLE IF NOT EXISTS entry_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    symbol TEXT,
                    side TEXT,
                    reason TEXT,
                    success INTEGER
                )
            """)
            # TP/SL события
            c.execute("""
                CREATE TABLE IF NOT EXISTS tp_sl_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    symbol TEXT,
                    type TEXT,
                    price REAL,
                    qty REAL
                )
            """)
            # Системные события
            c.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    level TEXT,
                    component TEXT,
                    message TEXT,
                    details TEXT
                )
            """)
            conn.commit()

    def log_trade(
        self,
        symbol: str,
        side: str,
        qty: float,
        price: float,
        reason: str,
        pnl: float = 0,
        win: bool = False,
    ):
        """Логирует сделку с красивым выводом"""
        timestamp = datetime.now(timezone.utc)

        # Определяем цвет и эмодзи на основе результата
        if pnl > 0:
            color = self.special_colors["PROFIT"]
            emoji = "💰"
            result_text = f"PROFIT +${pnl:.2f}"
        elif pnl < 0:
            color = self.special_colors["LOSS"]
            emoji = "📉"
            result_text = f"LOSS ${pnl:.2f}"
        else:
            color = self.special_colors["BREAK_EVEN"]
            emoji = "⚖️"
            result_text = "BREAK EVEN"

        reset = self.reset_color

        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute(
                """
                INSERT INTO trades (timestamp, symbol, side, qty, entry_price, reason, pnl, win)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (timestamp.isoformat(), symbol, side, qty, price, reason, pnl, win),
            )
            conn.commit()

        # Красивый вывод в консоль
        formatted_time = timestamp.strftime("%H:%M:%S")
        side_emoji = "📈" if side == "BUY" else "📉"

        console_msg = f"{color}[{formatted_time}] {emoji} {side_emoji} {symbol} {side} {qty:.4f} @ ${price:.2f} | {result_text}{reset}"
        print(console_msg)

        # Telegram уведомление для важных сделок
        if self.telegram and abs(pnl) > 5:  # Уведомляем о сделках с PnL > $5
            telegram_msg = f"{emoji} {symbol} {side} | {result_text}"
            asyncio.create_task(self.telegram.send_notification(telegram_msg))

    def log_entry_attempt(self, symbol: str, side: str, reason: str, success: bool):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute(
                """
                INSERT INTO entry_attempts (timestamp, symbol, side, reason, success)
                VALUES (?, ?, ?, ?, ?)
            """,
                (datetime.now(timezone.utc).isoformat(), symbol, side, reason, int(success)),
            )
            conn.commit()

    def log_event(
        self, component: str, level: str, message: str, details: Any = None, channels: list = None
    ):
        """Улучшенное логирование событий с выбором каналов"""
        timestamp = datetime.now(timezone.utc)

        # Проверяем частоту логирования для предотвращения спама
        current_time = timestamp.timestamp()
        if component in self.log_rate_limit:
            time_since_last = current_time - self.log_rate_limit[component]
            if time_since_last < self.min_log_interval and level.upper() not in [
                "ERROR",
                "CRITICAL",
            ]:
                return  # Пропускаем логирование если прошло мало времени

        # Обновляем время последнего логирования
        self.log_rate_limit[component] = current_time

        # Определяем каналы для логирования
        if channels is None:
            channels = [LogLevel.FILE, LogLevel.DATABASE]
            if level.upper() in ["ERROR", "WARNING"] or component in ["TRADE", "POSITION", "RISK"]:
                channels.append(LogLevel.TELEGRAM)

        # Сохраняем в БД
        if LogLevel.DATABASE in channels:
            with self.lock, sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                details_json = json.dumps(details) if details else None
                c.execute(
                    """
                    INSERT INTO events (timestamp, level, component, message, details)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (timestamp.isoformat(), level.upper(), component, message, details_json),
                )
                conn.commit()

        # Логируем в файл
        if LogLevel.FILE in channels:
            # Определяем цвет и эмодзи
            color = self.level_colors.get(level.upper(), "")
            reset = self.reset_color
            emoji = self.event_emojis.get(component.upper(), "ℹ️")

            # Специальная обработка для торговых событий
            if "TRADE" in component.upper() or "PNL" in message.upper():
                if "profit" in message.lower() or "gain" in message.lower():
                    color = self.special_colors["PROFIT"]
                elif "loss" in message.lower() or "loss" in message.lower():
                    color = self.special_colors["LOSS"]
                elif "break even" in message.lower():
                    color = self.special_colors["BREAK_EVEN"]

            # Специальная обработка для сигналов
            if "SIGNAL" in component.upper():
                if "strong" in message.lower() or "buy" in message.lower():
                    color = self.special_colors["HIGH_PROFIT"]
                elif "sell" in message.lower():
                    color = self.special_colors["HIGH_LOSS"]

            # Форматируем сообщение
            formatted_time = timestamp.strftime("%H:%M:%S")
            component_str = f"[{component}]" if component else ""

        # Красивый вывод с эмодзи
        console_msg = (
            f"{color}[{formatted_time}] {emoji} {level.upper()}{component_str} {message}{reset}"
        )
        print(console_msg)

        # Логируем в файлы
        log_message = f"{level.upper()}[{component}] {message}"
        if details:
            log_message += f" | Details: {json.dumps(details, ensure_ascii=False)}"

        # В main.log
        self.file_logger.info(log_message)

        # В error.log для ошибок
        if level.upper() in ["ERROR", "CRITICAL"]:
            self.file_logger.error(log_message)

        # Детали для ERROR и CRITICAL
        if details and level.upper() in ["ERROR", "CRITICAL"]:
            print(f"  {color}Details: {json.dumps(details, indent=2)}{reset}")

        # Telegram уведомления для важных событий
        if self.telegram and level.upper() in ["ERROR", "WARNING", "CRITICAL"]:
            emoji_map = {"ERROR": "⚠️", "WARNING": "⚠️", "CRITICAL": "🚨"}
            emoji = emoji_map.get(level.upper(), "ℹ️")
            telegram_msg = f"{emoji} {component}: {message}"
            asyncio.create_task(self.telegram.send_notification(telegram_msg))

        # Отправляем во внешние лог-сервисы
        self._send_to_external_loggers(level.upper(), message, details)

    def log_analysis_recommendation(self, recommendation: str, priority: str = "INFO"):
        """Логирует короткую рекомендацию анализа"""
        timestamp = datetime.now(timezone.utc)

        # Логируем в консоль
        color = self.level_colors.get(priority, "")
        console_message = f"{color}[{timestamp.strftime('%H:%M:%S')}] 📊 ANALYSIS_RECOMMENDATION: {recommendation}{self.reset_color}"
        print(console_message)

        # Логируем в analysis.log
        self.file_logger.info(f"ANALYSIS_RECOMMENDATION: {recommendation}")

        # Сохраняем в БД
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute(
                """
                INSERT INTO events (timestamp, level, component, message, details)
                VALUES (?, ?, ?, ?, ?)
            """,
                (timestamp.isoformat(), priority, "POST_RUN_ANALYZER", recommendation, None),
            )
            conn.commit()

        # Отправляем в Telegram
        if self.telegram:
            telegram_message = f"📊 Рекомендация анализа:\n{recommendation}"
            asyncio.create_task(self.telegram.send_notification(telegram_message))

    def log_quick_summary(self, summary: str):
        """Логирует краткую сводку"""
        timestamp = datetime.now(timezone.utc)

        # Логируем в консоль
        console_message = f"{self.special_colors['INFO_BLUE']}[{timestamp.strftime('%H:%M:%S')}] 📋 QUICK_SUMMARY: {summary}{self.reset_color}"
        print(console_message)

        # Логируем в main.log
        self.file_logger.info(f"QUICK_SUMMARY: {summary}")

        # Сохраняем в БД
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute(
                """
                INSERT INTO events (timestamp, level, component, message, details)
                VALUES (?, ?, ?, ?, ?)
            """,
                (timestamp.isoformat(), "INFO", "QUICK_SUMMARY", summary, None),
            )
            conn.commit()

    def get_recent_logs(self, hours: int = 24) -> list:
        """Получает логи за последние N часов"""
        since = datetime.now(timezone.utc) - timedelta(hours=hours)

        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute(
                """
                SELECT timestamp, level, component, message, details
                FROM events
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT 1000
            """,
                (since.isoformat(),),
            )

            logs = []
            for row in c.fetchall():
                logs.append(
                    {
                        "timestamp": row[0],
                        "level": row[1],
                        "component": row[2],
                        "message": row[3],
                        "details": json.loads(row[4]) if row[4] else None,
                    }
                )

            return logs

    def get_log_files_info(self) -> dict:
        """Получает информацию о файлах логов"""
        log_files = {}

        for log_file in ["logs/main.log", "logs/error.log", "logs/analysis.log"]:
            if Path(log_file).exists():
                stat = Path(log_file).stat()
                log_files[log_file] = {
                    "size_mb": stat.st_size / (1024 * 1024),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "lines": sum(1 for _ in open(log_file, encoding="utf-8")),
                }
            else:
                log_files[log_file] = {"exists": False}

        return log_files

    def log_run_status(self, status: str, details: dict = None):
        """Логирование статуса рана"""
        self.log_event("RUN_STATUS", "INFO", f"Bot status: {status}", details)

    def log_tp_sl_event(self, symbol: str, event_type: str, price: float, qty: float):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute(
                """
                INSERT INTO tp_sl_events (timestamp, symbol, type, price, qty)
                VALUES (?, ?, ?, ?, ?)
            """,
                (datetime.now(timezone.utc).isoformat(), symbol, event_type, price, qty),
            )
            conn.commit()

    def get_symbol_performance(self, symbol: str, days: int = 30) -> dict[str, Any] | None:
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            since = datetime.now(timezone.utc).timestamp() - days * 86400
            c.execute(
                """
                SELECT COUNT(*), SUM(pnl), SUM(win)
                FROM trades
                WHERE symbol = ? AND strftime('%s', timestamp) >= ?
            """,
                (symbol, since),
            )
            row = c.fetchone()
            if not row or row[0] == 0:
                return None

            total_trades, total_pnl, wins = row
            win_rate = wins / total_trades if total_trades else 0

            return {
                "win_rate": win_rate,
                "avg_drawdown_percent": 0.0,  # Calculate drawdown separately if needed
                "total_trades": total_trades,
                "total_pnl": total_pnl or 0.0,
            }

    def get_run_summary(self, hours: int = 24) -> dict[str, Any]:
        """Получает сводку за последние N часов"""
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            since = datetime.now(timezone.utc) - timedelta(hours=hours)

            # Статистика торговли
            c.execute(
                """
                SELECT COUNT(*), SUM(pnl), SUM(win), AVG(pnl)
                FROM trades
                WHERE timestamp >= ?
            """,
                (since.isoformat(),),
            )

            trade_row = c.fetchone()
            total_trades, total_pnl, total_wins, avg_pnl = trade_row or (0, 0, 0, 0)

            # Статистика событий
            c.execute(
                """
                SELECT level, COUNT(*)
                FROM events
                WHERE timestamp >= ?
                GROUP BY level
            """,
                (since.isoformat(),),
            )

            event_stats = dict(c.fetchall())

            return {
                "period_hours": hours,
                "total_trades": total_trades,
                "total_pnl": total_pnl or 0.0,
                "total_wins": total_wins or 0,
                "win_rate": (total_wins / total_trades) if total_trades > 0 else 0,
                "avg_pnl": avg_pnl or 0.0,
                "events": event_stats,
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }

    def attach_telegram(self, telegram_bot):
        """Привязывает Telegram бота к логгеру"""
        self.telegram = telegram_bot

    def get_log_stats(self) -> dict[str, Any]:
        """Получает статистику логов"""
        with self.lock, sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()

            # Размер БД
            db_size = self.db_path.stat().st_size / (1024 * 1024)  # MB

            # Количество записей в таблицах
            tables = ["trades", "entry_attempts", "tp_sl_events", "events"]
            table_counts = {}

            for table in tables:
                c.execute(f"SELECT COUNT(*) FROM {table}")
                table_counts[table] = c.fetchone()[0]

            return {
                "db_size_mb": round(db_size, 2),
                "table_counts": table_counts,
                "max_size_mb": self.max_log_size_mb,
                "retention_days": self.log_retention_days,
            }

    def log_runtime_status(self, status: str, details: dict = None):
        """Логирует runtime статус с адаптивным интервалом"""
        current_time = datetime.utcnow()
        component = "RUNTIME_STATUS"

        # Проверяем интервал для runtime статусов
        if component in self.log_rate_limit:
            time_diff = (current_time - self.log_rate_limit[component]).total_seconds()
            if time_diff < self.current_verbosity["terminal_interval"]:
                return

        self.log_rate_limit[component] = current_time

        # Логируем в runtime.log
        runtime_message = f"Status: {status}"
        if details:
            runtime_message += f" | {json.dumps(details, ensure_ascii=False, default=str)}"

        self.file_logger.info(f"[RUNTIME] {runtime_message}")

        # В БД только важные статусы
        if status in ["READY", "TRADING", "PAUSED", "ERROR"]:
            self._log_to_db(component, "INFO", status, details)

    def log_trading_event(self, event_type: str, symbol: str, details: dict = None):
        """Логирует торговые события с улучшенной структурой"""
        current_time = datetime.utcnow()

        # Определяем важность события
        important_events = ["ENTRY", "EXIT", "TP_HIT", "SL_HIT", "AUTO_PROFIT"]
        is_important = event_type in important_events

        # Формируем сообщение
        message = f"{event_type}: {symbol}"
        if details:
            message += f" | {json.dumps(details, ensure_ascii=False, default=str)}"

        # Логируем в соответствующие каналы
        channels = [LogLevel.FILE, LogLevel.DATABASE]
        if is_important:
            channels.append(LogLevel.TELEGRAM)
            channels.append(LogLevel.TERMINAL)

        self.log_event("TRADING", "INFO", message, details, channels)

    def log_analysis_event(self, analysis_type: str, message: str, details: dict = None):
        """Логирует события анализа"""
        # Логируем в analysis.log и БД
        self.log_event(
            "ANALYSIS",
            "INFO",
            f"{analysis_type}: {message}",
            details,
            [LogLevel.FILE, LogLevel.DATABASE],
        )

    def log_performance_metric(self, metric_name: str, value: float, symbol: str = None):
        """Логирует метрики производительности"""
        message = f"{metric_name}: {value:.4f}"
        if symbol:
            message += f" | Symbol: {symbol}"

        # Логируем в runtime.log и БД
        self.log_event("PERFORMANCE", "INFO", message, None, [LogLevel.FILE, LogLevel.DATABASE])

    def log_symbol_analysis(self, symbol: str, analysis_type: str, details: dict = None):
        """Логирует анализ символов"""
        message = f"Symbol Analysis: {symbol} | Type: {analysis_type}"
        if details:
            message += f" | {json.dumps(details, ensure_ascii=False, default=str)}"

        # Логируем в runtime.log и БД
        self.log_event(
            "SYMBOL_ANALYSIS", "INFO", message, details, [LogLevel.FILE, LogLevel.DATABASE]
        )

    def log_strategy_event(self, strategy_name: str, event_type: str, details: dict = None):
        """Логирует события стратегий"""
        message = f"Strategy: {strategy_name} | Event: {event_type}"
        if details:
            message += f" | {json.dumps(details, ensure_ascii=False, default=str)}"

        # Логируем в runtime.log и БД
        self.log_event("STRATEGY", "INFO", message, details, [LogLevel.FILE, LogLevel.DATABASE])

    def set_verbosity_level(self, level: str):
        """Устанавливает уровень verbosity"""
        level = level.upper()
        if level in self.verbosity_settings:
            self.log_level = level
            self.current_verbosity = self.verbosity_settings[level]
            self.log_event("LOGGER", "INFO", f"Verbosity level changed to: {level}")
        else:
            self.log_event("LOGGER", "WARNING", f"Invalid verbosity level: {level}")

    def get_verbosity_info(self) -> dict:
        """Получает информацию о текущих настройках verbosity"""
        return {
            "current_level": self.log_level,
            "settings": self.current_verbosity,
            "available_levels": list(self.verbosity_settings.keys()),
        }

    def send_alert(self, message: str, level: str = "INFO", details: Any = None):
        """Отправка алерта через Telegram и логирование"""
        try:
            # Логируем алерт
            self.log_event(
                "ALERT", level, message, details, channels=["telegram", "terminal", "file"]
            )

            # Отправляем в Telegram если доступен
            if self.telegram:
                try:
                    asyncio.create_task(self.telegram.send_message(message))
                except Exception as e:
                    self.log_event("TELEGRAM", "ERROR", f"Failed to send alert: {e}")
        except Exception as e:
            print(f"Error sending alert: {e}")

    def send_message(self, message: str, level: str = "INFO", details: Any = None):
        """Отправка сообщения через Telegram и логирование"""
        try:
            # Логируем сообщение
            self.log_event(
                "MESSAGE", level, message, details, channels=["telegram", "terminal", "file"]
            )

            # Отправляем в Telegram если доступен
            if self.telegram:
                try:
                    asyncio.create_task(self.telegram.send_message(message))
                except Exception as e:
                    self.log_event("TELEGRAM", "ERROR", f"Failed to send message: {e}")
        except Exception as e:
            print(f"Error sending message: {e}")
