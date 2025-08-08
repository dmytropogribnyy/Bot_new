#!/usr/bin/env python3
"""
Performance Monitor для системы стратегий
Отслеживает производительность стратегий и предоставляет аналитику
"""

import json
from datetime import datetime, timedelta
from typing import Any

import pandas as pd


class StrategyPerformanceMonitor:
    """Монитор производительности стратегий с детальной аналитикой"""

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.performance_data = {}
        self.alerts = []

        # Параметры мониторинга
        self.min_trades_for_analysis = 10
        self.alert_thresholds = {
            "low_win_rate": 0.4,
            "negative_pnl": -0.001,
            "high_drawdown": -0.05,
            "low_roi": -0.02
        }

    async def update_strategy_performance(self, strategy_name: str, trade_data: dict[str, Any]):
        """Обновляет данные производительности стратегии"""
        try:
            if strategy_name not in self.performance_data:
                self.performance_data[strategy_name] = {
                    "trades": [],
                    "metrics": {
                        "total_trades": 0,
                        "win_rate": 0.0,
                        "avg_pnl": 0.0,
                        "total_pnl": 0.0,
                        "roi": 0.0,
                        "max_drawdown": 0.0,
                        "best_trade": 0.0,
                        "worst_trade": 0.0,
                        "avg_trade_duration": 0.0,
                        "sharpe_ratio": 0.0
                    },
                    "last_updated": datetime.utcnow()
                }

            # Добавляем сделку
            self.performance_data[strategy_name]["trades"].append(trade_data)

            # Пересчитываем метрики
            await self._recalculate_metrics(strategy_name)

            # Проверяем алерты
            await self._check_alerts(strategy_name)

        except Exception as e:
            self.logger.log_event(
                "PERFORMANCE_MONITOR", "ERROR",
                f"Failed to update performance for {strategy_name}: {e}"
            )

    async def _recalculate_metrics(self, strategy_name: str):
        """Пересчитывает метрики производительности"""
        try:
            data = self.performance_data[strategy_name]
            trades = data["trades"]

            if len(trades) < 1:
                return

            # Базовые метрики
            total_trades = len(trades)
            winning_trades = [t for t in trades if t.get("pnl", 0) > 0]
            win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0.0

            # PnL метрики
            pnl_values = [t.get("pnl", 0) for t in trades]
            total_pnl = sum(pnl_values)
            avg_pnl = total_pnl / total_trades if total_trades > 0 else 0.0

            # ROI
            total_investment = sum(t.get("investment", 0) for t in trades)
            roi = (total_pnl / total_investment * 100) if total_investment > 0 else 0.0

            # Drawdown
            cumulative_pnl = []
            running_total = 0
            for pnl in pnl_values:
                running_total += pnl
                cumulative_pnl.append(running_total)

            max_drawdown = min(cumulative_pnl) if cumulative_pnl else 0.0

            # Другие метрики
            best_trade = max(pnl_values) if pnl_values else 0.0
            worst_trade = min(pnl_values) if pnl_values else 0.0

            # Средняя продолжительность сделки
            durations = [t.get("duration", 0) for t in trades]
            avg_duration = sum(durations) / len(durations) if durations else 0.0

            # Sharpe Ratio (упрощенный)
            if len(pnl_values) > 1:
                returns_std = pd.Series(pnl_values).std()
                sharpe_ratio = (avg_pnl / returns_std) if returns_std > 0 else 0.0
            else:
                sharpe_ratio = 0.0

            # Обновляем метрики
            data["metrics"].update({
                "total_trades": total_trades,
                "win_rate": win_rate,
                "avg_pnl": avg_pnl,
                "total_pnl": total_pnl,
                "roi": roi,
                "max_drawdown": max_drawdown,
                "best_trade": best_trade,
                "worst_trade": worst_trade,
                "avg_trade_duration": avg_duration,
                "sharpe_ratio": sharpe_ratio
            })

            data["last_updated"] = datetime.utcnow()

        except Exception as e:
            self.logger.log_event(
                "PERFORMANCE_MONITOR", "ERROR",
                f"Failed to recalculate metrics for {strategy_name}: {e}"
            )

    async def _check_alerts(self, strategy_name: str):
        """Проверяет условия для алертов"""
        try:
            metrics = self.performance_data[strategy_name]["metrics"]

            if metrics["total_trades"] < self.min_trades_for_analysis:
                return

            alerts = []

            # Проверяем win rate
            if metrics["win_rate"] < self.alert_thresholds["low_win_rate"]:
                alerts.append(f"Low win rate: {metrics['win_rate']:.1%}")

            # Проверяем PnL
            if metrics["avg_pnl"] < self.alert_thresholds["negative_pnl"]:
                alerts.append(f"Negative PnL: {metrics['avg_pnl']:.4f}")

            # Проверяем drawdown
            if metrics["max_drawdown"] < self.alert_thresholds["high_drawdown"]:
                alerts.append(f"High drawdown: {metrics['max_drawdown']:.2%}")

            # Проверяем ROI
            if metrics["roi"] < self.alert_thresholds["low_roi"]:
                alerts.append(f"Low ROI: {metrics['roi']:.2%}")

            if alerts:
                alert_message = f"⚠️ Strategy Alert - {strategy_name}:\n" + "\n".join(alerts)
                self.alerts.append({
                    "timestamp": datetime.utcnow(),
                    "strategy": strategy_name,
                    "alerts": alerts,
                    "metrics": metrics
                })

                self.logger.log_event("PERFORMANCE_MONITOR", "WARNING", alert_message)

        except Exception as e:
            self.logger.log_event(
                "PERFORMANCE_MONITOR", "ERROR",
                f"Failed to check alerts for {strategy_name}: {e}"
            )

    async def get_performance_report(self, strategy_name: str | None = None) -> dict[str, Any]:
        """Генерирует отчет о производительности"""
        try:
            if strategy_name:
                if strategy_name not in self.performance_data:
                    return {"error": f"Strategy {strategy_name} not found"}

                data = self.performance_data[strategy_name]
                return {
                    "strategy": strategy_name,
                    "metrics": data["metrics"],
                    "recent_trades": data["trades"][-10:],  # Последние 10 сделок
                    "last_updated": data["last_updated"]
                }
            else:
                # Общий отчет по всем стратегиям
                report = {
                    "summary": {},
                    "strategies": {},
                    "alerts": self.alerts[-10:],  # Последние 10 алертов
                    "recommendations": []
                }

                total_trades = 0
                total_pnl = 0.0
                best_strategy = None
                worst_strategy = None

                for name, data in self.performance_data.items():
                    metrics = data["metrics"]
                    report["strategies"][name] = metrics

                    total_trades += metrics["total_trades"]
                    total_pnl += metrics["total_pnl"]

                    # Находим лучшую и худшую стратегии
                    if best_strategy is None or metrics["roi"] > report["strategies"][best_strategy]["roi"]:
                        best_strategy = name
                    if worst_strategy is None or metrics["roi"] < report["strategies"][worst_strategy]["roi"]:
                        worst_strategy = name

                # Общая сводка
                report["summary"] = {
                    "total_strategies": len(self.performance_data),
                    "total_trades": total_trades,
                    "total_pnl": total_pnl,
                    "best_strategy": best_strategy,
                    "worst_strategy": worst_strategy
                }

                # Рекомендации
                if best_strategy:
                    report["recommendations"].append(f"✅ Лучшая стратегия: {best_strategy}")
                if worst_strategy:
                    report["recommendations"].append(f"⚠️ Требует внимания: {worst_strategy}")

                return report

        except Exception as e:
            self.logger.log_event(
                "PERFORMANCE_MONITOR", "ERROR",
                f"Failed to generate performance report: {e}"
            )
            return {"error": str(e)}

    async def export_performance_data(self, filepath: str):
        """Экспортирует данные производительности в файл"""
        try:
            export_data = {
                "export_timestamp": datetime.utcnow().isoformat(),
                "performance_data": self.performance_data,
                "alerts": self.alerts
            }

            with open(filepath, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)

            self.logger.log_event(
                "PERFORMANCE_MONITOR", "INFO",
                f"Performance data exported to {filepath}"
            )

        except Exception as e:
            self.logger.log_event(
                "PERFORMANCE_MONITOR", "ERROR",
                f"Failed to export performance data: {e}"
            )

    async def cleanup_old_data(self, days_to_keep: int = 30):
        """Очищает старые данные производительности"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)

            for strategy_name, data in self.performance_data.items():
                # Очищаем старые сделки
                data["trades"] = [
                    trade for trade in data["trades"]
                    if trade.get("timestamp", datetime.min) > cutoff_date
                ]

                # Пересчитываем метрики
                await self._recalculate_metrics(strategy_name)

            # Очищаем старые алерты
            self.alerts = [
                alert for alert in self.alerts
                if alert["timestamp"] > cutoff_date
            ]

            self.logger.log_event(
                "PERFORMANCE_MONITOR", "INFO",
                f"Cleaned up data older than {days_to_keep} days"
            )

        except Exception as e:
            self.logger.log_event(
                "PERFORMANCE_MONITOR", "ERROR",
                f"Failed to cleanup old data: {e}"
            )
