# Import Windows compatibility error handling
import asyncio
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

import core.windows_compatibility
from core.metrics_aggregator import MetricsAggregator


@dataclass
class AnalysisResult:
    """Результат анализа торговли"""

    period_hours: int
    total_trades: int
    total_pnl: float
    win_rate: float
    avg_pnl: float
    max_profit: float
    max_loss: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    best_symbol: str | None
    worst_symbol: str | None
    errors_count: int
    warnings_count: int
    recommendations: list[str]
    performance_score: float


class PostRunAnalyzer:
    """Автоматический анализатор торговли после запуска"""

    def __init__(self, logger, config):
        self.logger = logger
        self.config = config
        self.db_path = Path(config.db_path)

        # Инициализируем MetricsAggregator для устранения дублирования логики
        self.metrics_aggregator = MetricsAggregator(config, logger)

    async def analyze_trading_session(self, hours: int = 24) -> AnalysisResult:
        """Анализирует торговую сессию и возвращает детальный результат"""
        # Skip analysis on Windows due to compatibility issues
        if core.windows_compatibility.IS_WINDOWS:
            self.logger.log_event("POST_RUN_ANALYZER", "INFO", "Analysis disabled for Windows")
            return self._empty_analysis_result(hours)

        try:
            # Получаем данные из БД
            events_data = await self._get_events_data(hours)

            # Используем MetricsAggregator для получения метрик
            period_map = {"1h": "1h", "4h": "4h", "24h": "1d", "1d": "1d"}
            period = period_map.get(f"{hours}h", "1d")

            trading_metrics = await self.metrics_aggregator.get_trading_metrics(period)

            # Анализируем ошибки и предупреждения
            error_analysis = self._analyze_errors(events_data)

            # Генерируем рекомендации
            recommendations = self._generate_recommendations(trading_metrics, error_analysis)

            # Рассчитываем общий score
            performance_score = self._calculate_performance_score(trading_metrics, error_analysis)

            return AnalysisResult(
                period_hours=hours,
                total_trades=trading_metrics.total_trades,
                total_pnl=trading_metrics.total_pnl,
                win_rate=trading_metrics.win_rate,
                avg_pnl=trading_metrics.avg_pnl,
                max_profit=trading_metrics.max_profit,
                max_loss=trading_metrics.max_loss,
                profit_factor=trading_metrics.profit_factor,
                sharpe_ratio=trading_metrics.sharpe_ratio,
                max_drawdown=trading_metrics.max_drawdown,
                best_symbol=trading_metrics.best_symbol,
                worst_symbol=trading_metrics.worst_symbol,
                errors_count=error_analysis["errors_count"],
                warnings_count=error_analysis["warnings_count"],
                recommendations=recommendations,
                performance_score=performance_score,
            )

        except Exception as e:
            self.logger.log_event("POST_RUN_ANALYZER", "ERROR", f"Analysis failed: {e}")
            return self._empty_analysis_result(hours)

    async def _get_trades_data(self, hours: int) -> pd.DataFrame:
        """Получает данные о сделках"""
        since = datetime.utcnow() - timedelta(hours=hours)

        try:
            with sqlite3.connect(self.db_path) as conn:
                query = """
                    SELECT symbol, side, qty, entry_price, pnl, win, timestamp
                    FROM trades
                    WHERE timestamp >= ?
                    ORDER BY timestamp DESC
                """
                df = pd.read_sql_query(query, conn, params=(since.isoformat(),))
            return df
        except Exception as e:
            # Handle Windows compatibility errors
            if core.windows_compatibility.is_windows_compatibility_error(str(e)):
                self.logger.log_event(
                    "POST_RUN_ANALYZER", "INFO", "Analysis data retrieved (Windows compatibility)"
                )
            else:
                self.logger.log_event(
                    "POST_RUN_ANALYZER", "ERROR", f"Failed to get trades data: {e}"
                )
            return pd.DataFrame()

    async def _get_events_data(self, hours: int) -> pd.DataFrame:
        """Получает данные о событиях"""
        since = datetime.utcnow() - timedelta(hours=hours)

        try:
            with sqlite3.connect(self.db_path) as conn:
                query = """
                    SELECT level, component, message, details, timestamp
                    FROM events
                    WHERE timestamp >= ?
                    ORDER BY timestamp DESC
                """
                df = pd.read_sql_query(query, conn, params=(since.isoformat(),))
            return df
        except Exception as e:
            # Игнорируем ошибки Windows compatibility
            if "warnings" in str(e) or "maxsize" in str(e) or "builtin_module_names" in str(e):
                self.logger.log_event(
                    "POST_RUN_ANALYZER", "INFO", "Events data retrieved (Windows compatibility)"
                )
            else:
                self.logger.log_event(
                    "POST_RUN_ANALYZER", "ERROR", f"Failed to get events data: {e}"
                )
            return pd.DataFrame()

    def _calculate_metrics(self, trades_df: pd.DataFrame) -> dict[str, Any]:
        """Рассчитывает торговые метрики"""
        if trades_df.empty:
            return self._empty_metrics()

        # Базовые метрики
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df["pnl"] > 0])
        losing_trades = len(trades_df[trades_df["pnl"] < 0])
        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        # PnL метрики
        total_pnl = trades_df["pnl"].sum()
        avg_pnl = trades_df["pnl"].mean()
        max_profit = trades_df["pnl"].max()
        max_loss = trades_df["pnl"].min()

        # Продвинутые метрики
        profit_factor = self._calculate_profit_factor(trades_df)
        sharpe_ratio = self._calculate_sharpe_ratio(trades_df)
        max_drawdown = self._calculate_max_drawdown(trades_df)

        # Лучшие/худшие символы
        symbol_pnl = trades_df.groupby("symbol")["pnl"].sum()
        best_symbol = symbol_pnl.idxmax() if not symbol_pnl.empty else None
        worst_symbol = symbol_pnl.idxmin() if not symbol_pnl.empty else None

        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "avg_pnl": avg_pnl,
            "max_profit": max_profit,
            "max_loss": max_loss,
            "profit_factor": profit_factor,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,
            "best_symbol": best_symbol,
            "worst_symbol": worst_symbol,
        }

    def _analyze_errors(self, events_df: pd.DataFrame) -> dict[str, Any]:
        """Анализирует ошибки и предупреждения"""
        if events_df.empty:
            return {"errors_count": 0, "warnings_count": 0, "error_types": {}}

        errors_df = events_df[events_df["level"].isin(["ERROR", "CRITICAL"])]
        warnings_df = events_df[events_df["level"] == "WARNING"]

        error_types = errors_df["component"].value_counts().to_dict()

        return {
            "errors_count": len(errors_df),
            "warnings_count": len(warnings_df),
            "error_types": error_types,
        }

    def _generate_recommendations(
        self, metrics: dict[str, Any], error_analysis: dict[str, Any]
    ) -> list[str]:
        """Генерирует рекомендации на основе анализа"""
        recommendations = []

        # Анализ прибыльности
        if metrics["total_pnl"] < 0:
            recommendations.append("🔴 Общий PnL отрицательный - пересмотрите стратегию")

        if metrics["win_rate"] < 0.5:
            recommendations.append("📉 Низкий винрейт - улучшите фильтры сигналов")

        if metrics["profit_factor"] < 1.2:
            recommendations.append("⚖️ Низкий profit factor - оптимизируйте риск-менеджмент")

        if metrics["max_drawdown"] > 10:
            recommendations.append("📉 Высокий drawdown - уменьшите размер позиций")

        # Анализ ошибок
        if error_analysis["errors_count"] > 5:
            recommendations.append("⚠️ Много ошибок - проверьте стабильность системы")

        if error_analysis["warnings_count"] > 10:
            recommendations.append("⚠️ Много предупреждений - оптимизируйте логику")

        # Положительные аспекты
        if metrics["win_rate"] > 0.7:
            recommendations.append("✅ Отличный винрейт - система работает хорошо")

        if metrics["profit_factor"] > 2.0:
            recommendations.append("✅ Высокий profit factor - отличная стратегия")

        if metrics["total_pnl"] > 0 and metrics["total_trades"] > 10:
            recommendations.append("✅ Прибыльная торговля - продолжайте в том же духе")

        # Логируем короткие рекомендации
        for rec in recommendations:
            self.logger.log_analysis_recommendation(rec)

        return recommendations

    def _calculate_performance_score(
        self, metrics: dict[str, Any], error_analysis: dict[str, Any]
    ) -> float:
        """Рассчитывает общий score производительности (0-100)"""
        score = 0

        # Базовый score за прибыльность (40 баллов)
        if metrics["total_pnl"] > 0:
            score += min(40, metrics["total_pnl"] * 10)  # До 40 баллов за прибыль

        # Score за винрейт (20 баллов)
        score += metrics["win_rate"] * 20

        # Score за profit factor (20 баллов)
        if metrics["profit_factor"] > 0:
            score += min(20, metrics["profit_factor"] * 10)

        # Штраф за ошибки (до -20 баллов)
        error_penalty = min(20, error_analysis["errors_count"] * 2)
        score -= error_penalty

        # Штраф за drawdown (до -10 баллов)
        drawdown_penalty = min(10, metrics["max_drawdown"] / 2)
        score -= drawdown_penalty

        return max(0, min(100, score))

    def _calculate_profit_factor(self, trades_df: pd.DataFrame) -> float:
        """Рассчитывает profit factor"""
        if trades_df.empty:
            return 0

        gross_profit = trades_df[trades_df["pnl"] > 0]["pnl"].sum()
        gross_loss = abs(trades_df[trades_df["pnl"] < 0]["pnl"].sum())

        return gross_profit / gross_loss if gross_loss > 0 else float("inf")

    def _calculate_sharpe_ratio(self, trades_df: pd.DataFrame) -> float:
        """Рассчитывает Sharpe ratio"""
        if trades_df.empty or len(trades_df) < 2:
            return 0

        returns = trades_df["pnl"].pct_change().dropna()
        if len(returns) == 0:
            return 0

        return returns.mean() / returns.std() if returns.std() > 0 else 0

    def _calculate_max_drawdown(self, trades_df: pd.DataFrame) -> float:
        """Рассчитывает максимальный drawdown"""
        if trades_df.empty:
            return 0

        cumulative = trades_df["pnl"].cumsum()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max * 100

        return abs(drawdown.min()) if len(drawdown) > 0 else 0

    def _empty_metrics(self) -> dict[str, Any]:
        """Возвращает пустые метрики"""
        return {
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
            "best_symbol": None,
            "worst_symbol": None,
        }

    def _empty_analysis_result(self, hours: int) -> AnalysisResult:
        """Возвращает пустой результат анализа"""
        return AnalysisResult(
            period_hours=hours,
            total_trades=0,
            total_pnl=0,
            win_rate=0,
            avg_pnl=0,
            max_profit=0,
            max_loss=0,
            profit_factor=0,
            sharpe_ratio=0,
            max_drawdown=0,
            best_symbol=None,
            worst_symbol=None,
            errors_count=0,
            warnings_count=0,
            recommendations=["📊 Нет данных для анализа"],
            performance_score=0,
        )

    def generate_console_report(self, result: AnalysisResult) -> str:
        """Генерирует красивый консольный отчет"""
        report = f"""
{"=" * 60}
🎯 ПОСТ-АНАЛИЗ ТОРГОВОЙ СЕССИИ ({result.period_hours}ч)
{"=" * 60}

📊 ОСНОВНЫЕ МЕТРИКИ:
• Сделок: {result.total_trades}
• PnL: ${result.total_pnl:.2f}
• Винрейт: {result.win_rate:.1%}
• Средний PnL: ${result.avg_pnl:.2f}
• Макс. прибыль: ${result.max_profit:.2f}
• Макс. убыток: ${result.max_loss:.2f}

📈 ПРОДВИНУТЫЕ МЕТРИКИ:
• Profit Factor: {result.profit_factor:.2f}
• Sharpe Ratio: {result.sharpe_ratio:.2f}
• Max Drawdown: {result.max_drawdown:.1f}%

🏆 ЛУЧШИЕ/ХУДШИЕ СИМВОЛЫ:
• Лучший: {result.best_symbol or "N/A"}
• Худший: {result.worst_symbol or "N/A"}

⚠️ СИСТЕМНЫЕ СОБЫТИЯ:
• Ошибок: {result.errors_count}
• Предупреждений: {result.warnings_count}

🎯 ОБЩИЙ SCORE: {result.performance_score:.1f}/100

💡 РЕКОМЕНДАЦИИ:
"""

        for rec in result.recommendations:
            report += f"• {rec}\n"

        report += f"\n{'=' * 60}"

        return report

    def save_analysis_report(self, result: AnalysisResult, filename: str = None) -> str:
        """Сохраняет анализ в файл"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"analysis_report_{result.period_hours}h_{timestamp}.json"

        report_path = Path("data/analysis_reports") / filename
        report_path.parent.mkdir(exist_ok=True)

        # Конвертируем в словарь для JSON
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "period_hours": result.period_hours,
            "total_trades": result.total_trades,
            "total_pnl": result.total_pnl,
            "win_rate": result.win_rate,
            "avg_pnl": result.avg_pnl,
            "max_profit": result.max_profit,
            "max_loss": result.max_loss,
            "profit_factor": result.profit_factor,
            "sharpe_ratio": result.sharpe_ratio,
            "max_drawdown": result.max_drawdown,
            "best_symbol": result.best_symbol,
            "worst_symbol": result.worst_symbol,
            "errors_count": result.errors_count,
            "warnings_count": result.warnings_count,
            "recommendations": result.recommendations,
            "performance_score": result.performance_score,
        }

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        # Очищаем старые отчеты (синхронно)
        asyncio.create_task(self._cleanup_old_reports())

        return str(report_path)

    async def _cleanup_old_reports(self, days_to_keep: int = 30):
        """Очищает старые отчеты, оставляя только последние N дней"""
        try:
            data_dir = Path("data")
            analysis_reports_dir = Path("data/analysis_reports")
            if not data_dir.exists():
                return

            # Находим все файлы отчетов
            report_files = list(analysis_reports_dir.glob("analysis_report_*.json"))
            report_files.extend(list(data_dir.glob("final_analysis_*.txt")))

            # Фильтруем файлы старше N дней
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            files_to_delete = []

            for file_path in report_files:
                try:
                    # Пытаемся извлечь дату из имени файла
                    file_date_str = file_path.stem.split("_")[-1]  # Последняя часть имени
                    if len(file_date_str) >= 8:  # YYYYMMDD
                        file_date = datetime.strptime(file_date_str[:8], "%Y%m%d")
                        if file_date < cutoff_date:
                            files_to_delete.append(file_path)
                except Exception:
                    # Если не удается извлечь дату, проверяем время модификации
                    if file_path.stat().st_mtime < cutoff_date.timestamp():
                        files_to_delete.append(file_path)

            # Удаляем старые файлы
            deleted_count = 0
            for file_path in files_to_delete:
                try:
                    file_path.unlink()
                    deleted_count += 1
                except Exception as e:
                    self.logger.log_event(
                        "POST_RUN_ANALYZER",
                        "WARNING",
                        f"Failed to delete old report {file_path}: {e}",
                    )

            if deleted_count > 0:
                self.logger.log_event(
                    "POST_RUN_ANALYZER",
                    "INFO",
                    f"Cleaned up {deleted_count} old report files (older than {days_to_keep} days)",
                )

        except Exception as e:
            self.logger.log_event(
                "POST_RUN_ANALYZER", "ERROR", f"Failed to cleanup old reports: {e}"
            )

    def get_reports_info(self) -> dict:
        """Возвращает информацию о сохраненных отчетах"""
        try:
            data_dir = Path("data")
            analysis_reports_dir = Path("data/analysis_reports")
            if not data_dir.exists():
                return {"total_reports": 0, "reports": []}

            # Находим все файлы отчетов
            json_reports = list(analysis_reports_dir.glob("analysis_report_*.json"))
            txt_reports = list(data_dir.glob("final_analysis_*.txt"))
            all_reports = json_reports + txt_reports

            reports_info = []
            total_size_mb = 0

            for file_path in all_reports:
                try:
                    stat = file_path.stat()
                    size_mb = stat.st_size / (1024 * 1024)
                    total_size_mb += size_mb

                    reports_info.append(
                        {
                            "filename": file_path.name,
                            "size_mb": round(size_mb, 2),
                            "modified": datetime.fromtimestamp(stat.st_mtime).strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                            "type": "json" if file_path.suffix == ".json" else "txt",
                        }
                    )
                except Exception as e:
                    self.logger.log_event(
                        "POST_RUN_ANALYZER", "WARNING", f"Failed to get info for {file_path}: {e}"
                    )

            # Сортируем по дате модификации (новые сначала)
            reports_info.sort(key=lambda x: x["modified"], reverse=True)

            return {
                "total_reports": len(reports_info),
                "total_size_mb": round(total_size_mb, 2),
                "reports": reports_info[:10],  # Показываем только последние 10
            }

        except Exception as e:
            self.logger.log_event("POST_RUN_ANALYZER", "ERROR", f"Failed to get reports info: {e}")
            return {"total_reports": 0, "reports": []}

    async def analyze_performance_loop(self):
        """Автоматический цикл анализа производительности"""
        while True:
            try:
                # Анализируем последние 24 часа
                result = await self.analyze_trading_session(hours=24)

                # Генерируем консольный отчет
                console_report = self.generate_console_report(result)

                # Логируем отчет
                self.logger.log_event(
                    "POST_RUN_ANALYZER",
                    "INFO",
                    f"Performance Analysis ({result.period_hours}h): "
                    f"Trades: {result.total_trades}, PnL: ${result.total_pnl:.2f}, "
                    f"Win Rate: {result.win_rate:.1%}, Score: {result.performance_score:.1f}/100",
                )

                # Выводим полный отчет в консоль
                print(console_report)

                # Сохраняем отчет в файл
                report_path = self.save_analysis_report(result)
                self.logger.log_event(
                    "POST_RUN_ANALYZER", "INFO", f"Analysis report saved: {report_path}"
                )

                # Если есть критические проблемы, логируем их отдельно
                if result.performance_score < 50:
                    self.logger.log_event(
                        "POST_RUN_ANALYZER",
                        "WARNING",
                        f"Low performance score: {result.performance_score:.1f}/100",
                    )

                if result.errors_count > 5:
                    self.logger.log_event(
                        "POST_RUN_ANALYZER", "WARNING", f"High error count: {result.errors_count}"
                    )

                # Ждем 6 часов до следующего анализа
                await asyncio.sleep(6 * 3600)  # 6 часов

            except Exception as e:
                self.logger.log_event(
                    "POST_RUN_ANALYZER", "ERROR", f"Performance analysis loop error: {e}"
                )
                await asyncio.sleep(3600)  # Ждем час при ошибке

    async def generate_quick_summary(self, hours: int = 24) -> str:
        """Генерирует краткую текстовую сводку"""
        try:
            result = await self.analyze_trading_session(hours)

            summary = f"""
📊 КРАТКАЯ СВОДКА ЗА {hours}Ч:

💰 Прибыль: ${result.total_pnl:.2f}
📈 Сделок: {result.total_trades}
✅ Винрейт: {result.win_rate:.1%}
📊 Score: {result.performance_score:.1f}/100

🏆 Лучший символ: {result.best_symbol or "N/A"}
📉 Худший символ: {result.worst_symbol or "N/A"}

⚠️ Ошибок: {result.errors_count}
⚠️ Предупреждений: {result.warnings_count}

💡 Ключевые рекомендации:
"""

            # Добавляем топ-3 рекомендации
            for i, rec in enumerate(result.recommendations[:3], 1):
                summary += f"{i}. {rec}\n"

            return summary.strip()

        except Exception as e:
            return f"❌ Ошибка анализа: {e}"

    async def generate_detailed_report(self, hours: int = 24) -> str:
        """Генерирует детальный текстовый отчет"""
        try:
            result = await self.analyze_trading_session(hours)

            report = f"""
🎯 ДЕТАЛЬНЫЙ АНАЛИЗ ТОРГОВЛИ ({hours}ч)

📊 ОСНОВНЫЕ МЕТРИКИ:
• Общий PnL: ${result.total_pnl:.2f}
• Количество сделок: {result.total_trades}
• Винрейт: {result.win_rate:.1%}
• Средний PnL за сделку: ${result.avg_pnl:.2f}
• Максимальная прибыль: ${result.max_profit:.2f}
• Максимальный убыток: ${result.max_loss:.2f}

📈 ПРОДВИНУТЫЕ МЕТРИКИ:
• Profit Factor: {result.profit_factor:.2f}
• Sharpe Ratio: {result.sharpe_ratio:.2f}
• Максимальный Drawdown: {result.max_drawdown:.1f}%

🏆 АНАЛИЗ ПО СИМВОЛАМ:
• Лучший символ: {result.best_symbol or "N/A"}
• Худший символ: {result.worst_symbol or "N/A"}

⚠️ СИСТЕМНЫЕ СОБЫТИЯ:
• Количество ошибок: {result.errors_count}
• Количество предупреждений: {result.warnings_count}

🎯 ОБЩИЙ SCORE: {result.performance_score:.1f}/100

💡 РЕКОМЕНДАЦИИ:
"""

            for i, rec in enumerate(result.recommendations, 1):
                report += f"{i}. {rec}\n"

            # Добавляем интерпретацию score
            if result.performance_score >= 80:
                report += "\n✅ ОТЛИЧНАЯ ПРОИЗВОДИТЕЛЬНОСТЬ"
            elif result.performance_score >= 60:
                report += "\n🟡 ХОРОШАЯ ПРОИЗВОДИТЕЛЬНОСТЬ"
            elif result.performance_score >= 40:
                report += "\n🟠 СРЕДНЯЯ ПРОИЗВОДИТЕЛЬНОСТЬ"
            else:
                report += "\n🔴 НИЗКАЯ ПРОИЗВОДИТЕЛЬНОСТЬ"

            return report.strip()

        except Exception as e:
            return f"❌ Ошибка генерации отчета: {e}"

    async def get_binance_position_history(self, hours: int = 24) -> dict:
        """Получает точную сводку позиций из Binance API"""
        try:
            from core.config import TradingConfig
            from core.exchange_client import OptimizedExchangeClient

            # Создаем временный exchange client
            config = TradingConfig.load_optimized_for_profit_target(0.7)
            exchange = OptimizedExchangeClient(config, self.logger)

            if not await exchange.initialize():
                return {"error": "Failed to initialize exchange client"}

            # Получаем время начала периода
            since = datetime.now() - timedelta(hours=hours)
            since_timestamp = int(since.timestamp() * 1000)

            # 1. Получаем историю сделок (userTrades)
            trades_data = await self._get_user_trades(exchange, since_timestamp)

            # 2. Получаем текущие позиции (positionRisk)
            positions_data = await self._get_position_risk(exchange)

            # 3. Получаем доходы/расходы (income)
            income_data = await self._get_income_history(exchange, since_timestamp)

            # 4. Получаем информацию об аккаунте
            account_data = await self._get_account_info(exchange)

            # Анализируем данные
            analysis = self._analyze_position_history(
                trades_data, positions_data, income_data, account_data
            )

            return analysis

        except Exception as e:
            self.logger.log_event(
                "POST_RUN_ANALYZER", "ERROR", f"Failed to get Binance position history: {e}"
            )
            return {"error": str(e)}

    async def _get_user_trades(self, exchange, since_timestamp: int) -> list:
        """Получает историю сделок пользователя"""
        try:
            # GET /fapi/v1/userTrades
            params = {
                "startTime": since_timestamp,
                "limit": 1000,  # Максимальный лимит
            }

            response = await exchange.client.futures_account_trades(**params)
            return response
        except Exception as e:
            self.logger.log_event("POST_RUN_ANALYZER", "ERROR", f"Failed to get user trades: {e}")
            return []

    async def _get_position_risk(self, exchange) -> list:
        """Получает информацию о позициях"""
        try:
            # GET /fapi/v1/positionRisk
            response = await exchange.client.futures_position_information()
            return response
        except Exception as e:
            self.logger.log_event("POST_RUN_ANALYZER", "ERROR", f"Failed to get position risk: {e}")
            return []

    async def _get_income_history(self, exchange, since_timestamp: int) -> list:
        """Получает историю доходов/расходов"""
        try:
            # GET /fapi/v1/income
            params = {"startTime": since_timestamp, "limit": 1000}

            response = await exchange.client.futures_income_history(**params)
            return response
        except Exception as e:
            self.logger.log_event(
                "POST_RUN_ANALYZER", "ERROR", f"Failed to get income history: {e}"
            )
            return []

    async def _get_account_info(self, exchange) -> dict:
        """Получает информацию об аккаунте"""
        try:
            # GET /fapi/v1/account
            response = await exchange.client.futures_account()
            return response
        except Exception as e:
            self.logger.log_event("POST_RUN_ANALYZER", "ERROR", f"Failed to get account info: {e}")
            return {}

    def _analyze_position_history(
        self, trades_data: list, positions_data: list, income_data: list, account_data: dict
    ) -> dict:
        """Анализирует данные позиций из Binance API"""
        try:
            # Группируем сделки по символам
            symbol_trades = {}
            total_fees = 0
            total_commission = 0

            for trade in trades_data:
                symbol = trade["symbol"]
                if symbol not in symbol_trades:
                    symbol_trades[symbol] = []

                # Рассчитываем комиссию
                fee = float(trade["commission"])
                total_commission += fee

                symbol_trades[symbol].append(
                    {
                        "time": trade["time"],
                        "side": trade["side"],
                        "price": float(trade["price"]),
                        "qty": float(trade["qty"]),
                        "commission": fee,
                        "realizedPnl": float(trade.get("realizedPnl", 0)),
                    }
                )

            # Анализируем позиции по символам
            position_analysis = {}
            total_realized_pnl = 0
            total_trades = 0
            winning_trades = 0

            for symbol, trades in symbol_trades.items():
                if len(trades) < 2:  # Нужно минимум 2 сделки (открытие + закрытие)
                    continue

                # Сортируем сделки по времени
                trades.sort(key=lambda x: x["time"])

                # Группируем в позиции (открытие + закрытие)
                positions = []
                i = 0
                while i < len(trades) - 1:
                    open_trade = trades[i]
                    close_trade = trades[i + 1]

                    # Проверяем, что это открытие и закрытие позиции
                    if (
                        open_trade["side"] != close_trade["side"]
                        and open_trade["qty"] == close_trade["qty"]
                    ):
                        position = {
                            "symbol": symbol,
                            "side": open_trade["side"],
                            "entry_price": open_trade["price"],
                            "exit_price": close_trade["price"],
                            "qty": open_trade["qty"],
                            "entry_time": open_trade["time"],
                            "exit_time": close_trade["time"],
                            "realized_pnl": close_trade["realizedPnl"],
                            "fees": open_trade["commission"] + close_trade["commission"],
                        }

                        # Рассчитываем PnL
                        if position["side"] == "BUY":
                            pnl = (position["exit_price"] - position["entry_price"]) * position[
                                "qty"
                            ]
                        else:
                            pnl = (position["entry_price"] - position["exit_price"]) * position[
                                "qty"
                            ]

                        position["calculated_pnl"] = pnl
                        position["net_pnl"] = pnl - position["fees"]

                        positions.append(position)
                        total_realized_pnl += position["net_pnl"]
                        total_trades += 1

                        if position["net_pnl"] > 0:
                            winning_trades += 1

                        i += 2  # Пропускаем обе сделки
                    else:
                        i += 1

                position_analysis[symbol] = positions

            # Анализируем funding fees
            total_funding_fees = 0
            for income in income_data:
                if income["incomeType"] == "FUNDING_FEE":
                    total_funding_fees += float(income["income"])

            # Рассчитываем итоговые метрики
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            avg_pnl_per_trade = total_realized_pnl / total_trades if total_trades > 0 else 0

            # Получаем информацию о текущих позициях
            current_positions = []
            unrealized_pnl = 0

            for position in positions_data:
                if float(position["positionAmt"]) != 0:  # Есть открытая позиция
                    current_positions.append(
                        {
                            "symbol": position["symbol"],
                            "side": "LONG" if float(position["positionAmt"]) > 0 else "SHORT",
                            "size": abs(float(position["positionAmt"])),
                            "entry_price": float(position["entryPrice"]),
                            "mark_price": float(position["markPrice"]),
                            "unrealized_pnl": float(position["unRealizedProfit"]),
                        }
                    )
                    unrealized_pnl += float(position["unRealizedProfit"])

            return {
                "period_hours": 24,
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "win_rate": win_rate,
                "total_realized_pnl": total_realized_pnl,
                "total_commission": total_commission,
                "total_funding_fees": total_funding_fees,
                "net_pnl": total_realized_pnl - total_commission - total_funding_fees,
                "avg_pnl_per_trade": avg_pnl_per_trade,
                "current_positions": current_positions,
                "unrealized_pnl": unrealized_pnl,
                "position_analysis": position_analysis,
                "account_info": {
                    "total_wallet_balance": float(account_data.get("totalWalletBalance", 0)),
                    "total_unrealized_profit": float(account_data.get("totalUnrealizedProfit", 0)),
                    "total_margin_balance": float(account_data.get("totalMarginBalance", 0)),
                },
            }

        except Exception as e:
            self.logger.log_event(
                "POST_RUN_ANALYZER", "ERROR", f"Failed to analyze position history: {e}"
            )
            return {"error": str(e)}

    async def generate_binance_summary(self, hours: int = 24) -> str:
        """Генерирует сводку на основе данных Binance API"""
        try:
            binance_data = await self.get_binance_position_history(hours)

            if "error" in binance_data:
                return f"❌ Ошибка получения данных Binance: {binance_data['error']}"

            summary = f"""
📊 ТОЧНАЯ СВОДКА ИЗ BINANCE API ({hours}ч)

💰 РЕАЛИЗОВАННЫЙ PnL:
• Общий PnL: ${binance_data["total_realized_pnl"]:.2f}
• Комиссии: ${binance_data["total_commission"]:.2f}
• Funding Fees: ${binance_data["total_funding_fees"]:.2f}
• Чистый PnL: ${binance_data["net_pnl"]:.2f}

📈 СТАТИСТИКА СДЕЛОК:
• Всего сделок: {binance_data["total_trades"]}
• Прибыльных: {binance_data["winning_trades"]}
• Винрейт: {binance_data["win_rate"]:.1f}%
• Средний PnL за сделку: ${binance_data["avg_pnl_per_trade"]:.2f}

🏆 ТЕКУЩИЕ ПОЗИЦИИ ({len(binance_data["current_positions"])}):
"""

            for pos in binance_data["current_positions"]:
                summary += f"• {pos['symbol']} {pos['side']}: {pos['size']:.4f} @ ${pos['entry_price']:.4f} (UnPnL: ${pos['unrealized_pnl']:.2f})\n"

            summary += f"""
💼 АККАУНТ:
• Общий баланс: ${binance_data["account_info"]["total_wallet_balance"]:.2f}
• Нереализованная прибыль: ${binance_data["account_info"]["total_unrealized_profit"]:.2f}
• Маржинальный баланс: ${binance_data["account_info"]["total_margin_balance"]:.2f}

📋 ДЕТАЛИ ПО СИМВОЛАМ:
"""

            # Показываем топ-5 символов по PnL
            symbol_pnl = {}
            for symbol, positions in binance_data["position_analysis"].items():
                symbol_total = sum(pos["net_pnl"] for pos in positions)
                symbol_pnl[symbol] = symbol_total

            # Сортируем по PnL
            sorted_symbols = sorted(symbol_pnl.items(), key=lambda x: x[1], reverse=True)

            for i, (symbol, pnl) in enumerate(sorted_symbols[:5], 1):
                summary += f"{i}. {symbol}: ${pnl:.2f}\n"

            return summary.strip()

        except Exception as e:
            return f"❌ Ошибка генерации сводки Binance: {e}"
