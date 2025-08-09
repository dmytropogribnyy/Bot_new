import asyncio
import os
import sqlite3
import time
from typing import Any

from core.config import TradingConfig
from core.unified_logger import UnifiedLogger


class DatabaseOptimizer:
    """Comprehensive database optimization and maintenance system"""

    def __init__(self, config: TradingConfig, logger: UnifiedLogger | None = None):
        self.config = config
        self.logger = logger

        # Database paths
        self._db_paths = {
            "trading_log": "logs/trading_log.db",
            "monitoring": "logs/monitoring.db",
            "performance": "logs/performance.db",
            "telegram": "test_telegram.db",
        }

        # Optimization settings
        self._optimization_settings = {
            "auto_vacuum": True,
            "auto_analyze": True,
            "index_optimization": True,
            "cache_size": 10000,  # 10MB
            "temp_store": "memory",
            "synchronous": "normal",
            "journal_mode": "wal",
            "page_size": 4096,
        }

        # Performance tracking
        self._performance_metrics = {
            "query_times": [],
            "index_usage": {},
            "table_sizes": {},
            "fragmentation_levels": {},
            "last_optimization": {},
        }

        # Maintenance schedule
        self._maintenance_schedule = {
            "vacuum_interval": 24 * 3600,  # 24 hours
            "analyze_interval": 6 * 3600,  # 6 hours
            "index_rebuild_interval": 7 * 24 * 3600,  # 7 days
            "cleanup_interval": 12 * 3600,  # 12 hours
        }

        # Optimization tasks
        self._optimization_tasks = []
        self._is_running = False

        # Ограничение частоты логирования
        self.last_log_time = {}
        self.min_log_interval = 300  # 5 минут между логами

    async def start_optimization(self):
        """Start database optimization tasks"""
        if self._is_running:
            return

        self._is_running = True
        self.logger.log_event("DATABASE", "INFO", "🗄️ Starting Database Optimization System...")

        # Initialize all databases
        await self._initialize_databases()

        # Start optimization tasks
        self._optimization_tasks = [
            asyncio.create_task(self._periodic_vacuum()),
            asyncio.create_task(self._periodic_analyze()),
            asyncio.create_task(self._periodic_index_optimization()),
            asyncio.create_task(self._periodic_cleanup()),
            asyncio.create_task(self._performance_monitoring()),
        ]

    async def stop_optimization(self):
        """Stop database optimization tasks"""
        self._is_running = False

        for task in self._optimization_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self.logger.log_event("DATABASE", "INFO", "🛑 Database Optimization System stopped")

    async def _initialize_databases(self):
        """Initialize all databases with optimal settings"""
        for db_name, db_path in self._db_paths.items():
            try:
                if os.path.exists(db_path):
                    await self._optimize_database_settings(db_path)
                    await self._create_indexes(db_path)
                    self.logger.log_event(
                        "DATABASE", "INFO", f"✅ Initialized {db_name}: {db_path}"
                    )
                else:
                    self.logger.log_event("DATABASE", "WARNING", f"⚠️ Database not found: {db_path}")

            except Exception as e:
                self.logger.log_event(
                    "DATABASE", "ERROR", f"❌ Failed to initialize {db_name}: {e}"
                )

    async def _optimize_database_settings(self, db_path: str):
        """Apply optimal database settings"""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Apply optimization settings
            cursor.execute(f"PRAGMA cache_size = {self._optimization_settings['cache_size']}")
            cursor.execute(f"PRAGMA temp_store = {self._optimization_settings['temp_store']}")
            cursor.execute(f"PRAGMA synchronous = {self._optimization_settings['synchronous']}")
            cursor.execute(f"PRAGMA journal_mode = {self._optimization_settings['journal_mode']}")
            cursor.execute(f"PRAGMA page_size = {self._optimization_settings['page_size']}")

            if self._optimization_settings["auto_vacuum"]:
                cursor.execute("PRAGMA auto_vacuum = incremental")

            conn.commit()
            conn.close()

        except Exception as e:
            self.logger.log_event(
                "DATABASE", "ERROR", f"❌ Failed to optimize settings for {db_path}: {e}"
            )

    async def _create_indexes(self, db_path: str):
        """Create optimal indexes for database"""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Get table information
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()

            for table in tables:
                table_name = table[0]

                # Create indexes based on table name
                if "trading_log" in db_path:
                    await self._create_trading_log_indexes(cursor, table_name)
                elif "monitoring" in db_path:
                    await self._create_monitoring_indexes(cursor, table_name)
                elif "performance" in db_path:
                    await self._create_performance_indexes(cursor, table_name)
                elif "telegram" in db_path:
                    await self._create_telegram_indexes(cursor, table_name)

            conn.commit()
            conn.close()

        except Exception as e:
            self.logger.log_event(
                "DATABASE", "ERROR", f"❌ Failed to create indexes for {db_path}: {e}"
            )

    async def _create_trading_log_indexes(self, cursor, table_name: str):
        """Create indexes for trading log database"""
        try:
            if table_name == "trades":
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp)"
                )
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_side ON trades(side)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status)")
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_trades_timestamp_symbol ON trades(timestamp, symbol)"
                )

            elif table_name == "positions":
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_positions_timestamp ON positions(timestamp)"
                )

            elif table_name == "performance_metrics":
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_perf_metrics_timestamp ON performance_metrics(timestamp)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_perf_metrics_type ON performance_metrics(metric_type)"
                )

        except Exception as e:
            self.logger.log_event(
                "DATABASE", "ERROR", f"❌ Failed to create trading log indexes: {e}"
            )

    async def _create_monitoring_indexes(self, cursor, table_name: str):
        """Create indexes for monitoring database"""
        try:
            if table_name == "performance_metrics":
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_mon_perf_timestamp ON performance_metrics(timestamp)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_mon_perf_type ON performance_metrics(metric_type)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_mon_perf_name ON performance_metrics(metric_name)"
                )

            elif table_name == "system_alerts":
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON system_alerts(timestamp)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_alerts_type ON system_alerts(alert_type)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_alerts_severity ON system_alerts(severity)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_alerts_resolved ON system_alerts(resolved)"
                )

            elif table_name == "system_health":
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_health_timestamp ON system_health(timestamp)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_health_score ON system_health(overall_score)"
                )

        except Exception as e:
            self.logger.log_event(
                "DATABASE", "ERROR", f"❌ Failed to create monitoring indexes: {e}"
            )

    async def _create_performance_indexes(self, cursor, table_name: str):
        """Create indexes for performance database"""
        try:
            if table_name == "performance_data":
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_perf_data_timestamp ON performance_data(timestamp)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_perf_data_metric ON performance_data(metric_name)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_perf_data_value ON performance_data(value)"
                )

        except Exception as e:
            self.logger.log_event(
                "DATABASE", "ERROR", f"❌ Failed to create performance indexes: {e}"
            )

    async def _create_telegram_indexes(self, cursor, table_name: str):
        """Create indexes for telegram database"""
        try:
            if table_name == "messages":
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_messages_type ON messages(message_type)"
                )

        except Exception as e:
            self.logger.log_event("DATABASE", "ERROR", f"❌ Failed to create telegram indexes: {e}")

    async def _periodic_vacuum(self):
        """Perform periodic VACUUM operations"""
        while self._is_running:
            try:
                for db_name, db_path in self._db_paths.items():
                    if os.path.exists(db_path):
                        await self._vacuum_database(db_path)

                await asyncio.sleep(self._maintenance_schedule["vacuum_interval"])

            except Exception as e:
                self.logger.log_event("DATABASE", "ERROR", f"❌ Periodic vacuum error: {e}")
                await asyncio.sleep(3600)  # Wait 1 hour on error

    async def _periodic_analyze(self):
        """Perform periodic ANALYZE operations"""
        while self._is_running:
            try:
                for db_name, db_path in self._db_paths.items():
                    if os.path.exists(db_path):
                        await self._analyze_database(db_path)

                await asyncio.sleep(self._maintenance_schedule["analyze_interval"])

            except Exception as e:
                self.logger.log_event("DATABASE", "ERROR", f"❌ Periodic analyze error: {e}")
                await asyncio.sleep(1800)  # Wait 30 minutes on error

    async def _periodic_index_optimization(self):
        """Perform periodic index optimization"""
        while self._is_running:
            try:
                for db_name, db_path in self._db_paths.items():
                    if os.path.exists(db_path):
                        await self._optimize_indexes(db_path)

                await asyncio.sleep(self._maintenance_schedule["index_rebuild_interval"])

            except Exception as e:
                self.logger.log_event(
                    "DATABASE", "ERROR", f"❌ Periodic index optimization error: {e}"
                )
                await asyncio.sleep(86400)  # Wait 1 day on error

    async def _periodic_cleanup(self):
        """Perform periodic cleanup operations"""
        while self._is_running:
            try:
                for db_name, db_path in self._db_paths.items():
                    if os.path.exists(db_path):
                        await self._cleanup_old_data(db_path)

                await asyncio.sleep(self._maintenance_schedule["cleanup_interval"])

            except Exception as e:
                self.logger.log_event("DATABASE", "ERROR", f"❌ Periodic cleanup error: {e}")
                await asyncio.sleep(3600)  # Wait 1 hour on error

    async def _performance_monitoring(self):
        """Monitor database performance"""
        while self._is_running:
            try:
                for db_name, db_path in self._db_paths.items():
                    if os.path.exists(db_path):
                        await self._monitor_database_performance(db_path)

                await asyncio.sleep(300)  # Check every 5 minutes

            except Exception as e:
                self.logger.log_event("DATABASE", "ERROR", f"❌ Performance monitoring error: {e}")
                await asyncio.sleep(600)  # Wait 10 minutes on error

    async def _vacuum_database(self, db_path: str):
        """Perform VACUUM operation on database"""
        try:
            start_time = time.time()

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Get database size before vacuum
            cursor.execute("PRAGMA page_count")
            page_count_before = cursor.fetchone()[0]

            # Perform VACUUM
            cursor.execute("VACUUM")

            # Get database size after vacuum
            cursor.execute("PRAGMA page_count")
            page_count_after = cursor.fetchone()[0]

            conn.close()

            vacuum_time = time.time() - start_time
            space_saved = page_count_before - page_count_after

            # Проверяем частоту логирования
            current_time = time.time()
            if (
                db_path not in self.last_log_time
                or current_time - self.last_log_time[db_path] > self.min_log_interval
            ):
                self.logger.log_event(
                    "DATABASE",
                    "INFO",
                    f"🗄️ VACUUM completed for {db_path}: {vacuum_time:.2f}s, "
                    f"space saved: {space_saved} pages",
                )
                self.last_log_time[db_path] = current_time

            # Update performance metrics
            self._performance_metrics["last_optimization"][db_path] = {
                "operation": "vacuum",
                "timestamp": time.time(),
                "duration": vacuum_time,
                "space_saved": space_saved,
            }

        except Exception as e:
            self.logger.log_event("DATABASE", "ERROR", f"❌ VACUUM failed for {db_path}: {e}")

    async def _analyze_database(self, db_path: str):
        """Perform ANALYZE operation on database"""
        try:
            start_time = time.time()

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Perform ANALYZE
            cursor.execute("ANALYZE")

            conn.close()

            analyze_time = time.time() - start_time

            # Проверяем частоту логирования
            current_time = time.time()
            if (
                db_path not in self.last_log_time
                or current_time - self.last_log_time[db_path] > self.min_log_interval
            ):
                self.logger.log_event(
                    "DATABASE", "INFO", f"📊 ANALYZE completed for {db_path}: {analyze_time:.2f}s"
                )
                self.last_log_time[db_path] = current_time

            # Update performance metrics
            self._performance_metrics["last_optimization"][db_path] = {
                "operation": "analyze",
                "timestamp": time.time(),
                "duration": analyze_time,
            }

        except Exception as e:
            self.logger.log_event("DATABASE", "ERROR", f"❌ ANALYZE failed for {db_path}: {e}")

    async def _optimize_indexes(self, db_path: str):
        """Optimize database indexes"""
        try:
            start_time = time.time()

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Get index information
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indexes = cursor.fetchall()

            optimized_count = 0
            for index in indexes:
                index_name = index[0]
                if not index_name.startswith("sqlite_autoindex"):  # Skip auto-indexes
                    try:
                        # Rebuild index
                        cursor.execute(f"REINDEX {index_name}")
                        optimized_count += 1
                    except Exception as e:
                        self.logger.log_event(
                            "DATABASE", "WARNING", f"⚠️ Failed to optimize index {index_name}: {e}"
                        )

            conn.close()

            optimize_time = time.time() - start_time

            self.logger.log_event(
                "DATABASE",
                "INFO",
                f"🔧 Index optimization completed for {db_path}: "
                f"{optimize_time:.2f}s, {optimized_count} indexes optimized",
            )

        except Exception as e:
            self.logger.log_event(
                "DATABASE", "ERROR", f"❌ Index optimization failed for {db_path}: {e}"
            )

    async def _cleanup_old_data(self, db_path: str):
        """Clean up old data from database"""
        try:
            start_time = time.time()

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Get current timestamp
            current_time = time.time()

            # Clean up old records (older than 30 days)
            cutoff_time = current_time - (30 * 24 * 3600)

            deleted_count = 0

            # Clean up different tables based on database type
            if "trading_log" in db_path:
                cursor.execute("DELETE FROM trades WHERE timestamp < ?", (cutoff_time,))
                deleted_count += cursor.rowcount

                cursor.execute("DELETE FROM positions WHERE timestamp < ?", (cutoff_time,))
                deleted_count += cursor.rowcount

            elif "monitoring" in db_path:
                cursor.execute(
                    "DELETE FROM performance_metrics WHERE timestamp < ?", (cutoff_time,)
                )
                deleted_count += cursor.rowcount

                cursor.execute(
                    "DELETE FROM system_alerts WHERE timestamp < ? AND resolved = 1", (cutoff_time,)
                )
                deleted_count += cursor.rowcount

            elif "performance" in db_path:
                cursor.execute("DELETE FROM performance_data WHERE timestamp < ?", (cutoff_time,))
                deleted_count += cursor.rowcount

            elif "telegram" in db_path:
                # Check if messages table exists before trying to clean it
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='messages'"
                )
                if cursor.fetchone():
                    cursor.execute("DELETE FROM messages WHERE timestamp < ?", (cutoff_time,))
                    deleted_count += cursor.rowcount

            conn.commit()
            conn.close()

            cleanup_time = time.time() - start_time

            if deleted_count > 0:
                self.logger.log_event(
                    "DATABASE",
                    "INFO",
                    f"🧹 Cleanup completed for {db_path}: {cleanup_time:.2f}s, "
                    f"{deleted_count} records deleted",
                )

        except Exception as e:
            self.logger.log_event("DATABASE", "ERROR", f"❌ Cleanup failed for {db_path}: {e}")

    async def _monitor_database_performance(self, db_path: str):
        """Monitor database performance metrics"""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Get database statistics
            cursor.execute("PRAGMA page_count")
            page_count = cursor.fetchone()[0]

            cursor.execute("PRAGMA page_size")
            page_size = cursor.fetchone()[0]

            cursor.execute("PRAGMA cache_size")
            cache_size = cursor.fetchone()[0]

            # Calculate database size
            db_size = page_count * page_size

            # Get table sizes
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()

            table_sizes = {}
            for table in tables:
                table_name = table[0]
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                row_count = cursor.fetchone()[0]
                table_sizes[table_name] = row_count

            conn.close()

            # Update performance metrics
            self._performance_metrics["table_sizes"][db_path] = table_sizes

            # Log performance summary
            if db_size > 100 * 1024 * 1024:  # 100MB
                self.logger.log_event(
                    "DATABASE",
                    "WARNING",
                    f"⚠️ Large database detected: {db_path} ({db_size / (1024 * 1024):.1f}MB)",
                )

        except Exception as e:
            self.logger.log_event(
                "DATABASE", "ERROR", f"❌ Performance monitoring failed for {db_path}: {e}"
            )

    async def get_database_stats(self) -> dict[str, Any]:
        """Get comprehensive database statistics"""
        stats = {}

        for db_name, db_path in self._db_paths.items():
            if os.path.exists(db_path):
                try:
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()

                    # Basic stats
                    cursor.execute("PRAGMA page_count")
                    page_count = cursor.fetchone()[0]

                    cursor.execute("PRAGMA page_size")
                    page_size = cursor.fetchone()[0]

                    db_size = page_count * page_size

                    # Table stats
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = cursor.fetchall()

                    table_stats = {}
                    for table in tables:
                        table_name = table[0]
                        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                        row_count = cursor.fetchone()[0]
                        table_stats[table_name] = row_count

                    conn.close()

                    stats[db_name] = {
                        "path": db_path,
                        "size_bytes": db_size,
                        "size_mb": db_size / (1024 * 1024),
                        "page_count": page_count,
                        "page_size": page_size,
                        "tables": table_stats,
                        "last_optimization": self._performance_metrics["last_optimization"].get(
                            db_path, {}
                        ),
                    }

                except Exception as e:
                    stats[db_name] = {"error": str(e)}

        return stats

    async def force_optimization(self, db_name: str | None = None):
        """Force immediate optimization of specified database or all databases"""
        try:
            if db_name:
                db_path = self._db_paths.get(db_name)
                if db_path and os.path.exists(db_path):
                    await self._vacuum_database(db_path)
                    await self._analyze_database(db_path)
                    await self._optimize_indexes(db_path)
                    self.logger.log_event(
                        "DATABASE", "INFO", f"✅ Forced optimization completed for {db_name}"
                    )
                else:
                    self.logger.log_event("DATABASE", "ERROR", f"❌ Database not found: {db_name}")
            else:
                # Optimize all databases
                for db_name, db_path in self._db_paths.items():
                    if os.path.exists(db_path):
                        await self._vacuum_database(db_path)
                        await self._analyze_database(db_path)
                        await self._optimize_indexes(db_path)

                self.logger.log_event(
                    "DATABASE", "INFO", "✅ Forced optimization completed for all databases"
                )

        except Exception as e:
            self.logger.log_event("DATABASE", "ERROR", f"❌ Forced optimization failed: {e}")

    def get_optimization_settings(self) -> dict[str, Any]:
        """Get current optimization settings"""
        return self._optimization_settings.copy()

    def update_optimization_settings(self, new_settings: dict[str, Any]):
        """Update optimization settings"""
        self._optimization_settings.update(new_settings)
        self.logger.log_event("DATABASE", "INFO", "⚙️ Database optimization settings updated")
