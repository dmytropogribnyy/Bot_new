# strategies/strategy_manager.py

from datetime import datetime, timedelta, timezone
from typing import Any

from strategies.base_strategy import BaseStrategy
from strategies.grid_strategy import GridStrategy
from strategies.scalping_v1 import ScalpingV1
from strategies.tp_optimizer import TPOptimizer


class MarketRegimeDetector:
    """Детектор режима рынка для адаптивного выбора стратегий"""

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.volatility_threshold = 0.02  # 2% для определения высокой волатильности
        self.trend_threshold = 0.01  # 1% для определения тренда

    async def detect_regime(self, symbol: str, market_data: dict[str, Any]) -> str:
        """Определяет режим рынка: trending, ranging, volatile"""
        try:
            # Анализ волатильности
            atr_percent = market_data.get("atr_percent", 0)
            price_change = abs(market_data.get("price_change_percent", 0))

            # Анализ объема
            volume_ratio = market_data.get("volume_ratio", 1.0)

            # Определение режима
            if atr_percent > self.volatility_threshold * 2:
                return "volatile"
            elif price_change > self.trend_threshold and volume_ratio > 1.2:
                return "trending"
            else:
                return "ranging"

        except Exception as e:
            self.logger.log_event(
                "MARKET_REGIME", "ERROR", f"Failed to detect regime for {symbol}: {e}"
            )
            return "ranging"  # По умолчанию


class StrategyManager:
    """
    Менеджер стратегий с адаптивным переключением
    """

    def __init__(self, config, exchange_client, symbol_manager, logger):
        self.config = config
        self.exchange = exchange_client
        self.symbol_manager = symbol_manager
        self.logger = logger

        # Инициализация стратегий
        self.strategies = {
            "scalping": ScalpingV1(config, exchange_client, symbol_manager, logger),
            "tp_optimizer": TPOptimizer(config, exchange_client, symbol_manager, logger),
            "grid": GridStrategy(config, exchange_client, symbol_manager, logger),
        }

        # Детектор режима рынка
        self.regime_detector = MarketRegimeDetector(config, logger)

        # Текущие активные стратегии по символам
        self.active_strategies: dict[str, str] = {}

        # Статистика производительности стратегий
        self.strategy_performance: dict[str, dict[str, float]] = {
            "scalping": {"win_rate": 0.5, "avg_pnl": 0.0, "trades_count": 0},
            "tp_optimizer": {"win_rate": 0.5, "avg_pnl": 0.0, "trades_count": 0},
            "grid": {"win_rate": 0.5, "avg_pnl": 0.0, "trades_count": 0},
        }

        # Временные окна для анализа
        self.performance_window = timedelta(hours=24)
        self.last_performance_update = datetime.now(timezone.utc)

    async def get_optimal_strategy(self, symbol: str, market_data: dict[str, Any]) -> BaseStrategy:
        """Выбирает оптимальную стратегию для символа"""
        try:
            # Определяем режим рынка
            regime = await self.regime_detector.detect_regime(symbol, market_data)

            # Выбираем стратегию на основе режима и производительности
            strategy_name = await self._select_strategy_by_regime(regime, symbol)

            # Обновляем активную стратегию
            self.active_strategies[symbol] = strategy_name

            self.logger.log_event(
                "STRATEGY_MANAGER",
                "INFO",
                f"Selected {strategy_name} for {symbol} (regime: {regime})",
            )

            return self.strategies[strategy_name]

        except Exception as e:
            self.logger.log_event(
                "STRATEGY_MANAGER", "ERROR", f"Strategy selection failed for {symbol}: {e}"
            )
            return self.strategies["scalping"]  # Fallback

    async def _select_strategy_by_regime(self, regime: str, symbol: str) -> str:
        """Выбирает стратегию на основе режима рынка"""

        # Получаем производительность стратегий
        scalping_perf = self.strategy_performance["scalping"]
        tp_perf = self.strategy_performance["tp_optimizer"]
        grid_perf = self.strategy_performance["grid"]

        if regime == "trending":
            # В трендовом рынке предпочитаем scalping
            if scalping_perf["win_rate"] > tp_perf["win_rate"]:
                return "scalping"
            else:
                return "tp_optimizer"

        elif regime == "ranging":
            # В боковом рынке предпочитаем grid strategy
            if grid_perf["win_rate"] > tp_perf["win_rate"]:
                return "grid"
            elif tp_perf["win_rate"] > scalping_perf["win_rate"]:
                return "tp_optimizer"
            else:
                return "scalping"

        else:  # volatile
            # В волатильном рынке используем лучшую по производительности
            if scalping_perf["avg_pnl"] > tp_perf["avg_pnl"]:
                return "scalping"
            else:
                return "tp_optimizer"

    async def update_strategy_performance(self, strategy_name: str, trade_result: dict[str, Any]):
        """Обновляет статистику производительности стратегии на основе реальных сделок"""
        try:
            if strategy_name not in self.strategy_performance:
                return

            perf = self.strategy_performance[strategy_name]

            # Получаем данные о сделке
            pnl = trade_result.get("pnl", 0)
            is_win = trade_result.get("win", pnl > 0)
            trade_duration = trade_result.get("duration", 0)
            entry_price = trade_result.get("entry_price", 0)
            exit_price = trade_result.get("exit_price", 0)

            # Обновляем статистику
            trades_count = perf["trades_count"] + 1

            # Обновляем win rate
            if is_win:
                win_rate = (perf["win_rate"] * perf["trades_count"] + 1) / trades_count
            else:
                win_rate = (perf["win_rate"] * perf["trades_count"]) / trades_count

            # Обновляем средний PnL
            avg_pnl = (perf["avg_pnl"] * perf["trades_count"] + pnl) / trades_count

            # Добавляем новые метрики
            if "total_pnl" not in perf:
                perf["total_pnl"] = 0.0
                perf["max_drawdown"] = 0.0
                perf["avg_trade_duration"] = 0.0
                perf["best_trade"] = 0.0
                perf["worst_trade"] = 0.0

            perf["total_pnl"] += pnl
            perf["avg_trade_duration"] = (
                perf["avg_trade_duration"] * perf["trades_count"] + trade_duration
            ) / trades_count

            # Обновляем лучшую/худшую сделку
            if pnl > perf["best_trade"]:
                perf["best_trade"] = pnl
            if pnl < perf["worst_trade"]:
                perf["worst_trade"] = pnl

            # Обновляем данные
            perf["trades_count"] = trades_count
            perf["win_rate"] = win_rate
            perf["avg_pnl"] = avg_pnl

            # Рассчитываем ROI
            if perf["trades_count"] > 0:
                perf["roi"] = (perf["total_pnl"] / perf["trades_count"]) * 100

            self.logger.log_event(
                "STRATEGY_MANAGER",
                "DEBUG",
                f"Updated {strategy_name} performance: WR={win_rate:.2f}, AvgPnL={avg_pnl:.4f}, ROI={perf.get('roi', 0):.2f}%",
            )

        except Exception as e:
            self.logger.log_event("STRATEGY_MANAGER", "ERROR", f"Failed to update performance: {e}")

    async def get_strategy_status(self) -> dict[str, Any]:
        """Возвращает детальный статус всех стратегий"""
        status = {
            "active_strategies": self.active_strategies,
            "performance": self.strategy_performance,
            "total_strategies": len(self.strategies),
            "regime_distribution": {},
            "recommendations": [],
        }

        # Анализируем распределение режимов рынка
        regime_counts = {}
        for symbol, strategy in self.active_strategies.items():
            regime_counts[strategy] = regime_counts.get(strategy, 0) + 1

        status["regime_distribution"] = regime_counts

        # Генерируем рекомендации
        for strategy_name, perf in self.strategy_performance.items():
            if perf["trades_count"] >= 10:  # Минимум сделок для анализа
                if perf["win_rate"] < 0.4:
                    status["recommendations"].append(
                        f"⚠️ {strategy_name}: Низкий win rate ({perf['win_rate']:.1%})"
                    )
                elif perf["avg_pnl"] < -0.001:
                    status["recommendations"].append(
                        f"📉 {strategy_name}: Отрицательный PnL ({perf['avg_pnl']:.4f})"
                    )
                elif perf["win_rate"] > 0.7 and perf["avg_pnl"] > 0.002:
                    status["recommendations"].append(
                        f"✅ {strategy_name}: Отличная производительность (WR: {perf['win_rate']:.1%}, PnL: {perf['avg_pnl']:.4f})"
                    )

        return status

    async def force_strategy_switch(self, symbol: str, strategy_name: str) -> bool:
        """Принудительно переключает стратегию для символа"""
        if strategy_name not in self.strategies:
            self.logger.log_event("STRATEGY_MANAGER", "ERROR", f"Unknown strategy: {strategy_name}")
            return False

        self.active_strategies[symbol] = strategy_name
        self.logger.log_event(
            "STRATEGY_MANAGER", "INFO", f"Force switched {symbol} to {strategy_name}"
        )
        return True

    async def get_hybrid_signal(
        self, symbol: str, market_data: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Получает гибридный сигнал от нескольких стратегий"""
        try:
            # Получаем сигналы от всех стратегий
            signals = []
            weights = []

            for strategy_name, strategy in self.strategies.items():
                signal = await strategy.analyze_market(symbol)
                if signal:
                    signals.append(signal)
                    # Вес на основе производительности
                    perf = self.strategy_performance[strategy_name]
                    weight = perf["win_rate"] * 0.7 + (perf["avg_pnl"] + 1) * 0.3
                    weights.append(max(weight, 0.1))  # Минимальный вес 0.1

            if not signals:
                return None

            # Нормализуем веса
            total_weight = sum(weights)
            weights = [w / total_weight for w in weights]

            # Вычисляем взвешенный сигнал
            weighted_signal = {
                "side": signals[0]
                .get("direction", "buy")
                .upper(),  # Берем direction и конвертируем в side
                "entry_price": sum(
                    s.get("entry_price", 0) * w for s, w in zip(signals, weights, strict=False)
                ),
                "confidence": sum(
                    s.get("strength", 0) * w for s, w in zip(signals, weights, strict=False)
                ),
            }

            self.logger.log_event(
                "STRATEGY_MANAGER", "DEBUG", f"Hybrid signal for {symbol}: {weighted_signal}"
            )

            return weighted_signal

        except Exception as e:
            self.logger.log_event(
                "STRATEGY_MANAGER", "ERROR", f"Hybrid signal failed for {symbol}: {e}"
            )
            return None

    async def cleanup_old_performance_data(self):
        """Очищает старые данные производительности"""
        current_time = datetime.utcnow()
        if current_time - self.last_performance_update > timedelta(hours=1):
            # Сбрасываем статистику каждые 24 часа
            for strategy_name in self.strategy_performance:
                self.strategy_performance[strategy_name] = {
                    "win_rate": 0.5,
                    "avg_pnl": 0.0,
                    "trades_count": 0,
                }
            self.last_performance_update = current_time

    def get_position_count(self) -> int:
        """Возвращает количество активных позиций"""
        try:
            # Простая реализация - возвращаем 0 для тестирования
            return 0
        except Exception as e:
            self.logger.log_event("STRATEGY_MANAGER", "ERROR", f"Error getting position count: {e}")
            return 0
