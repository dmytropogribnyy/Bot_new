"""
Централизованный агрегатор метрик для устранения дублирования логики
"""

import sqlite3
import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import json


@dataclass
class TradingMetrics:
    """Метрики торговли"""
    total_trades: int
    win_rate: float
    total_pnl: float
    avg_pnl: float
    max_profit: float
    max_loss: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    trades_per_hour: float
    avg_trade_duration: float
    best_symbol: Optional[str]
    worst_symbol: Optional[str]
    targets_status: Dict[str, Dict[str, Any]]


@dataclass
class SymbolMetrics:
    """Метрики по символу"""
    symbol: str
    total_trades: int
    win_rate: float
    total_pnl: float
    avg_pnl: float
    max_profit: float
    max_loss: float
    profit_factor: float
    avg_trade_duration: float
    best_strategy: Optional[str]
    worst_strategy: Optional[str]


class MetricsAggregator:
    """Централизованный агрегатор метрик"""

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.db_path = config.get('database_path', 'trading_data.db')
        self.cache = {}
        self.cache_ttl = 300  # 5 минут

    async def get_performance_summary(self, period: str = "1d") -> Dict[str, Any]:
        """Получает сводку производительности за период"""
        cache_key = f"performance_summary_{period}"

        # Проверяем кеш
        if cache_key in self.cache:
            cache_time, data = self.cache[cache_key]
            if (datetime.now() - cache_time).seconds < self.cache_ttl:
                return data

        try:
            # Получаем базовые метрики
            metrics = await self.get_trading_metrics(period)

            # Получаем статус целей
            targets_status = await self._get_targets_status(period)

            # Формируем сводку
            summary = {
                'total_trades': metrics.total_trades,
                'win_rate': metrics.win_rate,
                'total_pnl': metrics.total_pnl,
                'avg_pnl': metrics.avg_pnl,
                'max_profit': metrics.max_profit,
                'max_loss': metrics.max_loss,
                'profit_factor': metrics.profit_factor,
                'sharpe_ratio': metrics.sharpe_ratio,
                'max_drawdown': metrics.max_drawdown,
                'trades_per_hour': metrics.trades_per_hour,
                'avg_trade_duration': metrics.avg_trade_duration,
                'best_symbol': metrics.best_symbol,
                'worst_symbol': metrics.worst_symbol,
                'targets_status': targets_status
            }

            # Кешируем результат
            self.cache[cache_key] = (datetime.now(), summary)

            return summary

        except Exception as e:
            self.logger.log_event("METRICS_AGGREGATOR", "ERROR", f"Failed to get performance summary: {e}")
            return {}

    async def get_trading_metrics(self, period: str = "1d") -> TradingMetrics:
        """Получает метрики торговли за период"""
        try:
            # Определяем временной интервал
            end_time = datetime.now()
            if period == "1h":
                start_time = end_time - timedelta(hours=1)
            elif period == "1d":
                start_time = end_time - timedelta(days=1)
            elif period == "7d":
                start_time = end_time - timedelta(days=7)
            elif period == "30d":
                start_time = end_time - timedelta(days=30)
            else:
                start_time = end_time - timedelta(days=1)

            # Подключаемся к БД
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Получаем все сделки за период
            cursor.execute("""
                SELECT symbol, side, entry_price, exit_price, qty, pnl,
                       entry_time, exit_time, strategy, win
                FROM trades
                WHERE entry_time >= ? AND entry_time <= ?
                ORDER BY entry_time DESC
            """, (start_time.timestamp(), end_time.timestamp()))

            trades = cursor.fetchall()
            conn.close()

            if not trades:
                return TradingMetrics(
                    total_trades=0, win_rate=0.0, total_pnl=0.0, avg_pnl=0.0,
                    max_profit=0.0, max_loss=0.0, profit_factor=0.0, sharpe_ratio=0.0,
                    max_drawdown=0.0, trades_per_hour=0.0, avg_trade_duration=0.0,
                    best_symbol=None, worst_symbol=None, targets_status={}
                )

            # Анализируем сделки
            total_trades = len(trades)
            wins = sum(1 for trade in trades if trade[9])  # win column
            win_rate = wins / total_trades if total_trades > 0 else 0.0

            pnls = [trade[5] for trade in trades]  # pnl column
            total_pnl = sum(pnls)
            avg_pnl = total_pnl / total_trades if total_trades > 0 else 0.0
            max_profit = max(pnls) if pnls else 0.0
            max_loss = min(pnls) if pnls else 0.0

            # Profit factor
            profits = sum(pnl for pnl in pnls if pnl > 0)
            losses = abs(sum(pnl for pnl in pnls if pnl < 0))
            profit_factor = profits / losses if losses > 0 else float('inf') if profits > 0 else 0.0

            # Sharpe ratio (упрощенный)
            if len(pnls) > 1:
                import statistics
                sharpe_ratio = (avg_pnl / statistics.stdev(pnls)) if statistics.stdev(pnls) > 0 else 0.0
            else:
                sharpe_ratio = 0.0

            # Max drawdown
            max_drawdown = self._calculate_max_drawdown(pnls)

            # Trades per hour
            period_hours = (end_time - start_time).total_seconds() / 3600
            trades_per_hour = total_trades / period_hours if period_hours > 0 else 0.0

            # Average trade duration
            durations = []
            for trade in trades:
                if trade[6] and trade[7]:  # entry_time and exit_time
                    duration = trade[7] - trade[6]  # exit_time - entry_time
                    durations.append(duration)
            avg_trade_duration = sum(durations) / len(durations) if durations else 0.0

            # Best/worst symbols
            symbol_pnls = {}
            for trade in trades:
                symbol = trade[0]
                pnl = trade[5]
                if symbol not in symbol_pnls:
                    symbol_pnls[symbol] = []
                symbol_pnls[symbol].append(pnl)

            if symbol_pnls:
                symbol_totals = {symbol: sum(pnls) for symbol, pnls in symbol_pnls.items()}
                best_symbol = max(symbol_totals.items(), key=lambda x: x[1])[0]
                worst_symbol = min(symbol_totals.items(), key=lambda x: x[1])[0]
            else:
                best_symbol = None
                worst_symbol = None

            return TradingMetrics(
                total_trades=total_trades,
                win_rate=win_rate,
                total_pnl=total_pnl,
                avg_pnl=avg_pnl,
                max_profit=max_profit,
                max_loss=max_loss,
                profit_factor=profit_factor,
                sharpe_ratio=sharpe_ratio,
                max_drawdown=max_drawdown,
                trades_per_hour=trades_per_hour,
                avg_trade_duration=avg_trade_duration,
                best_symbol=best_symbol,
                worst_symbol=worst_symbol,
                targets_status={}
            )

        except Exception as e:
            self.logger.log_event("METRICS_AGGREGATOR", "ERROR", f"Failed to get trading metrics: {e}")
            return TradingMetrics(
                total_trades=0, win_rate=0.0, total_pnl=0.0, avg_pnl=0.0,
                max_profit=0.0, max_loss=0.0, profit_factor=0.0, sharpe_ratio=0.0,
                max_drawdown=0.0, trades_per_hour=0.0, avg_trade_duration=0.0,
                best_symbol=None, worst_symbol=None, targets_status={}
            )

    async def get_symbol_performance(self, symbol: str, period: str = "1d") -> Dict[str, Any]:
        """Получает производительность по символу"""
        try:
            # Определяем временной интервал
            end_time = datetime.now()
            if period == "1h":
                start_time = end_time - timedelta(hours=1)
            elif period == "1d":
                start_time = end_time - timedelta(days=1)
            elif period == "7d":
                start_time = end_time - timedelta(days=7)
            elif period == "30d":
                start_time = end_time - timedelta(days=30)
            else:
                start_time = end_time - timedelta(days=1)

            # Подключаемся к БД
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Получаем сделки по символу
            cursor.execute("""
                SELECT side, entry_price, exit_price, qty, pnl,
                       entry_time, exit_time, strategy, win
                FROM trades
                WHERE symbol = ? AND entry_time >= ? AND entry_time <= ?
                ORDER BY entry_time DESC
            """, (symbol, start_time.timestamp(), end_time.timestamp()))

            trades = cursor.fetchall()
            conn.close()

            if not trades:
                return {
                    'total_trades': 0,
                    'win_rate': 0.0,
                    'total_pnl': 0.0,
                    'avg_pnl': 0.0,
                    'max_profit': 0.0,
                    'max_loss': 0.0,
                    'profit_factor': 0.0,
                    'avg_trade_duration': 0.0,
                    'best_strategy': None,
                    'worst_strategy': None
                }

            # Анализируем сделки
            total_trades = len(trades)
            wins = sum(1 for trade in trades if trade[8])  # win column
            win_rate = wins / total_trades if total_trades > 0 else 0.0

            pnls = [trade[4] for trade in trades]  # pnl column
            total_pnl = sum(pnls)
            avg_pnl = total_pnl / total_trades if total_trades > 0 else 0.0
            max_profit = max(pnls) if pnls else 0.0
            max_loss = min(pnls) if pnls else 0.0

            # Profit factor
            profits = sum(pnl for pnl in pnls if pnl > 0)
            losses = abs(sum(pnl for pnl in pnls if pnl < 0))
            profit_factor = profits / losses if losses > 0 else float('inf') if profits > 0 else 0.0

            # Average trade duration
            durations = []
            for trade in trades:
                if trade[5] and trade[6]:  # entry_time and exit_time
                    duration = trade[6] - trade[5]  # exit_time - entry_time
                    durations.append(duration)
            avg_trade_duration = sum(durations) / len(durations) if durations else 0.0

            # Best/worst strategies
            strategy_pnls = {}
            for trade in trades:
                strategy = trade[7]  # strategy column
                pnl = trade[4]  # pnl column
                if strategy not in strategy_pnls:
                    strategy_pnls[strategy] = []
                strategy_pnls[strategy].append(pnl)

            if strategy_pnls:
                strategy_totals = {strategy: sum(pnls) for strategy, pnls in strategy_pnls.items()}
                best_strategy = max(strategy_totals.items(), key=lambda x: x[1])[0]
                worst_strategy = min(strategy_totals.items(), key=lambda x: x[1])[0]
            else:
                best_strategy = None
                worst_strategy = None

            return {
                'total_trades': total_trades,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'avg_pnl': avg_pnl,
                'max_profit': max_profit,
                'max_loss': max_loss,
                'profit_factor': profit_factor,
                'avg_trade_duration': avg_trade_duration,
                'best_strategy': best_strategy,
                'worst_strategy': worst_strategy
            }

        except Exception as e:
            self.logger.log_event("METRICS_AGGREGATOR", "ERROR", f"Failed to get symbol performance: {e}")
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'avg_pnl': 0.0,
                'max_profit': 0.0,
                'max_loss': 0.0,
                'profit_factor': 0.0,
                'avg_trade_duration': 0.0,
                'best_strategy': None,
                'worst_strategy': None
            }

    async def get_detailed_analytics(self, period: str = "1d") -> Dict[str, Any]:
        """Получает детальную аналитику производительности"""
        try:
            # Получаем базовые метрики
            metrics = await self.get_trading_metrics(period)

            # Анализ по временным периодам
            time_analysis = await self._analyze_time_periods(period)

            # Анализ корреляции между стратегиями
            strategy_correlation = await self._analyze_strategy_correlation(period)

            # Анализ по символам
            symbol_analysis = await self._analyze_symbols_performance(period)

            # Анализ рисков
            risk_analysis = await self._analyze_risk_metrics(period)

            # Анализ трендов
            trend_analysis = await self._analyze_performance_trends(period)

            return {
                'basic_metrics': {
                    'total_trades': metrics.total_trades,
                    'win_rate': metrics.win_rate,
                    'total_pnl': metrics.total_pnl,
                    'profit_factor': metrics.profit_factor,
                    'sharpe_ratio': metrics.sharpe_ratio,
                    'max_drawdown': metrics.max_drawdown
                },
                'time_analysis': time_analysis,
                'strategy_correlation': strategy_correlation,
                'symbol_analysis': symbol_analysis,
                'risk_analysis': risk_analysis,
                'trend_analysis': trend_analysis
            }

        except Exception as e:
            self.logger.log_event("METRICS_AGGREGATOR", "ERROR", f"Failed to get detailed analytics: {e}")
            return {}

    async def _analyze_time_periods(self, period: str) -> Dict[str, Any]:
        """Анализирует производительность по временным периодам"""
        try:
            # Определяем временной интервал
            end_time = datetime.now()
            if period == "1d":
                start_time = end_time - timedelta(days=1)
                intervals = 24  # По часам
            elif period == "7d":
                start_time = end_time - timedelta(days=7)
                intervals = 7  # По дням
            elif period == "30d":
                start_time = end_time - timedelta(days=30)
                intervals = 30  # По дням
            else:
                return {}

            # Подключаемся к БД
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Получаем данные по интервалам
            interval_data = []
            for i in range(intervals):
                if period == "1d":
                    interval_start = start_time + timedelta(hours=i)
                    interval_end = interval_start + timedelta(hours=1)
                else:
                    interval_start = start_time + timedelta(days=i)
                    interval_end = interval_start + timedelta(days=1)

                cursor.execute("""
                    SELECT COUNT(*), SUM(pnl), AVG(pnl), SUM(CASE WHEN win THEN 1 ELSE 0 END)
                    FROM trades
                    WHERE entry_time >= ? AND entry_time < ?
                """, (interval_start.timestamp(), interval_end.timestamp()))

                result = cursor.fetchone()
                if result[0] > 0:  # Есть сделки
                    interval_data.append({
                        'period': interval_start.strftime('%H:%M' if period == "1d" else '%Y-%m-%d'),
                        'trades': result[0],
                        'total_pnl': result[1] or 0.0,
                        'avg_pnl': result[2] or 0.0,
                        'wins': result[3] or 0,
                        'win_rate': (result[3] or 0) / result[0] if result[0] > 0 else 0.0
                    })

            conn.close()

            return {
                'intervals': interval_data,
                'best_period': max(interval_data, key=lambda x: x['total_pnl']) if interval_data else None,
                'worst_period': min(interval_data, key=lambda x: x['total_pnl']) if interval_data else None
            }

        except Exception as e:
            self.logger.log_event("METRICS_AGGREGATOR", "ERROR", f"Failed to analyze time periods: {e}")
            return {}

    async def _analyze_strategy_correlation(self, period: str) -> Dict[str, Any]:
        """Анализирует корреляцию между стратегиями"""
        try:
            # Определяем временной интервал
            end_time = datetime.now()
            if period == "1d":
                start_time = end_time - timedelta(days=1)
            elif period == "7d":
                start_time = end_time - timedelta(days=7)
            elif period == "30d":
                start_time = end_time - timedelta(days=30)
            else:
                start_time = end_time - timedelta(days=1)

            # Подключаемся к БД
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Получаем данные по стратегиям
            cursor.execute("""
                SELECT strategy, COUNT(*), SUM(pnl), AVG(pnl),
                       SUM(CASE WHEN win THEN 1 ELSE 0 END)
                FROM trades
                WHERE entry_time >= ? AND entry_time <= ?
                GROUP BY strategy
            """, (start_time.timestamp(), end_time.timestamp()))

            strategies = cursor.fetchall()
            conn.close()

            if not strategies:
                return {}

            # Анализируем стратегии
            strategy_analysis = []
            for strategy in strategies:
                strategy_name, trades_count, total_pnl, avg_pnl, wins = strategy
                win_rate = wins / trades_count if trades_count > 0 else 0.0

                strategy_analysis.append({
                    'strategy': strategy_name,
                    'trades': trades_count,
                    'total_pnl': total_pnl or 0.0,
                    'avg_pnl': avg_pnl or 0.0,
                    'win_rate': win_rate,
                    'profit_per_trade': (total_pnl or 0.0) / trades_count if trades_count > 0 else 0.0
                })

            # Сортируем по прибыльности
            strategy_analysis.sort(key=lambda x: x['total_pnl'], reverse=True)

            return {
                'strategies': strategy_analysis,
                'best_strategy': strategy_analysis[0] if strategy_analysis else None,
                'worst_strategy': strategy_analysis[-1] if strategy_analysis else None,
                'total_strategies': len(strategy_analysis)
            }

        except Exception as e:
            self.logger.log_event("METRICS_AGGREGATOR", "ERROR", f"Failed to analyze strategy correlation: {e}")
            return {}

    async def _analyze_symbols_performance(self, period: str) -> Dict[str, Any]:
        """Анализирует производительность по символам"""
        try:
            # Определяем временной интервал
            end_time = datetime.now()
            if period == "1d":
                start_time = end_time - timedelta(days=1)
            elif period == "7d":
                start_time = end_time - timedelta(days=7)
            elif period == "30d":
                start_time = end_time - timedelta(days=30)
            else:
                start_time = end_time - timedelta(days=1)

            # Подключаемся к БД
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Получаем данные по символам
            cursor.execute("""
                SELECT symbol, COUNT(*), SUM(pnl), AVG(pnl),
                       SUM(CASE WHEN win THEN 1 ELSE 0 END)
                FROM trades
                WHERE entry_time >= ? AND entry_time <= ?
                GROUP BY symbol
            """, (start_time.timestamp(), end_time.timestamp()))

            symbols = cursor.fetchall()
            conn.close()

            if not symbols:
                return {}

            # Анализируем символы
            symbol_analysis = []
            for symbol in symbols:
                symbol_name, trades_count, total_pnl, avg_pnl, wins = symbol
                win_rate = wins / trades_count if trades_count > 0 else 0.0

                symbol_analysis.append({
                    'symbol': symbol_name,
                    'trades': trades_count,
                    'total_pnl': total_pnl or 0.0,
                    'avg_pnl': avg_pnl or 0.0,
                    'win_rate': win_rate,
                    'profit_per_trade': (total_pnl or 0.0) / trades_count if trades_count > 0 else 0.0
                })

            # Сортируем по прибыльности
            symbol_analysis.sort(key=lambda x: x['total_pnl'], reverse=True)

            return {
                'symbols': symbol_analysis,
                'best_symbol': symbol_analysis[0] if symbol_analysis else None,
                'worst_symbol': symbol_analysis[-1] if symbol_analysis else None,
                'total_symbols': len(symbol_analysis)
            }

        except Exception as e:
            self.logger.log_event("METRICS_AGGREGATOR", "ERROR", f"Failed to analyze symbols performance: {e}")
            return {}

    async def _analyze_risk_metrics(self, period: str) -> Dict[str, Any]:
        """Анализирует метрики риска"""
        try:
            # Определяем временной интервал
            end_time = datetime.now()
            if period == "1d":
                start_time = end_time - timedelta(days=1)
            elif period == "7d":
                start_time = end_time - timedelta(days=7)
            elif period == "30d":
                start_time = end_time - timedelta(days=30)
            else:
                start_time = end_time - timedelta(days=1)

            # Подключаемся к БД
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Получаем все сделки за период
            cursor.execute("""
                SELECT pnl, entry_time, exit_time
                FROM trades
                WHERE entry_time >= ? AND entry_time <= ?
                ORDER BY entry_time
            """, (start_time.timestamp(), end_time.timestamp()))

            trades = cursor.fetchall()
            conn.close()

            if not trades:
                return {}

            # Анализируем риски
            pnls = [trade[0] for trade in trades]

            # Value at Risk (VaR) - 95% confidence
            import statistics
            if len(pnls) > 1:
                mean_pnl = statistics.mean(pnls)
                std_pnl = statistics.stdev(pnls)
                var_95 = mean_pnl - 1.645 * std_pnl  # 95% VaR
            else:
                var_95 = 0.0

            # Maximum consecutive losses
            consecutive_losses = 0
            max_consecutive_losses = 0
            for pnl in pnls:
                if pnl < 0:
                    consecutive_losses += 1
                    max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
                else:
                    consecutive_losses = 0

            # Risk-adjusted return
            total_pnl = sum(pnls)
            max_loss = min(pnls) if pnls else 0.0
            risk_adjusted_return = total_pnl / abs(max_loss) if max_loss < 0 else float('inf') if total_pnl > 0 else 0.0

            return {
                'var_95': var_95,
                'max_consecutive_losses': max_consecutive_losses,
                'risk_adjusted_return': risk_adjusted_return,
                'total_trades': len(trades),
                'loss_trades': len([p for p in pnls if p < 0]),
                'profit_trades': len([p for p in pnls if p > 0]),
                'avg_loss': statistics.mean([p for p in pnls if p < 0]) if any(p < 0 for p in pnls) else 0.0,
                'avg_profit': statistics.mean([p for p in pnls if p > 0]) if any(p > 0 for p in pnls) else 0.0
            }

        except Exception as e:
            self.logger.log_event("METRICS_AGGREGATOR", "ERROR", f"Failed to analyze risk metrics: {e}")
            return {}

    async def _analyze_performance_trends(self, period: str) -> Dict[str, Any]:
        """Анализирует тренды производительности"""
        try:
            # Определяем временной интервал
            end_time = datetime.now()
            if period == "1d":
                start_time = end_time - timedelta(days=1)
                intervals = 24  # По часам
            elif period == "7d":
                start_time = end_time - timedelta(days=7)
                intervals = 7  # По дням
            elif period == "30d":
                start_time = end_time - timedelta(days=30)
                intervals = 30  # По дням
            else:
                return {}

            # Подключаемся к БД
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Получаем данные по интервалам
            interval_pnls = []
            for i in range(intervals):
                if period == "1d":
                    interval_start = start_time + timedelta(hours=i)
                    interval_end = interval_start + timedelta(hours=1)
                else:
                    interval_start = start_time + timedelta(days=i)
                    interval_end = interval_start + timedelta(days=1)

                cursor.execute("""
                    SELECT SUM(pnl)
                    FROM trades
                    WHERE entry_time >= ? AND entry_time < ?
                """, (interval_start.timestamp(), interval_end.timestamp()))

                result = cursor.fetchone()
                interval_pnls.append(result[0] or 0.0)

            conn.close()

            # Анализируем тренды
            if len(interval_pnls) > 1:
                # Линейная регрессия для определения тренда
                x = list(range(len(interval_pnls)))
                y = interval_pnls

                # Простая линейная регрессия
                n = len(x)
                sum_x = sum(x)
                sum_y = sum(y)
                sum_xy = sum(x[i] * y[i] for i in range(n))
                sum_x2 = sum(x[i] ** 2 for i in range(n))

                slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2) if (n * sum_x2 - sum_x ** 2) != 0 else 0
                intercept = (sum_y - slope * sum_x) / n

                # Определяем направление тренда
                if slope > 0.01:
                    trend = "UPWARD"
                elif slope < -0.01:
                    trend = "DOWNWARD"
                else:
                    trend = "SIDEWAYS"

                # Волатильность
                import statistics
                volatility = statistics.stdev(interval_pnls) if len(interval_pnls) > 1 else 0.0

                return {
                    'trend': trend,
                    'slope': slope,
                    'volatility': volatility,
                    'consistency': 1 - (volatility / abs(sum_y)) if sum_y != 0 else 0.0,
                    'intervals': interval_pnls
                }
            else:
                return {
                    'trend': "INSUFFICIENT_DATA",
                    'slope': 0.0,
                    'volatility': 0.0,
                    'consistency': 0.0,
                    'intervals': interval_pnls
                }

        except Exception as e:
            self.logger.log_event("METRICS_AGGREGATOR", "ERROR", f"Failed to analyze performance trends: {e}")
            return {}

    async def _get_targets_status(self, period: str) -> Dict[str, Dict[str, Any]]:
        """Получает статус целей"""
        try:
            # Получаем цели из конфигурации
            targets = {
                'hourly_profit': self.config.get('profit_target_hourly', 0.7),
                'daily_profit': self.config.get('profit_target_daily', 16.8),
                'max_daily_loss': self.config.get('max_daily_loss', 8.0)
            }

            # Получаем метрики за период
            metrics = await self.get_trading_metrics(period)

            # Определяем период в часах
            if period == "1h":
                period_hours = 1
            elif period == "1d":
                period_hours = 24
            elif period == "7d":
                period_hours = 168
            elif period == "30d":
                period_hours = 720
            else:
                period_hours = 24

            # Рассчитываем статус целей
            targets_status = {}

            # Почасовая прибыль
            hourly_profit = metrics.total_pnl / period_hours if period_hours > 0 else 0.0
            targets_status['hourly_profit'] = {
                'target': targets['hourly_profit'],
                'actual': hourly_profit,
                'achieved': hourly_profit >= targets['hourly_profit'],
                'percentage': (hourly_profit / targets['hourly_profit']) * 100 if targets['hourly_profit'] > 0 else 0.0
            }

            # Дневная прибыль
            daily_profit = metrics.total_pnl / (period_hours / 24) if period_hours > 0 else 0.0
            targets_status['daily_profit'] = {
                'target': targets['daily_profit'],
                'actual': daily_profit,
                'achieved': daily_profit >= targets['daily_profit'],
                'percentage': (daily_profit / targets['daily_profit']) * 100 if targets['daily_profit'] > 0 else 0.0
            }

            # Максимальная дневная просадка
            max_daily_loss = abs(metrics.max_loss) if metrics.max_loss < 0 else 0.0
            targets_status['max_daily_loss'] = {
                'target': targets['max_daily_loss'],
                'actual': max_daily_loss,
                'achieved': max_daily_loss <= targets['max_daily_loss'],
                'percentage': (max_daily_loss / targets['max_daily_loss']) * 100 if targets['max_daily_loss'] > 0 else 0.0
            }

            return targets_status

        except Exception as e:
            self.logger.log_event("METRICS_AGGREGATOR", "ERROR", f"Failed to get targets status: {e}")
            return {}

    def _calculate_max_drawdown(self, pnls: List[float]) -> float:
        """Рассчитывает максимальную просадку"""
        if not pnls:
            return 0.0

        cumulative = []
        running_sum = 0.0
        for pnl in pnls:
            running_sum += pnl
            cumulative.append(running_sum)

        max_drawdown = 0.0
        peak = cumulative[0]

        for value in cumulative:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak if peak > 0 else 0.0
            max_drawdown = max(max_drawdown, drawdown)

        return max_drawdown * 100  # В процентах

    def clear_cache(self):
        """Очищает кеш"""
        self.cache.clear()
        self.logger.log_event("METRICS_AGGREGATOR", "INFO", "Cache cleared")
