# core/performance_monitor.py

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from core.metrics_aggregator import MetricsAggregator


class PerformanceMonitor:
    """Система мониторинга производительности торговли"""

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.db_path = Path("data/trading_log.db")

        # Инициализируем MetricsAggregator для устранения дублирования логики
        self.metrics_aggregator = MetricsAggregator(config, logger)

        # Периоды для отчетов
        self.periods = {
            "1h": timedelta(hours=1),
            "4h": timedelta(hours=4),
            "1d": timedelta(days=1),
            "1w": timedelta(weeks=1),
            "1m": timedelta(days=30),
            "3m": timedelta(days=90),
            "6m": timedelta(days=180),
            "1y": timedelta(days=365),
        }

        # Целевые показатели
        self.targets = {
            "min_hourly_profit_usd": 2.0,
            "target_win_rate": 0.55,
            "max_drawdown_percent": 3.0,
            "min_trades_per_hour": 3,
        }

    async def get_performance_summary(self, period: str = "1d") -> dict[str, Any]:
        """Получает сводку производительности за период используя MetricsAggregator"""
        try:
            if period not in self.periods:
                period = "1d"

            # Используем MetricsAggregator вместо дублирования логики
            summary = await self.metrics_aggregator.get_performance_summary(period)

            # Добавляем статус целей
            summary["targets_status"] = self._check_targets_status(summary)

            return summary

        except Exception as e:
            self.logger.log_event(
                "PERFORMANCE_MONITOR", "ERROR", f"Failed to get performance summary: {e}"
            )
            return self._empty_summary(period)

    async def get_detailed_report(self, period: str = "1d", format: str = "json") -> str:
        """Генерирует детальный отчет"""
        try:
            summary = await self.get_performance_summary(period)

            if format == "csv":
                return self._generate_csv_report(summary)
            elif format == "json":
                return json.dumps(summary, indent=2)
            else:
                return self._generate_text_report(summary)

        except Exception as e:
            self.logger.log_event("PERFORMANCE_MONITOR", "ERROR", f"Failed to generate report: {e}")
            return f"Error generating report: {e}"

    async def get_symbol_performance(self, symbol: str, period: str = "1d") -> dict[str, Any]:
        """Получает производительность по конкретному символу"""
        try:
            start_time = datetime.utcnow() - self.periods.get(period, self.periods["1d"])

            trades_df = await self._get_trades_since(start_time)
            symbol_trades = trades_df[trades_df["symbol"] == symbol]

            if symbol_trades.empty:
                return {
                    "symbol": symbol,
                    "period": period,
                    "total_trades": 0,
                    "win_rate": 0,
                    "total_pnl": 0,
                    "avg_pnl": 0,
                }

            return {
                "symbol": symbol,
                "period": period,
                "total_trades": len(symbol_trades),
                "winning_trades": len(symbol_trades[symbol_trades["pnl"] > 0]),
                "losing_trades": len(symbol_trades[symbol_trades["pnl"] < 0]),
                "win_rate": len(symbol_trades[symbol_trades["pnl"] > 0]) / len(symbol_trades),
                "total_pnl": symbol_trades["pnl"].sum(),
                "avg_pnl": symbol_trades["pnl"].mean(),
                "max_profit": symbol_trades["pnl"].max(),
                "max_loss": symbol_trades["pnl"].min(),
                "profit_factor": self._calculate_profit_factor(symbol_trades),
            }

        except Exception as e:
            self.logger.log_event(
                "PERFORMANCE_MONITOR", "ERROR", f"Failed to get symbol performance: {e}"
            )
            return {}

    async def get_strategy_performance(
        self, strategy_name: str, period: str = "1d"
    ) -> dict[str, Any]:
        """Получает производительность по стратегии"""
        try:
            start_time = datetime.utcnow() - self.periods.get(period, self.periods["1d"])

            trades_df = await self._get_trades_since(start_time)
            strategy_trades = trades_df[trades_df["strategy"] == strategy_name]

            if strategy_trades.empty:
                return {
                    "strategy": strategy_name,
                    "period": period,
                    "total_trades": 0,
                    "win_rate": 0,
                    "total_pnl": 0,
                    "avg_pnl": 0,
                }

            return {
                "strategy": strategy_name,
                "period": period,
                "total_trades": len(strategy_trades),
                "winning_trades": len(strategy_trades[strategy_trades["pnl"] > 0]),
                "losing_trades": len(strategy_trades[strategy_trades["pnl"] < 0]),
                "win_rate": len(strategy_trades[strategy_trades["pnl"] > 0]) / len(strategy_trades),
                "total_pnl": strategy_trades["pnl"].sum(),
                "avg_pnl": strategy_trades["pnl"].mean(),
                "max_profit": strategy_trades["pnl"].max(),
                "max_loss": strategy_trades["pnl"].min(),
                "profit_factor": self._calculate_profit_factor(strategy_trades),
            }

        except Exception as e:
            self.logger.log_event(
                "PERFORMANCE_MONITOR", "ERROR", f"Failed to get strategy performance: {e}"
            )
            return {}

    async def export_performance_data(self, period: str = "1m", format: str = "csv") -> str:
        """Экспортирует данные производительности"""
        try:
            start_time = datetime.utcnow() - self.periods.get(period, self.periods["1m"])
            trades_df = await self._get_trades_since(start_time)

            if trades_df.empty:
                return "No data to export"

            # Создаем директорию для экспорта
            export_dir = Path("data/exports")
            export_dir.mkdir(exist_ok=True)

            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

            if format == "csv":
                filename = f"performance_export_{period}_{timestamp}.csv"
                filepath = export_dir / filename
                trades_df.to_csv(filepath, index=False)
                return f"Data exported to {filepath}"

            elif format == "json":
                filename = f"performance_export_{period}_{timestamp}.json"
                filepath = export_dir / filename
                trades_df.to_json(filepath, orient="records", indent=2)
                return f"Data exported to {filepath}"

            else:
                return "Unsupported format"

        except Exception as e:
            self.logger.log_event("PERFORMANCE_MONITOR", "ERROR", f"Failed to export data: {e}")
            return f"Export failed: {e}"

    async def _get_trades_since(self, start_time: datetime) -> pd.DataFrame:
        """Получает сделки с указанного времени"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = """
                SELECT
                    timestamp, symbol, side, qty, entry_price, reason
                FROM trades
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
                """

                df = pd.read_sql_query(query, conn, params=(start_time.isoformat(),))

                if not df.empty:
                    df["timestamp"] = pd.to_datetime(df["timestamp"])
                    # Добавляем заглушки для отсутствующих колонок
                    df["pnl"] = 0.0  # Заглушка
                    df["win"] = True  # Заглушка
                    df["strategy"] = "scalping"  # Заглушка
                    df["exit_price"] = df["entry_price"]  # Заглушка

                return df

        except Exception as e:
            self.logger.log_event("PERFORMANCE_MONITOR", "ERROR", f"Failed to get trades: {e}")
            return pd.DataFrame()

    def _calculate_profit_factor(self, df: pd.DataFrame) -> float:
        """Рассчитывает фактор прибыли"""
        if df.empty:
            return 0.0

        gross_profit = df[df["pnl"] > 0]["pnl"].sum()
        gross_loss = abs(df[df["pnl"] < 0]["pnl"].sum())

        return gross_profit / gross_loss if gross_loss > 0 else float("inf")

    def _calculate_sharpe_ratio(self, df: pd.DataFrame) -> float:
        """Рассчитывает коэффициент Шарпа"""
        if df.empty or len(df) < 2:
            return 0.0

        returns = df["pnl"].pct_change().dropna()
        if len(returns) == 0:
            return 0.0

        return returns.mean() / returns.std() if returns.std() > 0 else 0.0

    def _calculate_max_drawdown(self, df: pd.DataFrame) -> float:
        """Рассчитывает максимальную просадку"""
        if df.empty:
            return 0.0

        cumulative = df["pnl"].cumsum()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max * 100

        return abs(drawdown.min()) if len(drawdown) > 0 else 0.0

    def _check_targets_status(self, summary: dict[str, Any]) -> dict[str, Any]:
        """Проверяет статус целевых показателей"""
        status = {}

        # Проверяем часовую прибыль
        if summary["period"] == "1h":
            status["hourly_profit"] = {
                "target": self.targets["min_hourly_profit_usd"],
                "actual": summary["total_pnl"],
                "achieved": summary["total_pnl"] >= self.targets["min_hourly_profit_usd"],
            }

        # Проверяем win rate
        status["win_rate"] = {
            "target": self.targets["target_win_rate"],
            "actual": summary["win_rate"],
            "achieved": summary["win_rate"] >= self.targets["target_win_rate"],
        }

        # Проверяем просадку
        status["drawdown"] = {
            "target": self.targets["max_drawdown_percent"],
            "actual": summary["max_drawdown"],
            "achieved": summary["max_drawdown"] <= self.targets["max_drawdown_percent"],
        }

        # Проверяем количество сделок в час
        if summary["period"] == "1h":
            status["trades_per_hour"] = {
                "target": self.targets["min_trades_per_hour"],
                "actual": summary["trades_per_hour"],
                "achieved": summary["trades_per_hour"] >= self.targets["min_trades_per_hour"],
            }

        return status

    def _empty_summary(self, period: str) -> dict[str, Any]:
        """Возвращает пустую сводку"""
        return {
            "period": period,
            "start_time": (datetime.utcnow() - self.periods[period]).isoformat(),
            "end_time": datetime.utcnow().isoformat(),
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0,
            "total_pnl": 0,
            "avg_pnl": 0,
            "max_profit": 0,
            "max_loss": 0,
            "profit_factor": 0,
            "sharpe_ratio": 0,
            "max_drawdown": 0,
            "trades_per_hour": 0,
            "best_symbol": None,
            "worst_symbol": None,
            "targets_status": {},
        }

    def _generate_text_report(self, summary: dict[str, Any]) -> str:
        """Генерирует текстовый отчет"""
        report = f"""
📊 Performance Report ({summary['period']})

📈 Trading Statistics:
• Total Trades: {summary['total_trades']}
• Win Rate: {summary['win_rate']:.1%}
• Total PnL: ${summary['total_pnl']:.2f}
• Average PnL: ${summary['avg_pnl']:.2f}
• Max Profit: ${summary['max_profit']:.2f}
• Max Loss: ${summary['max_loss']:.2f}
• Profit Factor: {summary['profit_factor']:.2f}
• Sharpe Ratio: {summary['sharpe_ratio']:.2f}
• Max Drawdown: {summary['max_drawdown']:.1f}%

🎯 Target Status:
"""

        for target_name, target_data in summary["targets_status"].items():
            status_emoji = "✅" if target_data["achieved"] else "❌"
            report += f"• {target_name}: {status_emoji} {target_data['actual']:.2f}/{target_data['target']:.2f}\n"

        if summary["best_symbol"]:
            report += f"\n🏆 Best Symbol: {summary['best_symbol']}"
        if summary["worst_symbol"]:
            report += f"\n📉 Worst Symbol: {summary['worst_symbol']}"

        return report

    def _generate_csv_report(self, summary: dict[str, Any]) -> str:
        """Генерирует CSV отчет"""
        # Создаем DataFrame для экспорта
        data = {"metric": list(summary.keys()), "value": list(summary.values())}
        df = pd.DataFrame(data)

        # Сохраняем во временный файл
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"performance_report_{summary['period']}_{timestamp}.csv"
        filepath = Path("data/exports") / filename
        filepath.parent.mkdir(exist_ok=True)

        df.to_csv(filepath, index=False)
        return f"CSV report saved to {filepath}"
