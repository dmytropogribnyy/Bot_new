# strategies/grid_strategy.py

from datetime import datetime, timedelta
from typing import Any

from strategies.base_strategy import BaseStrategy
from core.aggression_manager import AggressionManager


class GridStrategy(BaseStrategy):
    """
    Grid Trading стратегия для боковых рынков.
    Создает сетку ордеров выше и ниже текущей цены.
    """

    def __init__(self, config, exchange_client, symbol_manager, logger):
        super().__init__(config, exchange_client, symbol_manager, logger)

        # Инициализируем AggressionManager для динамических настроек
        self.aggression_manager = AggressionManager(config, logger)

        # Получаем настройки с учетом агрессивности
        self._update_settings_from_aggression()

        # Активные сетки по символам
        self.active_grids: dict[str, dict[str, Any]] = {}

        # Статистика сетки
        self.grid_stats: dict[str, dict[str, Any]] = {}

    def _update_settings_from_aggression(self):
        """Обновляет настройки стратегии с учетом уровня агрессивности"""
        try:
            settings = self.aggression_manager.get_strategy_settings("grid")

            # Обновляем параметры из настроек агрессивности
            self.grid_levels = settings.get("grid_levels", 5)
            self.grid_spacing = settings.get("grid_spacing", 0.004)
            self.grid_range = settings.get("grid_range", 0.020)
            self.min_order_size = settings.get("min_order_size", 12)
            self.min_position_size_usdc = settings.get("min_position_size_usdc", 12)
            self.max_position_size_usdc = settings.get("max_position_size_usdc", 50)

            # Логируем обновление настроек
            self.logger.log_strategy_event("grid", "SETTINGS_UPDATED", {
                "aggression_level": self.aggression_manager.get_aggression_level(),
                "grid_levels": self.grid_levels,
                "grid_spacing": self.grid_spacing,
                "grid_range": self.grid_range,
                "min_order_size": self.min_order_size
            })

        except Exception as e:
            self.logger.log_event("STRATEGY", "ERROR", f"Failed to update settings from AggressionManager: {e}")
            # Fallback к базовым настройкам
            self.grid_levels = 5
            self.grid_spacing = 0.004
            self.grid_range = 0.020
            self.min_order_size = 12
            self.min_position_size_usdc = 12
            self.max_position_size_usdc = 50

    async def analyze_market(self, symbol: str) -> dict[str, Any] | None:
        """
        Анализирует рынок для создания/обновления сетки.
        Возвращает сигнал только для инициализации сетки.
        """
        try:
            # Получаем текущую цену
            ticker = await self.exchange.get_ticker(symbol)
            if not ticker:
                return None

            # Проверяем разные возможные ключи для цены
            if "lastPrice" in ticker:
                current_price = float(ticker["lastPrice"])
            elif "last" in ticker:
                current_price = float(ticker["last"])
            else:
                self.logger.log_event("GRID_STRATEGY", "ERROR", f"No price found in ticker for {symbol}")
                return None

            # Проверяем, нужна ли новая сетка
            if await self._should_create_grid(symbol, current_price):
                return await self._create_grid_signal(symbol, current_price)

            # Проверяем, нужно ли обновить существующую сетку
            if await self._should_update_grid(symbol, current_price):
                await self._update_grid(symbol, current_price)

            return None

        except Exception as e:
            self.logger.log_event(
                "GRID_STRATEGY", "ERROR", f"Failed to analyze market for {symbol}: {e}"
            )
            return None

    async def should_exit(self, symbol: str, position_data: dict[str, Any]) -> bool:
        """
        Определяет, следует ли закрыть позицию в сетке.
        В grid trading позиции закрываются автоматически при исполнении противоположных ордеров.
        """
        try:
            # В grid trading позиции закрываются автоматически
            # Проверяем только экстремальные условия для принудительного закрытия

            current_price = await self._get_current_price(symbol)
            if not current_price:
                return False

            position_side = position_data.get("side", "LONG")
            entry_price = position_data.get("entry_price", 0)

            # Принудительное закрытие при сильном движении против позиции
            if position_side == "LONG":
                loss_threshold = entry_price * (1 - self.grid_range * 2)  # Двойной диапазон сетки
                return current_price < loss_threshold
            else:
                profit_threshold = entry_price * (1 + self.grid_range * 2)
                return current_price > profit_threshold

        except Exception as e:
            self.logger.log_event(
                "GRID_STRATEGY", "ERROR", f"Failed to check exit for {symbol}: {e}"
            )
            return False

    async def _should_create_grid(self, symbol: str, current_price: float) -> bool:
        """Определяет, нужно ли создать новую сетку"""
        if symbol not in self.active_grids:
            return True

        grid = self.active_grids[symbol]
        grid_center = grid.get("center_price", 0)

        # Создаем новую сетку, если цена ушла слишком далеко от центра
        price_deviation = abs(current_price - grid_center) / grid_center
        return price_deviation > self.grid_range

    async def _should_update_grid(self, symbol: str, current_price: float) -> bool:
        """Определяет, нужно ли обновить существующую сетку"""
        if symbol not in self.active_grids:
            return False

        grid = self.active_grids[symbol]
        last_update = grid.get("last_update", datetime.min)

        # Обновляем каждые 30 минут
        return datetime.utcnow() - last_update > timedelta(minutes=30)

    async def _create_grid_signal(self, symbol: str, current_price: float) -> dict[str, Any]:
        """Создает сигнал для инициализации сетки с улучшенной логикой"""
        try:
            # Проверяем рыночные условия для grid trading
            market_conditions = await self._validate_grid_conditions(symbol, current_price)
            if not market_conditions["suitable"]:
                self.logger.log_event(
                    "GRID_STRATEGY", "DEBUG",
                    f"Grid not suitable for {symbol}: {market_conditions['reason']}"
                )
                return None

            # Создаем уровни сетки с адаптивными параметрами
            grid_levels = self._calculate_adaptive_grid_levels(current_price, market_conditions)

            # Сохраняем информацию о сетке
            self.active_grids[symbol] = {
                "center_price": current_price,
                "levels": grid_levels,
                "created_at": datetime.utcnow(),
                "last_update": datetime.utcnow(),
                "total_orders": len(grid_levels),
                "executed_orders": 0,
                "market_conditions": market_conditions,
                "total_investment": 0.0,
                "current_pnl": 0.0
            }

            # Инициализируем статистику
            self.grid_stats[symbol] = {
                "total_trades": 0,
                "total_pnl": 0.0,
                "win_rate": 0.0,
                "avg_trade_pnl": 0.0,
                "grid_efficiency": 0.0,
                "max_drawdown": 0.0
            }

            self.logger.log_event(
                "GRID_STRATEGY", "INFO",
                f"Created adaptive grid for {symbol} at {current_price} with {len(grid_levels)} levels"
            )

            return {
                "side": "GRID_INIT",
                "entry_price": current_price,
                "confidence": market_conditions["confidence"],
                "grid_levels": grid_levels,
                "strategy": "grid",
                "market_conditions": market_conditions
            }

        except Exception as e:
            self.logger.log_event(
                "GRID_STRATEGY", "ERROR", f"Failed to create grid signal for {symbol}: {e}"
            )
            return None

    async def _validate_grid_conditions(self, symbol: str, current_price: float) -> dict[str, Any]:
        """Проверяет подходящие ли условия для grid trading"""
        try:
            # Получаем исторические данные
            ohlcv_data = await self.symbol_manager.get_recent_ohlcv(symbol)
            if ohlcv_data is None or len(ohlcv_data) < 50:
                return {"suitable": False, "reason": "Insufficient data", "confidence": 0.0}

            # Конвертируем в DataFrame
            import pandas as pd
            df = pd.DataFrame(ohlcv_data)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            # Анализируем волатильность
            volatility = df["close"].pct_change().rolling(20).std().iloc[-1] * 100

            # Анализируем тренд
            sma_20 = df["close"].rolling(20).mean().iloc[-1]
            trend_strength = abs(current_price - sma_20) / sma_20 * 100

            # Анализируем объем
            volume_ratio = df["volume"].iloc[-10:].mean() / df["volume"].iloc[-50:].mean()

            # Определяем подходящие условия для grid
            suitable = True
            reason = "OK"
            confidence = 0.7

            if volatility < 0.5:  # Слишком низкая волатильность
                suitable = False
                reason = "Low volatility"
                confidence = 0.3
            elif volatility > 3.0:  # Слишком высокая волатильность
                suitable = False
                reason = "High volatility"
                confidence = 0.4
            elif trend_strength > 2.0:  # Сильный тренд
                suitable = False
                reason = "Strong trend"
                confidence = 0.5
            elif volume_ratio < 0.8:  # Низкий объем
                suitable = False
                reason = "Low volume"
                confidence = 0.4

            # Корректируем уверенность на основе условий
            if suitable:
                confidence = min(0.9, 0.7 + (volatility * 0.1) + (volume_ratio * 0.1))

            return {
                "suitable": suitable,
                "reason": reason,
                "confidence": confidence,
                "volatility": volatility,
                "trend_strength": trend_strength,
                "volume_ratio": volume_ratio
            }

        except Exception as e:
            self.logger.log_event(
                "GRID_STRATEGY", "ERROR", f"Failed to validate grid conditions for {symbol}: {e}"
            )
            return {"suitable": False, "reason": "Validation error", "confidence": 0.0}

    def _calculate_adaptive_grid_levels(self, center_price: float, market_conditions: dict[str, Any]) -> list[dict[str, Any]]:
        """Рассчитывает адаптивные уровни сетки на основе рыночных условий"""
        levels = []

        # Адаптируем параметры сетки на основе волатильности
        volatility = market_conditions.get("volatility", 1.0)
        adaptive_spacing = self.grid_spacing * (1 + (volatility - 1.0) * 0.5)
        adaptive_levels = max(5, min(self.grid_levels, int(10 / volatility)))

        # Создаем уровни выше и ниже центральной цены
        for i in range(-adaptive_levels, adaptive_levels + 1):
            if i == 0:  # Пропускаем центральный уровень
                continue

            price_offset = i * adaptive_spacing
            level_price = center_price * (1 + price_offset)

            # Определяем сторону ордера
            if i > 0:  # Уровни выше центра - продажа
                side = "SELL"
            else:  # Уровни ниже центра - покупка
                side = "BUY"

            # Рассчитываем размер ордера на основе расстояния от центра
            distance_factor = abs(i) / adaptive_levels
            order_size = self.min_order_size * (1 + distance_factor * 0.5)

            levels.append({
                "level": i,
                "price": level_price,
                "side": side,
                "status": "PENDING",
                "order_id": None,
                "size": order_size,
                "distance_factor": distance_factor
            })

        return levels

    async def _update_grid(self, symbol: str, current_price: float):
        """Обновляет существующую сетку"""
        try:
            grid = self.active_grids[symbol]
            grid["last_update"] = datetime.utcnow()

            # Проверяем исполненные ордера
            await self._check_filled_orders(symbol)

            # Пересчитываем уровни если нужно
            if await self._should_recalculate_grid(symbol, current_price):
                new_levels = self._calculate_grid_levels(current_price)
                grid["levels"] = new_levels
                grid["center_price"] = current_price

                self.logger.log_event(
                    "GRID_STRATEGY", "INFO",
                    f"Updated grid for {symbol} at {current_price}"
                )

        except Exception as e:
            self.logger.log_event(
                "GRID_STRATEGY", "ERROR", f"Failed to update grid for {symbol}: {e}"
            )

    async def _check_filled_orders(self, symbol: str):
        """Проверяет исполненные ордера в сетке"""
        try:
            grid = self.active_grids[symbol]

            for level in grid["levels"]:
                if level["status"] == "PENDING" and level["order_id"]:
                    # Проверяем статус ордера
                    order_status = await self.exchange.get_order_status(
                        symbol, level["order_id"]
                    )

                    if order_status and order_status.get("status") == "FILLED":
                        level["status"] = "FILLED"
                        grid["executed_orders"] += 1

                        # Логируем исполнение
                        self.logger.log_event(
                            "GRID_STRATEGY", "INFO",
                            f"Grid order filled: {symbol} {level['side']} at {level['price']}"
                        )

                        # Обновляем статистику
                        await self._update_grid_stats(symbol, level)

        except Exception as e:
            self.logger.log_event(
                "GRID_STRATEGY", "ERROR", f"Failed to check filled orders for {symbol}: {e}"
            )

    async def _should_recalculate_grid(self, symbol: str, current_price: float) -> bool:
        """Определяет, нужно ли пересчитать сетку"""
        grid = self.active_grids[symbol]
        center_price = grid["center_price"]

        # Пересчитываем, если цена ушла более чем на 50% от диапазона сетки
        deviation = abs(current_price - center_price) / center_price
        return deviation > self.grid_range * 0.5

    async def _update_grid_stats(self, symbol: str, filled_level: dict[str, Any]):
        """Обновляет статистику сетки"""
        try:
            stats = self.grid_stats[symbol]
            stats["total_trades"] += 1

            # Простая оценка PnL (в реальности нужно учитывать комиссии)
            # Здесь можно добавить более сложную логику расчета PnL

            self.logger.log_event(
                "GRID_STRATEGY", "DEBUG",
                f"Updated stats for {symbol}: {stats}"
            )

        except Exception as e:
            self.logger.log_event(
                "GRID_STRATEGY", "ERROR", f"Failed to update grid stats for {symbol}: {e}"
            )

    async def _get_current_price(self, symbol: str) -> float | None:
        """Получает текущую цену символа"""
        try:
            ticker = await self.exchange.get_ticker(symbol)
            return float(ticker["lastPrice"]) if ticker else None
        except Exception as e:
            self.logger.log_event(
                "GRID_STRATEGY", "ERROR", f"Failed to get price for {symbol}: {e}"
            )
            return None

    async def get_grid_status(self, symbol: str) -> dict[str, Any] | None:
        """Возвращает статус сетки для символа"""
        if symbol not in self.active_grids:
            return None

        grid = self.active_grids[symbol]
        stats = self.grid_stats.get(symbol, {})

        return {
            "center_price": grid["center_price"],
            "total_levels": grid["total_orders"],
            "executed_orders": grid["executed_orders"],
            "completion_rate": grid["executed_orders"] / grid["total_orders"],
            "created_at": grid["created_at"],
            "last_update": grid["last_update"],
            "stats": stats
        }

    async def get_all_grids_status(self) -> dict[str, Any]:
        """Возвращает статус всех активных сеток"""
        return {
            symbol: await self.get_grid_status(symbol)
            for symbol in self.active_grids.keys()
        }
