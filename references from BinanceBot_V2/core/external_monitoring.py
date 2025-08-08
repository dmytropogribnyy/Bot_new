"""
External Monitoring System Integration

This module provides integration with external monitoring systems like Prometheus/Grafana,
allowing the bot to export metrics for external monitoring and alerting.
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import aiohttp
import logging

from .unified_logger import UnifiedLogger
from .metrics_aggregator import MetricsAggregator
from .performance_monitor import PerformanceMonitor


class ExternalMonitoring:
    """
    Handles integration with external monitoring systems.

    Supports:
    - Prometheus metrics export
    - Grafana dashboard data
    - Custom HTTP endpoints
    - Webhook notifications
    """

    def __init__(self, config: Dict[str, Any], logger: UnifiedLogger):
        self.config = config
        self.logger = logger
        self.metrics_aggregator = None
        self.performance_monitor = None

        # External monitoring settings
        self.enabled = config.get('external_monitoring', {}).get('enabled', False)
        self.export_interval = config.get('external_monitoring', {}).get('export_interval', 60)
        self.prometheus_enabled = config.get('external_monitoring', {}).get('prometheus', {}).get('enabled', False)
        self.grafana_enabled = config.get('external_monitoring', {}).get('grafana', {}).get('enabled', False)
        self.webhook_enabled = config.get('external_monitoring', {}).get('webhook', {}).get('enabled', False)

        # Prometheus settings
        self.prometheus_url = config.get('external_monitoring', {}).get('prometheus', {}).get('url', '')
        self.prometheus_job = config.get('external_monitoring', {}).get('prometheus', {}).get('job_name', 'binance_bot')

        # Grafana settings
        self.grafana_url = config.get('external_monitoring', {}).get('grafana', {}).get('url', '')
        self.grafana_api_key = config.get('external_monitoring', {}).get('grafana', {}).get('api_key', '')

        # Webhook settings
        self.webhook_url = config.get('external_monitoring', {}).get('webhook', {}).get('url', '')
        self.webhook_headers = config.get('external_monitoring', {}).get('webhook', {}).get('headers', {})

        # Export task
        self.export_task = None
        self.running = False

        self.logger.log_runtime_status(
            "EXTERNAL_MONITORING_INIT",
            f"External monitoring {'enabled' if self.enabled else 'disabled'}. "
            f"Prometheus: {'enabled' if self.prometheus_enabled else 'disabled'}, "
            f"Grafana: {'enabled' if self.grafana_enabled else 'disabled'}, "
            f"Webhook: {'enabled' if self.webhook_enabled else 'disabled'}"
        )

    def set_dependencies(self, metrics_aggregator: MetricsAggregator, performance_monitor: PerformanceMonitor):
        """Set required dependencies."""
        self.metrics_aggregator = metrics_aggregator
        self.performance_monitor = performance_monitor

    async def start(self):
        """Start the external monitoring export task."""
        if not self.enabled:
            return

        self.running = True
        self.export_task = asyncio.create_task(self._export_loop())

        self.logger.log_runtime_status(
            "EXTERNAL_MONITORING_STARTED",
            f"Export interval: {self.export_interval}s"
        )

    async def stop(self):
        """Stop the external monitoring export task."""
        if not self.enabled or not self.running:
            return

        self.running = False
        if self.export_task:
            self.export_task.cancel()
            try:
                await self.export_task
            except asyncio.CancelledError:
                pass

        self.logger.log_runtime_status("EXTERNAL_MONITORING_STOPPED")

    async def _export_loop(self):
        """Main export loop that runs at specified intervals."""
        while self.running:
            try:
                await self._export_metrics()
                await asyncio.sleep(self.export_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.log_runtime_status(
                    "EXTERNAL_MONITORING_ERROR",
                    f"Export error: {str(e)}"
                )
                await asyncio.sleep(10)  # Wait before retry

    async def _export_metrics(self):
        """Export metrics to all enabled external systems."""
        if not self.metrics_aggregator or not self.performance_monitor:
            return

        # Gather metrics
        metrics = await self._gather_metrics()

        # Export to enabled systems
        tasks = []

        if self.prometheus_enabled:
            tasks.append(self._export_to_prometheus(metrics))

        if self.grafana_enabled:
            tasks.append(self._export_to_grafana(metrics))

        if self.webhook_enabled:
            tasks.append(self._export_to_webhook(metrics))

        # Execute all exports concurrently
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Log results
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.log_runtime_status(
                        "EXTERNAL_MONITORING_EXPORT_ERROR",
                        f"Export {i+1} failed: {str(result)}"
                    )
                else:
                    self.logger.log_runtime_status(
                        "EXTERNAL_MONITORING_EXPORT_SUCCESS",
                        f"Export {i+1} completed successfully"
                    )

    async def _gather_metrics(self) -> Dict[str, Any]:
        """Gather all metrics for export."""
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'bot_status': 'running',
            'trading_metrics': {},
            'performance_metrics': {},
            'system_metrics': {}
        }

        try:
            # Trading metrics
            trading_summary = await self.metrics_aggregator.get_performance_summary('24h')
            metrics['trading_metrics'] = trading_summary

            # Performance metrics
            if self.performance_monitor:
                performance_summary = await self.performance_monitor.get_performance_summary('24h')
                metrics['performance_metrics'] = performance_summary

            # System metrics
            metrics['system_metrics'] = {
                'memory_usage': self._get_memory_usage(),
                'cpu_usage': self._get_cpu_usage(),
                'uptime': self._get_uptime()
            }

        except Exception as e:
            self.logger.log_runtime_status(
                "EXTERNAL_MONITORING_GATHER_ERROR",
                f"Error gathering metrics: {str(e)}"
            )

        return metrics

    def _get_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage."""
        try:
            import psutil
            memory = psutil.virtual_memory()
            return {
                'total_gb': memory.total / (1024**3),
                'used_gb': memory.used / (1024**3),
                'available_gb': memory.available / (1024**3),
                'percent': memory.percent
            }
        except ImportError:
            return {'error': 'psutil not available'}
        except Exception:
            return {'error': 'Failed to get memory usage'}

    def _get_cpu_usage(self) -> Dict[str, float]:
        """Get current CPU usage."""
        try:
            import psutil
            cpu_percent = psutil.cpu_percent(interval=1)
            return {
                'percent': cpu_percent,
                'count': psutil.cpu_count()
            }
        except ImportError:
            return {'error': 'psutil not available'}
        except Exception:
            return {'error': 'Failed to get CPU usage'}

    def _get_uptime(self) -> Dict[str, Any]:
        """Get bot uptime."""
        try:
            import psutil
            process = psutil.Process()
            create_time = process.create_time()
            uptime_seconds = time.time() - create_time

            return {
                'seconds': uptime_seconds,
                'hours': uptime_seconds / 3600,
                'days': uptime_seconds / (3600 * 24)
            }
        except Exception:
            return {'error': 'Failed to get uptime'}

    async def _export_to_prometheus(self, metrics: Dict[str, Any]):
        """Export metrics to Prometheus."""
        if not self.prometheus_url:
            return

        try:
            prometheus_metrics = self._format_prometheus_metrics(metrics)

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.prometheus_url,
                    data=prometheus_metrics,
                    headers={'Content-Type': 'text/plain'}
                ) as response:
                    if response.status != 200:
                        raise Exception(f"Prometheus export failed: {response.status}")

        except Exception as e:
            raise Exception(f"Prometheus export error: {str(e)}")

    def _format_prometheus_metrics(self, metrics: Dict[str, Any]) -> str:
        """Format metrics for Prometheus export."""
        lines = []

        # Add job label
        job_label = f'job="{self.prometheus_job}"'

        # Trading metrics
        if 'trading_metrics' in metrics:
            trading = metrics['trading_metrics']

            if 'total_trades' in trading:
                lines.append(f'binance_bot_trades_total{{{job_label}}} {trading["total_trades"]}')

            if 'win_rate' in trading:
                lines.append(f'binance_bot_win_rate{{{job_label}}} {trading["win_rate"]}')

            if 'total_pnl' in trading:
                lines.append(f'binance_bot_total_pnl{{{job_label}}} {trading["total_pnl"]}')

            if 'profit_factor' in trading:
                lines.append(f'binance_bot_profit_factor{{{job_label}}} {trading["profit_factor"]}')

            if 'sharpe_ratio' in trading:
                lines.append(f'binance_bot_sharpe_ratio{{{job_label}}} {trading["sharpe_ratio"]}')

        # System metrics
        if 'system_metrics' in metrics:
            system = metrics['system_metrics']

            if 'memory_usage' in system and 'percent' in system['memory_usage']:
                lines.append(f'binance_bot_memory_usage_percent{{{job_label}}} {system["memory_usage"]["percent"]}')

            if 'cpu_usage' in system and 'percent' in system['cpu_usage']:
                lines.append(f'binance_bot_cpu_usage_percent{{{job_label}}} {system["cpu_usage"]["percent"]}')

            if 'uptime' in system and 'hours' in system['uptime']:
                lines.append(f'binance_bot_uptime_hours{{{job_label}}} {system["uptime"]["hours"]}')

        return '\n'.join(lines)

    async def _export_to_grafana(self, metrics: Dict[str, Any]):
        """Export metrics to Grafana."""
        if not self.grafana_url or not self.grafana_api_key:
            return

        try:
            grafana_data = self._format_grafana_data(metrics)

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.grafana_url}/api/datasources/proxy/1/api/v1/write",
                    json=grafana_data,
                    headers={
                        'Authorization': f'Bearer {self.grafana_api_key}',
                        'Content-Type': 'application/json'
                    }
                ) as response:
                    if response.status not in [200, 201, 204]:
                        raise Exception(f"Grafana export failed: {response.status}")

        except Exception as e:
            raise Exception(f"Grafana export error: {str(e)}")

    def _format_grafana_data(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Format metrics for Grafana export."""
        return {
            'timestamp': metrics.get('timestamp'),
            'bot_status': metrics.get('bot_status'),
            'trading_metrics': metrics.get('trading_metrics', {}),
            'performance_metrics': metrics.get('performance_metrics', {}),
            'system_metrics': metrics.get('system_metrics', {})
        }

    async def _export_to_webhook(self, metrics: Dict[str, Any]):
        """Export metrics to webhook endpoint."""
        if not self.webhook_url:
            return

        try:
            webhook_data = self._format_webhook_data(metrics)

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=webhook_data,
                    headers=self.webhook_headers
                ) as response:
                    if response.status not in [200, 201, 204]:
                        raise Exception(f"Webhook export failed: {response.status}")

        except Exception as e:
            raise Exception(f"Webhook export error: {str(e)}")

    def _format_webhook_data(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Format metrics for webhook export."""
        return {
            'event_type': 'metrics_export',
            'timestamp': metrics.get('timestamp'),
            'bot_status': metrics.get('bot_status'),
            'metrics': metrics
        }

    async def get_status(self) -> Dict[str, Any]:
        """Get external monitoring status."""
        return {
            'enabled': self.enabled,
            'running': self.running,
            'export_interval': self.export_interval,
            'prometheus_enabled': self.prometheus_enabled,
            'grafana_enabled': self.grafana_enabled,
            'webhook_enabled': self.webhook_enabled,
            'last_export': getattr(self, '_last_export_time', None)
        }

    async def manual_export(self) -> bool:
        """Trigger a manual metrics export."""
        if not self.enabled:
            return False

        try:
            await self._export_metrics()
            self._last_export_time = datetime.now()
            return True
        except Exception as e:
            self.logger.log_runtime_status(
                "EXTERNAL_MONITORING_MANUAL_EXPORT_ERROR",
                f"Manual export failed: {str(e)}"
            )
            return False
