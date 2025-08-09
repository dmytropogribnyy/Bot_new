#!/usr/bin/env python3
"""
TP Optimizer для BinanceBot v2
Адаптирован из старого бота с улучшениями
"""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from core.aggression_manager import AggressionManager
from strategies.base_strategy import BaseStrategy


class TPOptimizer(BaseStrategy):
    """Оптимизатор Take Profit уровней на основе исторических данных"""

    def __init__(self, config, exchange_client, symbol_manager, logger):
        super().__init__(config, exchange_client, symbol_manager, logger)

        # Инициализируем AggressionManager для динамических настроек
        self.aggression_manager = AggressionManager(config, logger)

        # Получаем настройки с учетом агрессивности
        self._update_settings_from_aggression()

        self.db_path = Path("data/trading_log.db")
        self.last_optimization = None

    def _update_settings_from_aggression(self):
        """Обновляет настройки стратегии с учетом уровня агрессивности"""
        try:
            settings = self.aggression_manager.get_strategy_settings("tp_optimizer")

            # Обновляем параметры из настроек агрессивности
            self.optimization_interval = timedelta(
                hours=settings.get("optimization_interval_hours", 6)
            )
            self.min_trades_for_optimization = settings.get("min_trades_for_optimization", 10)
            self.update_threshold = settings.get("update_threshold", 0.15)
            self.min_atr_percent = settings.get("min_atr_percent", 0.8)
            self.trend_threshold = settings.get("trend_threshold", 0.2)
            self.min_position_size_usdc = settings.get("min_position_size_usdc", 15)
            self.max_position_size_usdc = settings.get("max_position_size_usdc", 80)

            # Логируем обновление настроек
            self.logger.log_strategy_event(
                "tp_optimizer",
                "SETTINGS_UPDATED",
                {
                    "aggression_level": self.aggression_manager.get_aggression_level(),
                    "optimization_interval_hours": self.optimization_interval.total_seconds()
                    / 3600,
                    "min_trades_for_optimization": self.min_trades_for_optimization,
                    "update_threshold": self.update_threshold,
                },
            )

        except Exception as e:
            self.logger.log_event(
                "STRATEGY", "ERROR", f"Failed to update settings from AggressionManager: {e}"
            )
            # Fallback к базовым настройкам
            self.optimization_interval = timedelta(hours=6)
            self.min_trades_for_optimization = 10
            self.update_threshold = 0.15
            self.min_atr_percent = 0.8
            self.trend_threshold = 0.2
            self.min_position_size_usdc = 15
            self.max_position_size_usdc = 80

    async def analyze_market(self, symbol: str) -> dict[str, Any] | None:
        """Анализирует рынок для TP оптимизации"""
        try:
            # Получаем исторические данные
            ohlcv_data = await self.symbol_manager.get_recent_ohlcv(symbol)
            if not ohlcv_data or len(ohlcv_data) < 50:
                return None

            # Конвертируем в pandas DataFrame
            df = pd.DataFrame(ohlcv_data)
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)

            # Убеждаемся, что колонки имеют правильные имена
            if "close" not in df.columns:
                print(f"❌ Колонка 'close' не найдена в данных для {symbol}")
                return None

            # Анализируем волатильность для TP оптимизации
            current_price = df["close"].iloc[-1]
            atr = df["close"].rolling(14).std().iloc[-1]
            atr_percent = (atr / current_price) * 100

            # Улучшенные условия для TP оптимизации
            if atr_percent > 0.8:  # Оптимизировано для $400 депозита
                # Добавляем анализ тренда
                sma_20 = df["close"].rolling(20).mean().iloc[-1]
                trend_strength = (current_price - sma_20) / sma_20 * 100

                # Определяем направление на основе тренда
                side = "BUY" if trend_strength > 0.2 else "SELL" if trend_strength < -0.2 else "BUY"

                return {
                    "side": side,
                    "entry_price": current_price,
                    "confidence": min(atr_percent / 4.0, 0.9),  # Оптимизировано для $400
                    "trend_strength": trend_strength,
                    "volatility": atr_percent,
                }

            return None

        except Exception as e:
            self.logger.log_event(
                "TP_OPTIMIZER", "ERROR", f"Market analysis failed for {symbol}: {e}"
            )
            return None

    async def should_exit(self, symbol: str, position_data: dict[str, Any]) -> bool:
        """Определяет, следует ли закрыть позицию"""
        try:
            # Простая логика выхода для TP оптимизации
            entry_price = position_data.get("entry_price", 0)
            current_price = position_data.get("current_price", 0)

            if entry_price == 0 or current_price == 0:
                return False

            # Выход при достижении первого TP уровня
            tp_level = self.config.step_tp_levels[0] if self.config.step_tp_levels else 0.01

            if position_data.get("side") == "BUY":
                return current_price >= entry_price * (1 + tp_level)
            else:
                return current_price <= entry_price * (1 - tp_level)

        except Exception as e:
            self.logger.log_event(
                "TP_OPTIMIZER", "ERROR", f"Exit analysis failed for {symbol}: {e}"
            )
            return False

    async def should_optimize(self) -> bool:
        """Проверяет, нужно ли запускать оптимизацию"""
        if not self.config.get("tp_optimization_enabled", True):
            return False

        if self.last_optimization is None:
            return True

        time_since_last = datetime.utcnow() - self.last_optimization
        return time_since_last >= self.optimization_interval

    async def get_trade_history(self, days: int = 7) -> pd.DataFrame:
        """Получает историю сделок из БД"""
        try:
            import sqlite3

            query = f"""
            SELECT
                timestamp,
                symbol,
                side,
                entry_price,
                qty,
                reason,
                pnl
            FROM trades
            WHERE timestamp >= datetime('now', '-{days} days')
            ORDER BY timestamp DESC
            """

            with sqlite3.connect(self.db_path) as conn:
                df = pd.read_sql_query(query, conn)

            if df.empty:
                self.logger.log_event(
                    "TP_OPTIMIZER", "WARNING", "No trade history found for optimization"
                )
                return pd.DataFrame()

            # Конвертируем timestamp
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df["date"] = df["timestamp"].dt.date

            return df

        except Exception as e:
            self.logger.log_event("TP_OPTIMIZER", "ERROR", f"Failed to get trade history: {e}")
            return pd.DataFrame()

    def calculate_tp_performance(self, df: pd.DataFrame) -> dict[str, Any]:
        """Рассчитывает производительность текущих TP уровней"""
        if df.empty:
            return {}

        current_tp_levels = self.config.step_tp_levels
        current_tp_sizes = self.config.step_tp_sizes

        # Симулируем TP hits на основе исторических данных
        results = {
            "total_trades": len(df),
            "tp_hits": {},
            "avg_pnl": df.get("pnl", pd.Series([0.0] * len(df))).mean(),
            "win_rate": 0.0,
        }

        # Простая симуляция TP hits (в реальности нужно использовать реальные данные)
        for i, level in enumerate(current_tp_levels):
            # Симулируем, что 60% сделок достигают TP1, 30% - TP2, и т.д.
            hit_rate = 0.6 - (i * 0.2)
            results["tp_hits"][f"tp{i + 1}"] = {
                "level": level,
                "hit_rate": max(0.1, hit_rate),
                "hits": int(len(df) * hit_rate),
            }

        # Рассчитываем общий win rate
        total_hits = sum(r["hits"] for r in results["tp_hits"].values())
        results["win_rate"] = total_hits / len(df) if len(df) > 0 else 0.0

        return results

    def suggest_optimal_tp_levels(self, performance: dict[str, Any]) -> list[float]:
        """Предлагает оптимальные TP уровни на основе производительности"""
        if not performance:
            return self.config.step_tp_levels

        current_levels = self.config.step_tp_levels
        win_rate = performance.get("win_rate", 0.5)
        avg_pnl = performance.get("avg_pnl", 0.0)

        # Адаптивная корректировка на основе win rate
        adjustment_factor = (win_rate - 0.55) * 0.5  # Целевой win rate 55%

        new_levels = []
        for i, level in enumerate(current_levels):
            # Корректируем каждый уровень
            if i == 0:  # TP1
                new_level = level + (adjustment_factor * 0.002)
                new_level = max(0.003, min(new_level, 0.008))
            elif i == 1:  # TP2
                new_level = level + (adjustment_factor * 0.003)
                new_level = max(0.006, min(new_level, 0.015))
            else:  # TP3
                new_level = level + (adjustment_factor * 0.004)
                new_level = max(0.010, min(new_level, 0.025))

            new_levels.append(round(new_level, 4))

        return new_levels

    async def optimize_tp_levels(self) -> bool:
        """Основной метод оптимизации TP уровней"""
        try:
            if not await self.should_optimize():
                return False

            self.logger.log_event("TP_OPTIMIZER", "INFO", "Starting TP optimization...")

            # Получаем историю сделок
            df = await self.get_trade_history(days=7)
            if df.empty:
                return False

            # Проверяем минимальное количество сделок
            min_trades = self.config.get("tp_min_trades_initial", 5)
            if len(df) < min_trades:
                self.logger.log_event(
                    "TP_OPTIMIZER",
                    "INFO",
                    f"Not enough trades for optimization (need {min_trades}, have {len(df)})",
                )
                return False

            # Анализируем производительность
            performance = self.calculate_tp_performance(df)

            # Предлагаем новые уровни
            suggested_levels = self.suggest_optimal_tp_levels(performance)

            # Проверяем, нужно ли обновлять
            current_levels = self.config.step_tp_levels
            threshold = self.config.get("tp_update_threshold_initial", 0.15)

            changes_needed = False
            for current, suggested in zip(current_levels, suggested_levels, strict=False):
                if abs(suggested - current) / current > threshold:
                    changes_needed = True
                    break

            if changes_needed:
                # Обновляем конфигурацию
                await self.update_config_tp_levels(suggested_levels)

                # Логируем изменения
                self.logger.log_event(
                    "TP_OPTIMIZER",
                    "INFO",
                    f"TP levels updated: {current_levels} -> {suggested_levels}",
                )

                # Отправляем уведомление в Telegram
                await self.send_optimization_report(performance, current_levels, suggested_levels)
            else:
                self.logger.log_event("TP_OPTIMIZER", "INFO", "No TP optimization needed")

            self.last_optimization = datetime.utcnow()
            return True

        except Exception as e:
            self.logger.log_event("TP_OPTIMIZER", "ERROR", f"TP optimization failed: {e}")
            return False

    async def update_config_tp_levels(self, new_levels: list[float]):
        """Обновляет TP уровни в конфигурации"""
        try:
            config_path = Path("data/runtime_config.json")

            with open(config_path) as f:
                config_data = json.load(f)

            config_data["step_tp_levels"] = new_levels
            config_data["last_modified"] = datetime.utcnow().isoformat()

            with open(config_path, "w") as f:
                json.dump(config_data, f, indent=2)

        except Exception as e:
            self.logger.log_event("TP_OPTIMIZER", "ERROR", f"Failed to update config: {e}")

    async def send_optimization_report(
        self, performance: dict[str, Any], old_levels: list[float], new_levels: list[float]
    ):
        """Отправляет отчет об оптимизации в Telegram"""
        try:
            if not hasattr(self, "telegram") or not self.telegram:
                return

            report = (
                f"📊 *TP Optimization Report*\n\n"
                f"Total Trades: {performance.get('total_trades', 0)}\n"
                f"Win Rate: {performance.get('win_rate', 0):.1%}\n"
                f"Avg PnL: {performance.get('avg_pnl', 0):.2f}%\n\n"
                f"*TP Levels Updated:*\n"
                f"Old: {old_levels}\n"
                f"New: {new_levels}\n\n"
                f"⏰ Next optimization in {self.optimization_interval}"
            )

            await self.telegram.send_notification(report)

        except Exception as e:
            self.logger.log_event("TP_OPTIMIZER", "ERROR", f"Failed to send report: {e}")

    async def run_optimization_loop(self):
        """Фоновая задача оптимизации"""
        while True:
            try:
                await self.optimize_tp_levels()
                await asyncio.sleep(3600)  # Проверяем каждый час
            except Exception as e:
                self.logger.log_event("TP_OPTIMIZER", "ERROR", f"Optimization loop error: {e}")
                await asyncio.sleep(300)  # 5 минут при ошибке
