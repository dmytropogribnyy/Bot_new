#!/usr/bin/env python3
"""
Мониторинг производительности для BinanceBot v2
Отслеживание метрик системы и торговли
"""

import asyncio
import sqlite3
import statistics
import time
from collections import defaultdict, deque
from collections.abc import Callable
from typing import Any

import psutil

from core.config import TradingConfig
from core.unified_logger import UnifiedLogger


class AdvancedMonitor:
    """Enhanced monitoring system with real-time performance tracking and anomaly detection"""

    def __init__(self, config: TradingConfig, logger: UnifiedLogger | None = None):
        self.config = config
        self.logger = logger

        # Performance tracking
        self._performance_metrics = {
            'response_times': deque(maxlen=1000),
            'error_rates': defaultdict(lambda: deque(maxlen=100)),
            'success_rates': defaultdict(lambda: deque(maxlen=100)),
            'memory_usage': deque(maxlen=100),
            'cpu_usage': deque(maxlen=100),
            'network_latency': deque(maxlen=100)
        }

        # Anomaly detection
        self._anomaly_thresholds = {
            'response_time_threshold': 5.0,  # seconds
            'error_rate_threshold': 0.1,     # 10%
            'memory_threshold': 0.8,         # 80%
            'cpu_threshold': 0.9,            # 90%
            'latency_threshold': 1000        # milliseconds
        }

        # Alert system
        self._alerts = []
        self._alert_callbacks = []
        self._last_alert_time = defaultdict(float)
        self._alert_cooldown = 300  # 5 minutes

        # System health tracking
        self._system_health = {
            'overall_score': 100.0,
            'last_check': time.time(),
            'issues_detected': [],
            'recommendations': []
        }

        # Database for historical data
        self._db_path = "logs/monitoring.db"
        self._init_monitoring_db()

        # Monitoring tasks
        self._monitoring_tasks = []
        self._is_running = False

    def _init_monitoring_db(self):
        """Initialize monitoring database"""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    metric_type TEXT,
                    metric_name TEXT,
                    value REAL,
                    threshold REAL,
                    is_anomaly BOOLEAN
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    alert_type TEXT,
                    severity TEXT,
                    message TEXT,
                    resolved BOOLEAN DEFAULT FALSE
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_health (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    overall_score REAL,
                    issues_count INTEGER,
                    recommendations_count INTEGER
                )
            ''')

            conn.commit()
            conn.close()

        except Exception as e:
            self.logger.log_event("MONITORING", "ERROR", f"❌ Failed to initialize monitoring DB: {e}")

    async def start_monitoring(self):
        """Start all monitoring tasks"""
        if self._is_running:
            return

        self._is_running = True
        self.logger.log_event("MONITORING", "INFO", "🔍 Starting Advanced Monitoring System...")

        # Start monitoring tasks
        self._monitoring_tasks = [
            asyncio.create_task(self._monitor_system_resources()),
            asyncio.create_task(self._monitor_performance_metrics()),
            asyncio.create_task(self._detect_anomalies()),
            asyncio.create_task(self._update_system_health()),
            asyncio.create_task(self._cleanup_old_data())
        ]

    async def stop_monitoring(self):
        """Stop all monitoring tasks"""
        self._is_running = False

        for task in self._monitoring_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self.logger.log_event("MONITORING", "INFO", "🛑 Advanced Monitoring System stopped")

    async def _monitor_system_resources(self):
        """Monitor system resources (CPU, memory, network)"""
        while self._is_running:
            try:
                # CPU usage
                cpu_percent = psutil.cpu_percent(interval=1)
                self._performance_metrics['cpu_usage'].append(cpu_percent)

                # Memory usage
                memory = psutil.virtual_memory()
                memory_percent = memory.percent / 100.0
                self._performance_metrics['memory_usage'].append(memory_percent)

                # Network latency (simplified)
                network_latency = await self._measure_network_latency()
                self._performance_metrics['network_latency'].append(network_latency)

                # Log if thresholds exceeded
                if cpu_percent > self._anomaly_thresholds['cpu_threshold'] * 100:
                    await self._create_alert("HIGH_CPU", "WARNING",
                        f"CPU usage is high: {cpu_percent:.1f}%")

                if memory_percent > self._anomaly_thresholds['memory_threshold']:
                    await self._create_alert("HIGH_MEMORY", "WARNING",
                        f"Memory usage is high: {memory_percent:.1%}")

                if network_latency > self._anomaly_thresholds['latency_threshold']:
                    await self._create_alert("HIGH_LATENCY", "WARNING",
                        f"Network latency is high: {network_latency:.0f}ms")

                await asyncio.sleep(30)  # Check every 30 seconds

            except Exception as e:
                self.logger.log_event("MONITORING", "ERROR", f"❌ System resource monitoring error: {e}")
                await asyncio.sleep(60)

    async def _monitor_performance_metrics(self):
        """Monitor trading performance metrics"""
        while self._is_running:
            try:
                # Calculate average response times
                if self._performance_metrics['response_times']:
                    avg_response_time = statistics.mean(self._performance_metrics['response_times'])

                    if avg_response_time > self._anomaly_thresholds['response_time_threshold']:
                        await self._create_alert("SLOW_RESPONSE", "WARNING",
                            f"Average response time is slow: {avg_response_time:.2f}s")

                # Calculate error rates
                for operation, error_times in self._performance_metrics['error_rates'].items():
                    if len(error_times) >= 10:  # Need minimum data points
                        error_rate = sum(error_times) / len(error_times)

                        if error_rate > self._anomaly_thresholds['error_rate_threshold']:
                            await self._create_alert("HIGH_ERROR_RATE", "ERROR",
                                f"High error rate for {operation}: {error_rate:.1%}")

                await asyncio.sleep(60)  # Check every minute

            except Exception as e:
                self.logger.log_event("MONITORING", "ERROR", f"❌ Performance monitoring error: {e}")
                await asyncio.sleep(60)

    async def _detect_anomalies(self):
        """Detect anomalies in system behavior"""
        while self._is_running:
            try:
                anomalies = []

                # Check for sudden changes in metrics
                for metric_name, values in self._performance_metrics.items():
                    if len(values) >= 20:  # Need enough data points
                        recent_values = list(values)[-10:]  # Last 10 values
                        older_values = list(values)[-20:-10]  # Previous 10 values

                        if len(recent_values) >= 5 and len(older_values) >= 5:
                            recent_avg = statistics.mean(recent_values)
                            older_avg = statistics.mean(older_values)

                            # Detect significant changes (>50% change)
                            if older_avg > 0:
                                change_ratio = abs(recent_avg - older_avg) / older_avg
                                if change_ratio > 0.5:
                                    anomalies.append({
                                        'metric': metric_name,
                                        'change_ratio': change_ratio,
                                        'old_avg': older_avg,
                                        'new_avg': recent_avg
                                    })

                # Create alerts for anomalies
                for anomaly in anomalies:
                    await self._create_alert("ANOMALY_DETECTED", "WARNING",
                        f"Anomaly detected in {anomaly['metric']}: "
                        f"{anomaly['change_ratio']:.1%} change")

                await asyncio.sleep(120)  # Check every 2 minutes

            except Exception as e:
                self.logger.log_event("MONITORING", "ERROR", f"❌ Anomaly detection error: {e}")
                await asyncio.sleep(120)

    async def _update_system_health(self):
        """Update overall system health score"""
        while self._is_running:
            try:
                health_score = 100.0
                issues = []
                recommendations = []

                # Check CPU usage
                if self._performance_metrics['cpu_usage']:
                    avg_cpu = statistics.mean(self._performance_metrics['cpu_usage'])
                    if avg_cpu > 80:
                        health_score -= 10
                        issues.append(f"High CPU usage: {avg_cpu:.1f}%")
                        recommendations.append("Consider optimizing trading algorithms or reducing concurrent operations")

                # Check memory usage
                if self._performance_metrics['memory_usage']:
                    avg_memory = statistics.mean(self._performance_metrics['memory_usage'])
                    if avg_memory > 0.8:
                        health_score -= 15
                        issues.append(f"High memory usage: {avg_memory:.1%}")
                        recommendations.append("Consider implementing memory cleanup routines")

                # Check error rates
                total_errors = sum(len(errors) for errors in self._performance_metrics['error_rates'].values())
                total_operations = sum(len(success) for success in self._performance_metrics['success_rates'].values())

                if total_operations > 0:
                    error_rate = total_errors / (total_errors + total_operations)
                    if error_rate > 0.05:  # 5% error rate
                        health_score -= 20
                        issues.append(f"High error rate: {error_rate:.1%}")
                        recommendations.append("Review API connections and implement better error handling")

                # Check response times
                if self._performance_metrics['response_times']:
                    avg_response = statistics.mean(self._performance_metrics['response_times'])
                    if avg_response > 2.0:  # 2 seconds
                        health_score -= 10
                        issues.append(f"Slow response times: {avg_response:.2f}s")
                        recommendations.append("Optimize API calls and implement better caching")

                # Update system health
                self._system_health['overall_score'] = max(0, health_score)
                self._system_health['issues_detected'] = issues
                self._system_health['recommendations'] = recommendations
                self._system_health['last_check'] = time.time()

                # Log health status
                if health_score < 70:
                    self.logger.log_event("MONITORING", "WARNING",
                        f"⚠️ System health degraded: {health_score:.1f}/100")
                elif health_score < 50:
                    self.logger.log_event("MONITORING", "ERROR",
                        f"❌ System health critical: {health_score:.1f}/100")

                await asyncio.sleep(300)  # Update every 5 minutes

            except Exception as e:
                self.logger.log_event("MONITORING", "ERROR", f"❌ System health update error: {e}")
                await asyncio.sleep(300)

    async def _cleanup_old_data(self):
        """Clean up old monitoring data"""
        while self._is_running:
            try:
                # Clean up old database records (older than 30 days)
                cutoff_time = time.time() - (30 * 24 * 3600)

                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                cursor.execute("DELETE FROM performance_metrics WHERE timestamp < ?", (cutoff_time,))
                cursor.execute("DELETE FROM system_alerts WHERE timestamp < ? AND resolved = 1", (cutoff_time,))
                cursor.execute("DELETE FROM system_health WHERE timestamp < ?", (cutoff_time,))

                conn.commit()
                conn.close()

                await asyncio.sleep(3600)  # Clean up every hour

            except Exception as e:
                self.logger.log_event("MONITORING", "ERROR", f"❌ Data cleanup error: {e}")
                await asyncio.sleep(3600)

    async def _measure_network_latency(self) -> float:
        """Measure network latency to Binance"""
        try:
            import socket
            start_time = time.time()

            # Try to connect to Binance API
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect(('api.binance.com', 443))
            sock.close()

            return (time.time() - start_time) * 1000  # Convert to milliseconds

        except Exception:
            return 9999.0  # Return high latency if connection fails

    async def _create_alert(self, alert_type: str, severity: str, message: str):
        """Create and store an alert"""
        current_time = time.time()

        # Check cooldown to prevent spam
        if current_time - self._last_alert_time.get(alert_type, 0) < self._alert_cooldown:
            return

        alert = {
            'type': alert_type,
            'severity': severity,
            'message': message,
            'timestamp': current_time
        }

        self._alerts.append(alert)
        self._last_alert_time[alert_type] = current_time

        # Store in database
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO system_alerts (timestamp, alert_type, severity, message) VALUES (?, ?, ?, ?)",
                (current_time, alert_type, severity, message)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            self.logger.log_event("MONITORING", "ERROR", f"❌ Failed to store alert: {e}")

        # Log alert
        self.logger.log_event("MONITORING", severity, f"🚨 {message}")

        # Trigger callbacks
        for callback in self._alert_callbacks:
            try:
                await callback(alert)
            except Exception as e:
                self.logger.log_event("MONITORING", "ERROR", f"❌ Alert callback error: {e}")

    def add_alert_callback(self, callback: Callable):
        """Add a callback function for alerts"""
        self._alert_callbacks.append(callback)

    def record_metric(self, metric_type: str, metric_name: str, value: float, threshold: float | None = None):
        """Record a performance metric"""
        try:
            # Store in memory
            if metric_type == 'response_time':
                self._performance_metrics['response_times'].append(value)
            elif metric_type == 'error_rate':
                self._performance_metrics['error_rates'][metric_name].append(1 if value > 0 else 0)
            elif metric_type == 'success_rate':
                self._performance_metrics['success_rates'][metric_name].append(value)

            # Store in database
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO performance_metrics (timestamp, metric_type, metric_name, value, threshold, is_anomaly) VALUES (?, ?, ?, ?, ?, ?)",
                (time.time(), metric_type, metric_name, value, threshold or 0,
                 threshold and value > threshold)
            )
            conn.commit()
            conn.close()

        except Exception as e:
            self.logger.log_event("MONITORING", "ERROR", f"❌ Failed to record metric: {e}")

    def get_system_health(self) -> dict[str, Any]:
        """Get current system health status"""
        return self._system_health.copy()

    def get_performance_summary(self) -> dict[str, Any]:
        """Get performance metrics summary"""
        summary = {}

        for metric_name, values in self._performance_metrics.items():
            if values:
                summary[metric_name] = {
                    'current': values[-1] if values else 0,
                    'average': statistics.mean(values),
                    'min': min(values),
                    'max': max(values),
                    'count': len(values)
                }

        return summary

    def get_recent_alerts(self, hours: int = 24) -> list[dict[str, Any]]:
        """Get recent alerts from the last N hours"""
        cutoff_time = time.time() - (hours * 3600)
        return [alert for alert in self._alerts if alert['timestamp'] > cutoff_time]


# Keep the original Monitoring class for backward compatibility
class Monitoring(AdvancedMonitor):
    """Backward compatibility wrapper"""
    pass
