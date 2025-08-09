"""
Менеджер агрессивности для динамического управления настройками стратегий
"""

import time
from enum import Enum
from typing import Any


class AggressionLevel(Enum):
    """Уровни агрессивности"""

    CONSERVATIVE = "CONSERVATIVE"
    BALANCED = "BALANCED"
    AGGRESSIVE = "AGGRESSIVE"


class AggressionManager:
    """Менеджер для управления агрессивностью торговых стратегий"""

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.current_level = AggressionLevel(config.get("aggression_level", "BALANCED"))
        self.aggression_profiles = config.get("aggression_profiles", {})

        # Настройки для автоматического переключения
        self.auto_switch_enabled = config.get("auto_switch_enabled", False)
        self.market_conditions = {
            "volatility_threshold": config.get("volatility_threshold", 0.02),
            "trend_strength_threshold": config.get("trend_strength_threshold", 0.6),
            "volume_spike_threshold": config.get("volume_spike_threshold", 2.0),
            "market_sentiment_threshold": config.get("market_sentiment_threshold", 0.7),
        }

        # История изменений для предотвращения частых переключений
        self.last_switch_time = 0
        self.min_switch_interval = config.get("min_switch_interval", 3600)  # 1 час

    def set_aggression_level(self, level: str) -> bool:
        """Устанавливает уровень агрессивности"""
        try:
            new_level = AggressionLevel(level.upper())
            self.current_level = new_level

            # Применяем настройки профиля
            if level.upper() in self.aggression_profiles:
                profile = self.aggression_profiles[level.upper()]
                self._apply_profile_settings(profile)

            # Обновляем настройки стратегий
            self._update_strategy_aggression()

            self.logger.log_event(
                "AGGRESSION_MANAGER", "INFO", f"Уровень агрессивности изменен на: {level.upper()}"
            )
            return True

        except ValueError:
            self.logger.log_event(
                "AGGRESSION_MANAGER", "ERROR", f"Неверный уровень агрессивности: {level}"
            )
            return False

    def get_aggression_level(self) -> str:
        """Получает текущий уровень агрессивности"""
        return self.current_level.value

    def get_available_levels(self) -> list[str]:
        """Получает список доступных уровней агрессивности"""
        return [level.value for level in AggressionLevel]

    def get_profile_info(self, level: str = None) -> dict[str, Any]:
        """Получает информацию о профиле агрессивности"""
        if level is None:
            level = self.current_level.value

        if level.upper() in self.aggression_profiles:
            return self.aggression_profiles[level.upper()]
        return {}

    def _apply_profile_settings(self, profile: dict[str, Any]):
        """Применяет настройки профиля к конфигурации"""
        # Обновляем основные параметры
        for key, value in profile.items():
            if key != "description" and hasattr(self.config, key):
                setattr(self.config, key, value)

    def _update_strategy_aggression(self):
        """Обновляет настройки агрессивности стратегий"""
        strategy_config = self.config.get("strategy_config", {})

        for strategy_name, strategy_settings in strategy_config.items():
            if "aggressive_settings" in strategy_settings:
                # Определяем, нужно ли включить агрессивные настройки
                should_enable_aggressive = (
                    self.current_level == AggressionLevel.AGGRESSIVE
                    and strategy_settings.get("aggression_mode") == "AGGRESSIVE"
                )

                if should_enable_aggressive:
                    aggressive_settings = strategy_settings["aggressive_settings"]
                    # Применяем агрессивные настройки
                    for key, value in aggressive_settings.items():
                        if key != "enabled":
                            strategy_settings[key] = value

                    strategy_settings["aggression_mode"] = "AGGRESSIVE"
                    self.logger.log_event(
                        "AGGRESSION_MANAGER",
                        "INFO",
                        f"Включены агрессивные настройки для стратегии: {strategy_name}",
                    )
                else:
                    strategy_settings["aggression_mode"] = "BALANCED"

    def get_strategy_settings(self, strategy_name: str) -> dict[str, Any]:
        """Получает настройки стратегии с учетом текущего уровня агрессивности"""
        strategy_config = self.config.get("strategy_config", {})

        if strategy_name in strategy_config:
            settings = strategy_config[strategy_name].copy()

            # Применяем агрессивные настройки если нужно
            if (
                self.current_level == AggressionLevel.AGGRESSIVE
                and "aggressive_settings" in settings
            ):
                aggressive_settings = settings["aggressive_settings"]
                for key, value in aggressive_settings.items():
                    if key != "enabled":
                        settings[key] = value
                settings["aggression_mode"] = "AGGRESSIVE"
            else:
                settings["aggression_mode"] = "BALANCED"

            return settings

        return {}

    def enable_auto_switch(self, enabled: bool = True):
        """Включает/выключает автоматическое переключение агрессивности"""
        self.auto_switch_enabled = enabled
        self.logger.log_event(
            "AGGRESSION_MANAGER",
            "INFO",
            f"Автоматическое переключение агрессивности: {'ВКЛЮЧЕНО' if enabled else 'ВЫКЛЮЧЕНО'}",
        )

    def analyze_market_conditions(self, market_data: dict[str, Any]) -> dict[str, Any]:
        """Анализирует рыночные условия для автоматического переключения"""
        import time

        analysis = {
            "volatility": 0.0,
            "trend_strength": 0.0,
            "volume_spike": 0.0,
            "market_sentiment": 0.0,
            "recommended_level": self.current_level.value,
            "should_switch": False,
            "reason": "",
        }

        try:
            # Анализ волатильности
            if "atr" in market_data:
                atr_percent = market_data["atr"] / market_data.get("price", 1) * 100
                analysis["volatility"] = atr_percent

                if atr_percent > self.market_conditions["volatility_threshold"]:
                    analysis["recommended_level"] = "AGGRESSIVE"
                    analysis["reason"] += f"Высокая волатильность: {atr_percent:.2f}% "

            # Анализ силы тренда
            if "rsi" in market_data:
                rsi = market_data["rsi"]
                trend_strength = abs(50 - rsi) / 50  # 0-1 шкала
                analysis["trend_strength"] = trend_strength

                if trend_strength > self.market_conditions["trend_strength_threshold"]:
                    if rsi < 30:  # Сильный нисходящий тренд
                        analysis["recommended_level"] = "CONSERVATIVE"
                        analysis["reason"] += f"Сильный нисходящий тренд (RSI: {rsi:.1f}) "
                    elif rsi > 70:  # Сильный восходящий тренд
                        analysis["recommended_level"] = "AGGRESSIVE"
                        analysis["reason"] += f"Сильный восходящий тренд (RSI: {rsi:.1f}) "

            # Анализ объема
            if "volume_ratio" in market_data:
                volume_ratio = market_data["volume_ratio"]
                analysis["volume_spike"] = volume_ratio

                if volume_ratio > self.market_conditions["volume_spike_threshold"]:
                    analysis["recommended_level"] = "AGGRESSIVE"
                    analysis["reason"] += f"Спайк объема: {volume_ratio:.2f}x "

            # Анализ настроений рынка (если доступно)
            if "sentiment" in market_data:
                sentiment = market_data["sentiment"]
                analysis["market_sentiment"] = sentiment

                if sentiment > self.market_conditions["market_sentiment_threshold"]:
                    analysis["recommended_level"] = "AGGRESSIVE"
                    analysis["reason"] += f"Позитивные настроения: {sentiment:.2f} "
                elif sentiment < 0.3:
                    analysis["recommended_level"] = "CONSERVATIVE"
                    analysis["reason"] += f"Негативные настроения: {sentiment:.2f} "

            # Проверяем, нужно ли переключаться
            current_time = time.time()
            if (
                self.auto_switch_enabled
                and analysis["recommended_level"] != self.current_level.value
                and current_time - self.last_switch_time > self.min_switch_interval
            ):
                analysis["should_switch"] = True
                analysis["reason"] = analysis["reason"].strip()

        except Exception as e:
            self.logger.log_event(
                "AGGRESSION_MANAGER", "ERROR", f"Ошибка анализа рыночных условий: {e}"
            )

        return analysis

    def auto_switch_aggression(self, market_data: dict[str, Any]) -> bool:
        """Автоматически переключает агрессивность на основе рыночных условий"""
        if not self.auto_switch_enabled:
            return False

        analysis = self.analyze_market_conditions(market_data)

        if analysis["should_switch"]:
            success = self.set_aggression_level(analysis["recommended_level"])
            if success:
                self.last_switch_time = time.time()
                self.logger.log_event(
                    "AGGRESSION_MANAGER",
                    "INFO",
                    f"Автоматическое переключение на {analysis['recommended_level']}: {analysis['reason']}",
                )
                return True

        return False

    def get_auto_switch_status(self) -> dict[str, Any]:
        """Получает статус автоматического переключения"""
        return {
            "enabled": self.auto_switch_enabled,
            "current_level": self.current_level.value,
            "market_conditions": self.market_conditions,
            "last_switch_time": self.last_switch_time,
            "min_switch_interval": self.min_switch_interval,
        }

    def get_aggression_summary(self) -> dict[str, Any]:
        """Получает сводку по агрессивности"""
        return {
            "current_level": self.current_level.value,
            "available_levels": self.get_available_levels(),
            "profile_info": self.get_profile_info(),
            "strategy_modes": {
                name: settings.get("aggression_mode", "BALANCED")
                for name, settings in self.config.get("strategy_config", {}).items()
            },
        }

    def validate_aggression_settings(self) -> list[str]:
        """Валидирует настройки агрессивности"""
        errors = []

        # Проверяем, что все профили существуют
        for level in AggressionLevel:
            if level.value not in self.aggression_profiles:
                errors.append(f"Отсутствует профиль для уровня: {level.value}")

        # Проверяем настройки стратегий
        strategy_config = self.config.get("strategy_config", {})
        for strategy_name, settings in strategy_config.items():
            if "aggressive_settings" in settings:
                aggressive = settings["aggressive_settings"]
                if aggressive.get("enabled", False):
                    # Проверяем, что все необходимые параметры есть
                    required_params = ["rsi_oversold", "rsi_overbought", "volume_threshold"]
                    for param in required_params:
                        if param not in aggressive:
                            errors.append(
                                f"Отсутствует параметр {param} в агрессивных настройках {strategy_name}"
                            )

        return errors

    def switch_to_conservative(self) -> bool:
        """Переключает на консервативный режим"""
        return self.set_aggression_level("CONSERVATIVE")

    def switch_to_balanced(self) -> bool:
        """Переключает на сбалансированный режим"""
        return self.set_aggression_level("BALANCED")

    def switch_to_aggressive(self) -> bool:
        """Переключает на агрессивный режим"""
        return self.set_aggression_level("AGGRESSIVE")

    def is_aggressive_mode(self) -> bool:
        """Проверяет, включен ли агрессивный режим"""
        return self.current_level == AggressionLevel.AGGRESSIVE

    def get_risk_multiplier(self) -> float:
        """Получает множитель риска для текущего уровня агрессивности"""
        multipliers = {
            AggressionLevel.CONSERVATIVE: 0.3,
            AggressionLevel.BALANCED: 1.0,
            AggressionLevel.AGGRESSIVE: 1.5,
        }
        return multipliers.get(self.current_level, 1.0)
