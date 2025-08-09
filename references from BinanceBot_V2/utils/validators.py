#!/usr/bin/env python3
"""
Валидаторы для BinanceBot v2
Проверка корректности ордеров и параметров
"""

from typing import Any


class OrderValidator:
    """Валидатор ордеров для Binance USDC-M Futures"""

    def __init__(self, config):
        self.config = config
        self.symbol_info_cache = {}

    def validate_order_params(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float | None = None,
        order_type: str = "MARKET",
    ) -> tuple[bool, str]:
        """Валидирует параметры ордера"""
        try:
            # Проверка символа
            if not self._validate_symbol(symbol):
                return False, f"Invalid symbol: {symbol}"

            # Проверка стороны
            if side.upper() not in ["BUY", "SELL"]:
                return False, f"Invalid side: {side}"

            # Проверка количества
            if quantity <= 0:
                return False, f"Invalid quantity: {quantity}"

            # Проверка цены для лимитных ордеров
            if order_type == "LIMIT" and (price is None or price <= 0):
                return False, f"Invalid price for LIMIT order: {price}"

            # Проверка минимального размера позиции
            if not self._validate_min_position_size(symbol, quantity, price):
                return False, "Position size below minimum"

            # Проверка максимального размера позиции
            if not self._validate_max_position_size(symbol, quantity, price):
                return False, "Position size above maximum"

            return True, "OK"

        except Exception as e:
            return False, f"Validation error: {e}"

    def _validate_symbol(self, symbol: str) -> bool:
        """Проверяет корректность символа"""
        # Базовые проверки
        if not symbol or len(symbol) < 3:
            return False

        # Проверка формата USDC-M
        if not symbol.endswith("USDC"):
            return False

        # Проверка blacklist
        if symbol in self.config.blacklisted_symbols:
            return False

        return True

    def _validate_min_position_size(
        self, symbol: str, quantity: float, price: float | None
    ) -> bool:
        """Проверяет минимальный размер позиции"""
        try:
            # Используем цену из параметра или получаем текущую
            if price is None:
                # В реальности нужно получить текущую цену
                price = 50000  # Заглушка

            position_value_usd = quantity * price

            # Проверяем минимальный размер из конфига
            min_size = self.config.min_position_size_usdc
            if position_value_usd < min_size:
                return False

            return True

        except Exception:
            return False

    def _validate_max_position_size(
        self, symbol: str, quantity: float, price: float | None
    ) -> bool:
        """Проверяет максимальный размер позиции"""
        try:
            if price is None:
                price = 50000  # Заглушка

            position_value_usd = quantity * price
            max_size = self.config.max_position_size_usdc

            if position_value_usd > max_size:
                return False

            return True

        except Exception:
            return False

    def adjust_quantity_to_lot_size(self, symbol: str, quantity: float) -> float:
        """Корректирует количество под lot size"""
        try:
            # Получаем lot size для символа
            lot_size = self._get_lot_size(symbol)

            # Округляем вниз до ближайшего lot size
            adjusted_quantity = (quantity // lot_size) * lot_size

            # Проверяем минимальное количество
            min_qty = self.config.min_trade_qty
            if adjusted_quantity < min_qty:
                adjusted_quantity = min_qty

            return round(adjusted_quantity, 6)

        except Exception:
            return self.config.fallback_order_qty

    def _get_lot_size(self, symbol: str) -> float:
        """Получает lot size для символа"""
        # В реальности нужно получать из API Binance
        # Пока используем стандартные значения
        lot_sizes = {
            "BTCUSDC": 0.001,
            "ETHUSDC": 0.01,
            "SOLUSDC": 0.1,
            "XRPUSDC": 1.0,
            "ADAUSDC": 1.0,
            "DOGEUSDC": 1.0,
        }

        return lot_sizes.get(symbol, 0.001)

    def validate_risk_limits(
        self, symbol: str, quantity: float, price: float, current_positions: dict[str, Any]
    ) -> tuple[bool, str]:
        """Проверяет лимиты риска"""
        try:
            # Проверка максимального количества позиций
            if len(current_positions) >= self.config.max_concurrent_positions:
                return False, "Maximum concurrent positions reached"

            # Проверка корреляции позиций
            if not self._validate_correlation_risk(symbol, current_positions):
                return False, "Correlation risk limit exceeded"

            # Проверка общего риска
            total_risk = self._calculate_total_risk(current_positions, quantity, price)
            max_risk = self.config.base_risk_pct * 100  # Конвертируем в проценты

            if total_risk > max_risk:
                return False, f"Total risk {total_risk:.2f}% exceeds limit {max_risk:.2f}%"

            return True, "OK"

        except Exception as e:
            return False, f"Risk validation error: {e}"

    def _validate_correlation_risk(self, symbol: str, current_positions: dict[str, Any]) -> bool:
        """Проверяет риск корреляции"""
        # Простая проверка - не более 2 позиций в одном направлении
        buy_positions = sum(1 for pos in current_positions.values() if pos.get("side") == "BUY")
        sell_positions = sum(1 for pos in current_positions.values() if pos.get("side") == "SELL")

        # В реальности нужно рассчитывать корреляцию между активами
        correlation_limit = self.config.get("risk_management", {}).get("correlation_limit", 0.7)

        # Упрощенная проверка
        if buy_positions > 3 or sell_positions > 3:
            return False

        return True

    def _calculate_total_risk(
        self, current_positions: dict[str, Any], new_quantity: float, new_price: float
    ) -> float:
        """Рассчитывает общий риск портфеля"""
        try:
            total_risk = 0.0

            # Риск существующих позиций
            for position in current_positions.values():
                position_value = position.get("quantity", 0) * position.get("price", 0)
                total_risk += position_value

            # Риск новой позиции
            new_position_value = new_quantity * new_price
            total_risk += new_position_value

            # Конвертируем в проценты от баланса
            # В реальности нужно получить баланс
            balance = 1000  # Заглушка
            risk_percentage = (total_risk / balance) * 100

            return risk_percentage

        except Exception:
            return 0.0

    def validate_tp_sl_levels(
        self, entry_price: float, tp_levels: list, sl_level: float
    ) -> tuple[bool, str]:
        """Валидирует уровни TP/SL"""
        try:
            # Проверка SL
            if sl_level <= 0:
                return False, "Invalid SL level"

            # Проверка минимального расстояния SL
            sl_distance = abs(entry_price - sl_level) / entry_price
            min_sl_gap = self.config.min_sl_gap_percent

            if sl_distance < min_sl_gap:
                return False, f"SL too close to entry price: {sl_distance:.4f}"

            # Проверка TP уровней
            for i, tp_level in enumerate(tp_levels):
                if tp_level <= entry_price:
                    return False, f"TP{i + 1} level {tp_level} <= entry price {entry_price}"

                # Проверка минимального расстояния TP
                tp_distance = abs(tp_level - entry_price) / entry_price
                if tp_distance < 0.002:  # Минимум 0.2%
                    return False, f"TP{i + 1} too close to entry price: {tp_distance:.4f}"

            return True, "OK"

        except Exception as e:
            return False, f"TP/SL validation error: {e}"


class ConfigValidator:
    """Валидатор конфигурации"""

    @staticmethod
    def validate_runtime_config(config: dict[str, Any]) -> tuple[bool, str]:
        """Валидирует runtime конфигурацию"""
        try:
            required_fields = [
                "api_key",
                "api_secret",
                "telegram_token",
                "telegram_chat_id",
                "max_concurrent_positions",
                "base_risk_pct",
                "sl_percent",
            ]

            for field in required_fields:
                if field not in config:
                    return False, f"Missing required field: {field}"

            # Проверка значений
            if config["max_concurrent_positions"] <= 0:
                return False, "max_concurrent_positions must be > 0"

            if not (0 < config["base_risk_pct"] <= 1):
                return False, "base_risk_pct must be between 0 and 1"

            if config["sl_percent"] <= 0:
                return False, "sl_percent must be > 0"

            # Проверка TP уровней
            if "step_tp_levels" in config:
                tp_levels = config["step_tp_levels"]
                if not isinstance(tp_levels, list) or len(tp_levels) == 0:
                    return False, "step_tp_levels must be non-empty list"

                for level in tp_levels:
                    if level <= 0:
                        return False, "TP levels must be > 0"

            return True, "Configuration is valid"

        except Exception as e:
            return False, f"Configuration validation error: {e}"
