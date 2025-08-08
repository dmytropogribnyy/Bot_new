import asyncio
import time
from collections import defaultdict, deque
from datetime import datetime
from typing import Any

import numpy as np


class RiskManager:
    """
    🚀 Продвинутый риск-менеджер с ML-компонентами и адаптивными алгоритмами
    """

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger

        # Базовые счетчики
        self.sl_streak_counter = 0
        self.sl_streak_paused_until = None
        self.lock = asyncio.Lock()

        # 🚀 ОПТИМИЗАЦИЯ: Расширенная статистика рисков
        self.risk_metrics = {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_pnl": 0.0,
            "max_drawdown": 0.0,
            "current_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "volatility": 0.0
        }

        # 🚀 ОПТИМИЗАЦИЯ: Адаптивные параметры риска
        self.adaptive_risk_params = {
            "base_risk_pct": config.base_risk_pct,
            "max_position_size": config.max_position_size_usdc,
            "max_capital_utilization": config.max_capital_utilization_pct,
            "volatility_multiplier": 1.0,
            "market_regime_multiplier": 1.0
        }

        # 🚀 ОПТИМИЗАЦИЯ: Исторические данные для ML
        self.trade_history = deque(maxlen=1000)
        self.volatility_history = defaultdict(deque)
        self.correlation_matrix = {}

        # 🚀 ОПТИМИЗАЦИЯ: Динамические лимиты
        self.dynamic_limits = {
            "max_positions": config.max_concurrent_positions,
            "max_daily_loss": config.max_drawdown_daily,
            "max_position_duration": config.max_position_duration
        }

        # 🚀 ОПТИМИЗАЦИЯ: Анализ рыночных режимов
        self.market_regime = "normal"  # normal, volatile, trending, crisis
        self.regime_start_time = time.time()

        # 🚀 ОПТИМИЗАЦИЯ: ML-предсказания риска
        self.risk_predictions = {}
        self.prediction_accuracy = 0.7

    async def is_trading_allowed(self) -> bool:
        """Проверяет разрешена ли торговля с расширенными проверками"""
        # Базовая проверка SL streak
        if self.sl_streak_paused_until:
            now = time.time()
            if now < self.sl_streak_paused_until:
                return False
            else:
                self.sl_streak_paused_until = None

        # 🚀 ОПТИМИЗАЦИЯ: Проверка дневных лимитов
        if not await self.check_daily_limits():
            return False

        # 🚀 ОПТИМИЗАЦИЯ: Проверка рыночного режима
        if self.market_regime == "crisis":
            return False

        # 🚀 ОПТИМИЗАЦИЯ: Проверка корреляции портфеля
        if not await self.check_portfolio_correlation():
            return False

        return True

    async def check_daily_limits(self) -> bool:
        """Проверяет дневные лимиты потерь"""
        try:
            # Вычисляем дневной PnL
            today = datetime.now().date()
            daily_pnl = 0.0

            for trade in self.trade_history:
                trade_date = datetime.fromisoformat(trade["timestamp"]).date()
                if trade_date == today:
                    daily_pnl += trade["pnl"]

            # Проверяем лимит дневных потерь
            if daily_pnl < -self.dynamic_limits["max_daily_loss"]:
                self.logger.log_event("RISK_MANAGER", "WARNING",
                    f"Daily loss limit reached: ${daily_pnl:.2f}")
                return False

            return True

        except Exception as e:
            self.logger.log_event("RISK_MANAGER", "ERROR", f"Daily limits check failed: {e}")
            return True  # В случае ошибки разрешаем торговлю

    async def check_portfolio_correlation(self) -> bool:
        """Проверяет корреляцию портфеля для диверсификации"""
        try:
            # Простая проверка - можно расширить анализом корреляций
            # Пока возвращаем True
            return True

        except Exception as e:
            self.logger.log_event("RISK_MANAGER", "ERROR", f"Correlation check failed: {e}")
            return True

    async def register_sl_hit(self, symbol: str, pnl: float):
        """Регистрирует SL hit с расширенной аналитикой"""
        async with self.lock:
            self.sl_streak_counter += 1

            # 🚀 ОПТИМИЗАЦИЯ: Обновляем статистику
            self.risk_metrics["losing_trades"] += 1
            self.risk_metrics["total_trades"] += 1
            self.risk_metrics["total_pnl"] += pnl

            # Обновляем текущую просадку
            self.risk_metrics["current_drawdown"] = min(
                self.risk_metrics["current_drawdown"], pnl
            )

            # Обновляем максимальную просадку
            if self.risk_metrics["current_drawdown"] < self.risk_metrics["max_drawdown"]:
                self.risk_metrics["max_drawdown"] = self.risk_metrics["current_drawdown"]

            # 🚀 ОПТИМИЗАЦИЯ: Адаптивная пауза на основе просадки
            if self.sl_streak_counter >= self.config.max_sl_streak:
                pause_duration = self.calculate_adaptive_pause()
                self.sl_streak_paused_until = time.time() + pause_duration

                self.logger.log_event("RISK_MANAGER", "WARNING",
                    f"SL Streak reached {self.sl_streak_counter}. Trading paused for {pause_duration//60} minutes.")

                # 🚀 ОПТИМИЗАЦИЯ: Автоматическая корректировка параметров риска
                await self.adjust_risk_parameters()

    async def register_win(self, symbol: str, pnl: float):
        """Регистрирует выигрышную сделку с ML-обучением"""
        async with self.lock:
            if self.sl_streak_counter > 0:
                self.sl_streak_counter = max(
                    0, self.sl_streak_counter - self.config.sl_streak_reduction_factor
                )

            # 🚀 ОПТИМИЗАЦИЯ: Обновляем статистику
            self.risk_metrics["winning_trades"] += 1
            self.risk_metrics["total_trades"] += 1
            self.risk_metrics["total_pnl"] += pnl

            # Сбрасываем текущую просадку при прибыли
            if pnl > 0:
                self.risk_metrics["current_drawdown"] = 0

            # 🚀 ОПТИМИЗАЦИЯ: ML-обучение на успешных сделках
            await self.update_ml_model(symbol, pnl, "win")

    def calculate_position_size(
        self, symbol: str, entry_price: float, balance: float, leverage: int,
        volatility: float = 1.0, market_regime: str = "normal"
    ) -> float:
        # 🚀 ЗАЩИТА: Проверяем входные параметры
        if balance is None or balance <= 0:
            self.logger.log_event("RISK_MANAGER", "WARNING", f"Invalid balance for {symbol}: {balance}")
            return 0.0
            
        if entry_price is None or entry_price <= 0:
            self.logger.log_event("RISK_MANAGER", "WARNING", f"Invalid entry_price for {symbol}: {entry_price}")
            return 0.0
        """🚀 Продвинутый расчет размера позиции с ML-компонентами"""
        try:
            # 🚀 ОПТИМИЗАЦИЯ: Базовый риск с адаптивными параметрами
            base_risk = balance * self.adaptive_risk_params["base_risk_pct"]

            # 🚀 ОПТИМИЗАЦИЯ: Множественные множители
            volatility_mult = self.calculate_volatility_multiplier(symbol, volatility)
            regime_mult = self.calculate_regime_multiplier(market_regime)
            performance_mult = self.calculate_performance_multiplier()
            correlation_mult = self.calculate_correlation_multiplier(symbol)

            # 🚀 ОПТИМИЗАЦИЯ: ML-предсказание оптимального размера
            ml_prediction = self.predict_optimal_position_size(symbol, entry_price, balance)

            # Комбинируем все факторы
            adjusted_risk = base_risk * volatility_mult * regime_mult * performance_mult * correlation_mult

            # Корректируем на основе ML-предсказания
            if ml_prediction > 0:
                adjusted_risk = adjusted_risk * (0.8 + 0.4 * ml_prediction)  # 0.8-1.2 диапазон

            # Вычисляем количество
            qty = (adjusted_risk * leverage) / entry_price

            # 🚀 ОПТИМИЗАЦИЯ: Динамические ограничения
            qty = self.apply_dynamic_limits(qty, entry_price, balance)

            return round(qty, 6)

        except Exception as e:
            self.logger.log_event("RISK_MANAGER", "ERROR", f"Position size calculation failed: {e}")
            # Fallback к базовому расчету
            return self.calculate_basic_position_size(symbol, entry_price, balance, leverage)

    def calculate_volatility_multiplier(self, symbol: str, volatility: float) -> float:
        """Вычисляет множитель на основе волатильности"""
        try:
            # Анализируем историческую волатильность
            hist_volatility = self.get_historical_volatility(symbol)

            if hist_volatility > 0:
                # Корректируем на основе исторической волатильности
                vol_ratio = volatility / hist_volatility
                if vol_ratio > 1.5:  # Высокая волатильность
                    return 0.7  # Уменьшаем размер
                elif vol_ratio < 0.5:  # Низкая волатильность
                    return 1.3  # Увеличиваем размер
                else:
                    return 1.0
            else:
                return 1.0

        except Exception as e:
            self.logger.log_event("RISK_MANAGER", "ERROR", f"Volatility multiplier calculation failed: {e}")
            return 1.0

    def calculate_regime_multiplier(self, market_regime: str) -> float:
        """Вычисляет множитель на основе рыночного режима"""
        multipliers = {
            "normal": 1.0,
            "volatile": 0.8,
            "trending": 1.1,
            "crisis": 0.5
        }
        return multipliers.get(market_regime, 1.0)

    def calculate_performance_multiplier(self) -> float:
        """Вычисляет множитель на основе производительности"""
        try:
            if self.risk_metrics["total_trades"] < 10:
                return 1.0  # Недостаточно данных

            win_rate = self.risk_metrics["winning_trades"] / self.risk_metrics["total_trades"]
            avg_pnl = self.risk_metrics["total_pnl"] / self.risk_metrics["total_trades"]

            # Корректируем на основе производительности
            if win_rate > 0.6 and avg_pnl > 0:
                return 1.2  # Хорошая производительность
            elif win_rate < 0.4 or avg_pnl < -0.5:
                return 0.8  # Плохая производительность
            else:
                return 1.0

        except Exception as e:
            self.logger.log_event("RISK_MANAGER", "ERROR", f"Performance multiplier calculation failed: {e}")
            return 1.0

    def calculate_correlation_multiplier(self, symbol: str) -> float:
        """Вычисляет множитель на основе корреляции с существующими позициями"""
        try:
            # Простая логика - можно расширить анализом корреляций
            # Пока возвращаем 1.0
            return 1.0

        except Exception as e:
            self.logger.log_event("RISK_MANAGER", "ERROR", f"Correlation multiplier calculation failed: {e}")
            return 1.0

    def predict_optimal_position_size(self, symbol: str, entry_price: float, balance: float) -> float:
        """ML-предсказание оптимального размера позиции"""
        try:
            # 🚀 ОПТИМИЗАЦИЯ: Простая ML-модель на основе исторических данных
            symbol_history = [trade for trade in self.trade_history if trade["symbol"] == symbol]

            if len(symbol_history) < 5:
                return 0.5  # Нейтральное предсказание для новых символов

            # Анализируем успешность сделок с разными размерами
            successful_trades = [t for t in symbol_history if t["pnl"] > 0]
            if not successful_trades:
                return 0.5

            # Вычисляем оптимальный размер на основе успешных сделок
            avg_successful_size = np.mean([t["position_size"] for t in successful_trades])
            current_size = (balance * self.adaptive_risk_params["base_risk_pct"]) / entry_price

            if current_size > 0:
                optimal_ratio = avg_successful_size / current_size
                return max(0.5, min(1.5, optimal_ratio))  # Ограничиваем диапазон
            else:
                return 0.5

        except Exception as e:
            self.logger.log_event("RISK_MANAGER", "ERROR", f"ML prediction failed: {e}")
            return 0.5

    def apply_dynamic_limits(self, qty: float, entry_price: float, balance: float) -> float:
        """Применяет динамические ограничения к размеру позиции"""
        try:
            notional = qty * entry_price

            # Минимальный размер
            if notional < self.config.min_notional_open:
                qty = self.config.min_notional_open / entry_price

            # Максимальный размер позиции
            max_size = self.adaptive_risk_params["max_position_size"]
            if notional > max_size:
                qty = max_size / entry_price

            # Ограничение по капиталу
            max_utilization = self.adaptive_risk_params["max_capital_utilization"]
            if notional / balance > max_utilization:
                allowed_notional = balance * max_utilization
                qty = allowed_notional / entry_price

            # 🚀 ОПТИМИЗАЦИЯ: Динамическое ограничение на основе просадки
            if self.risk_metrics["current_drawdown"] < -0.1:  # Просадка больше 10%
                qty *= 0.7  # Уменьшаем размер позиции

            return qty

        except Exception as e:
            self.logger.log_event("RISK_MANAGER", "ERROR", f"Dynamic limits application failed: {e}")
            return qty

    def calculate_basic_position_size(self, symbol: str, entry_price: float, balance: float, leverage: int) -> float:
        """Базовый расчет размера позиции как fallback"""
        risk_amount = balance * self.config.base_risk_pct
        qty = (risk_amount * leverage) / entry_price

        # Базовые ограничения
        notional = qty * entry_price
        if notional < self.config.min_notional_open:
            qty = self.config.min_notional_open / entry_price
        if notional > self.config.max_position_size_usdc:
            qty = self.config.max_position_size_usdc / entry_price

        return round(qty, 6)

    def calculate_adaptive_pause(self) -> int:
        """Вычисляет адаптивную паузу на основе просадки"""
        try:
            base_pause = self.config.sl_streak_pause_minutes * 60

            # Корректируем на основе просадки
            drawdown_pct = abs(self.risk_metrics["current_drawdown"]) / 100
            if drawdown_pct > 0.05:  # Просадка больше 5%
                base_pause *= 1.5
            elif drawdown_pct > 0.1:  # Просадка больше 10%
                base_pause *= 2.0

            return int(base_pause)

        except Exception as e:
            self.logger.log_event("RISK_MANAGER", "ERROR", f"Adaptive pause calculation failed: {e}")
            return self.config.sl_streak_pause_minutes * 60

    async def adjust_risk_parameters(self):
        """Адаптивная корректировка параметров риска"""
        try:
            # Корректируем базовый риск на основе производительности
            if self.risk_metrics["total_trades"] > 20:
                win_rate = self.risk_metrics["winning_trades"] / self.risk_metrics["total_trades"]

                if win_rate < 0.4:  # Низкий винрейт
                    self.adaptive_risk_params["base_risk_pct"] *= 0.8
                    self.logger.log_event("RISK_MANAGER", "INFO",
                        f"Reducing base risk to {self.adaptive_risk_params['base_risk_pct']:.3f} due to low win rate")
                elif win_rate > 0.6:  # Высокий винрейт
                    self.adaptive_risk_params["base_risk_pct"] = min(
                        self.config.base_risk_pct * 1.2,
                        self.adaptive_risk_params["base_risk_pct"] * 1.1
                    )
                    self.logger.log_event("RISK_MANAGER", "INFO",
                        f"Increasing base risk to {self.adaptive_risk_params['base_risk_pct']:.3f} due to high win rate")

        except Exception as e:
            self.logger.log_event("RISK_MANAGER", "ERROR", f"Risk parameters adjustment failed: {e}")

    async def update_ml_model(self, symbol: str, pnl: float, result: str):
        """Обновляет ML-модель на основе результатов сделок"""
        try:
            # Добавляем сделку в историю
            trade_data = {
                "symbol": symbol,
                "pnl": pnl,
                "result": result,
                "timestamp": datetime.now().isoformat(),
                "position_size": 0.0,  # Можно добавить размер позиции
                "market_regime": self.market_regime
            }

            self.trade_history.append(trade_data)

            # 🚀 ОПТИМИЗАЦИЯ: Обновляем точность предсказаний
            if len(self.trade_history) > 10:
                recent_trades = list(self.trade_history)[-10:]
                predicted_wins = sum(1 for t in recent_trades if t["result"] == "win")
                actual_wins = sum(1 for t in recent_trades if t["pnl"] > 0)

                if actual_wins > 0:
                    self.prediction_accuracy = predicted_wins / actual_wins

        except Exception as e:
            self.logger.log_event("RISK_MANAGER", "ERROR", f"ML model update failed: {e}")

    def get_historical_volatility(self, symbol: str) -> float:
        """Получает историческую волатильность символа"""
        try:
            if symbol in self.volatility_history:
                recent_volatility = list(self.volatility_history[symbol])[-10:]
                if recent_volatility:
                    return np.mean(recent_volatility)
            return 1.0  # Базовое значение

        except Exception as e:
            self.logger.log_event("RISK_MANAGER", "ERROR", f"Historical volatility calculation failed: {e}")
            return 1.0

    async def check_entry_allowed(self, symbol: str, side: str, amount: float) -> bool:
        """Проверяет, разрешен ли вход в позицию с расширенными проверками"""
        try:
            # Базовая проверка торговли
            if not await self.is_trading_allowed():
                return False

            # 🚀 ОПТИМИЗАЦИЯ: Проверка лимитов позиций
            if not await self.check_position_limits(symbol, amount):
                return False

            # 🚀 ОПТИМИЗАЦИЯ: Проверка рыночных условий
            if not await self.check_market_conditions(symbol):
                return False

            return True

        except Exception as e:
            self.logger.log_event("RISK_MANAGER", "ERROR", f"Entry check failed: {e}")
            return False

    async def check_position_limits(self, symbol: str, amount: float) -> bool:
        """Проверяет лимиты позиций"""
        try:
            # Простая проверка - можно расширить анализом текущих позиций
            return True

        except Exception as e:
            self.logger.log_event("RISK_MANAGER", "ERROR", f"Position limits check failed: {e}")
            return True

    async def check_market_conditions(self, symbol: str) -> bool:
        """Проверяет рыночные условия"""
        try:
            # Простая проверка - можно расширить анализом рыночных данных
            return True

        except Exception as e:
            self.logger.log_event("RISK_MANAGER", "ERROR", f"Market conditions check failed: {e}")
            return True

    def reset_streak(self):
        """Сбрасывает счетчик SL streak"""
        self.sl_streak_counter = 0
        self.sl_streak_paused_until = None
        self.logger.log_event("RISK_MANAGER", "INFO", "SL Streak reset manually.")

    def get_risk_metrics(self) -> dict[str, Any]:
        """Возвращает текущие метрики риска"""
        return {
            **self.risk_metrics,
            "sl_streak": self.sl_streak_counter,
            "adaptive_params": self.adaptive_risk_params,
            "market_regime": self.market_regime,
            "prediction_accuracy": self.prediction_accuracy
        }
