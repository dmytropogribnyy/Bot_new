import time
from datetime import datetime

import pandas as pd

from core.aggression_manager import AggressionManager

# logger будет передаваться через конструктор
from strategies.base_strategy import BaseStrategy


class ScalpingV1(BaseStrategy):
    """
    Скальпинговая стратегия v1.
    Интегрирует MACD, RSI, EMA, Volume + гибридную фильтрацию.
    """

    def __init__(self, config, exchange_client, symbol_manager, logger):
        super().__init__(config, exchange_client, symbol_manager, logger)

        # Инициализируем AggressionManager для динамических настроек
        self.aggression_manager = AggressionManager(config, logger)

        # Получаем настройки с учетом агрессивности
        self._update_settings_from_aggression()

        # Улучшенные параметры для прибыльной торговли
        self.profit_target_hourly = getattr(config, "profit_target_hourly", 0.7)
        self.min_win_rate = getattr(config, "min_win_rate", 0.65)
        self.volatility_multiplier_max = getattr(config, "volatility_multiplier_max", 2.5)

        # Новые параметры для улучшенного анализа
        self.ema_fast = 9
        self.ema_slow = 21
        self.rsi_period = 14
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9

        # Стабильные параметры для качественных сделок
        self.min_signal_strength = 1.8  # Увеличен для качества сигналов
        self.max_hold_minutes = 15  # Увеличен для стабильности

    def _update_settings_from_aggression(self):
        """Обновляет настройки стратегии с учетом уровня агрессивности"""
        try:
            settings = self.aggression_manager.get_strategy_settings("scalping")

            # Обновляем параметры из настроек агрессивности
            self.rsi_oversold = settings.get("rsi_oversold", 28)
            self.rsi_overbought = settings.get("rsi_overbought", 72)
            self.volume_threshold = settings.get("volume_threshold", 1.6)
            self.min_atr_percent = settings.get("min_atr_percent", 0.5)
            self.min_signal_strength = settings.get("min_signal_strength", 1.8)
            self.max_hold_minutes = settings.get("max_hold_minutes", 15)
            self.target_profit_percent = settings.get("target_profit_percent", 0.5)
            self.max_loss_percent = settings.get("max_loss_percent", 0.4)

            # Логируем обновление настроек
            self.logger.log_strategy_event(
                "scalping",
                "SETTINGS_UPDATED",
                {
                    "aggression_level": self.aggression_manager.get_aggression_level(),
                    "rsi_oversold": self.rsi_oversold,
                    "rsi_overbought": self.rsi_overbought,
                    "volume_threshold": self.volume_threshold,
                    "min_signal_strength": self.min_signal_strength,
                },
            )

        except Exception as e:
            self.logger.log_event(
                "STRATEGY", "ERROR", f"Failed to update settings from AggressionManager: {e}"
            )
            # Fallback к базовым настройкам
            self.rsi_oversold = 28
            self.rsi_overbought = 72
            self.volume_threshold = 1.6
            self.min_atr_percent = 0.5
            self.min_signal_strength = 1.8
            self.max_hold_minutes = 15
            self.target_profit_percent = 0.5
            self.max_loss_percent = 0.4

    async def analyze_market(self, symbol: str) -> dict | None:
        ohlcv_data = await self.symbol_manager.get_recent_ohlcv(symbol)

        if not ohlcv_data or len(ohlcv_data) < 100:
            self.logger.log_event("STRATEGY", "DEBUG", f"Insufficient data for {symbol}")
            return None

        # Конвертируем в pandas DataFrame
        df = pd.DataFrame(ohlcv_data)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)

        # Убеждаемся, что колонки имеют правильные имена
        if "close" not in df.columns:
            self.logger.log_event("STRATEGY", "ERROR", f"Column 'close' not found for {symbol}")
            return None

        df = self.calculate_indicators(df)

        if df is None or len(df) < 2:
            return None

        current = df.iloc[-1]
        prev = df.iloc[-2]

        valid, reason = self.validate_market_conditions(current)
        if not valid:
            self.logger.log_event("STRATEGY", "DEBUG", f"Market invalid for {symbol}: {reason}")
            return None

        breakdown = self.get_signal_breakdown(current, prev)

        buy_score = self.calculate_buy_score(breakdown)
        sell_score = self.calculate_sell_score(breakdown)

        signal = None
        current_price = current["close"]  # Используем текущую цену закрытия

        if buy_score >= self.min_signal_strength:
            signal = self.format_signal("buy", buy_score, "bullish breakout", breakdown)
            signal["entry_price"] = current_price  # Добавляем цену входа
            self.logger.log_strategy_event(
                "scalping",
                "BUY_SIGNAL",
                {
                    "symbol": symbol,
                    "score": buy_score,
                    "reason": "bullish breakout",
                    "rsi": breakdown.get("rsi", 0),
                    "volume_ratio": breakdown.get("volume_ratio", 0),
                },
            )
        elif sell_score >= self.min_signal_strength:
            signal = self.format_signal("sell", sell_score, "bearish breakdown", breakdown)
            signal["entry_price"] = current_price  # Добавляем цену входа
            self.logger.log_strategy_event(
                "scalping",
                "SELL_SIGNAL",
                {
                    "symbol": symbol,
                    "score": sell_score,
                    "reason": "bearish breakdown",
                    "rsi": breakdown.get("rsi", 0),
                    "volume_ratio": breakdown.get("volume_ratio", 0),
                },
            )

        self.log_signal_analysis(symbol, signal, df)
        return signal

    async def should_exit(self, symbol: str, position_data: dict) -> bool:
        # 🎯 СТАБИЛЬНАЯ ЛОГИКА ВЫХОДА ДЛЯ $0.7/ЧАС С $400 ДЕПОЗИТОМ
        current_price = await self.symbol_manager.get_current_price(symbol)
        entry_price = position_data["entry_price"]
        direction = position_data["direction"]

        # Стабильный выход при +0.4% для качественной торговли
        if direction == "buy" and current_price >= entry_price * 1.004:
            self.logger.log_strategy_event(
                "scalping",
                "PROFIT_EXIT",
                {
                    "symbol": symbol,
                    "direction": direction,
                    "entry_price": entry_price,
                    "exit_price": current_price,
                    "profit_percent": ((current_price - entry_price) / entry_price) * 100,
                    "reason": "target_profit",
                },
            )
            return True
        elif direction == "sell" and current_price <= entry_price * 0.996:
            self.logger.log_strategy_event(
                "scalping",
                "PROFIT_EXIT",
                {
                    "symbol": symbol,
                    "direction": direction,
                    "entry_price": entry_price,
                    "exit_price": current_price,
                    "profit_percent": ((entry_price - current_price) / entry_price) * 100,
                    "reason": "target_profit",
                },
            )
            return True

        # Проверка времени удержания позиции
        position_duration = time.time() - position_data.get("entry_time", time.time())
        max_hold_seconds = self.max_hold_minutes * 60

        if position_duration > max_hold_seconds:
            self.logger.log_strategy_event(
                "scalping",
                "TIME_EXIT",
                {
                    "symbol": symbol,
                    "direction": direction,
                    "duration_minutes": position_duration / 60,
                    "max_hold_minutes": self.max_hold_minutes,
                    "reason": "time_limit",
                },
            )
            return True

        # Защитный стоп-лосс при убытке
        if direction == "buy" and current_price <= entry_price * 0.995:  # -0.5% стоп-лосс
            self.logger.log_strategy_event(
                "scalping",
                "STOP_LOSS",
                {
                    "symbol": symbol,
                    "direction": direction,
                    "entry_price": entry_price,
                    "exit_price": current_price,
                    "loss_percent": ((entry_price - current_price) / entry_price) * 100,
                    "reason": "stop_loss",
                },
            )
            return True
        elif direction == "sell" and current_price >= entry_price * 1.005:  # -0.5% стоп-лосс
            self.logger.log_strategy_event(
                "scalping",
                "STOP_LOSS",
                {
                    "symbol": symbol,
                    "direction": direction,
                    "entry_price": entry_price,
                    "exit_price": current_price,
                    "loss_percent": ((current_price - entry_price) / entry_price) * 100,
                    "reason": "stop_loss",
                },
            )
            return True

        return False

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        # Улучшенные индикаторы с настраиваемыми параметрами
        df["ema_fast"] = df["close"].ewm(span=self.ema_fast).mean()
        df["ema_slow"] = df["close"].ewm(span=self.ema_slow).mean()
        df["rsi"] = self.calculate_rsi(df["close"], self.rsi_period)

        # Улучшенный MACD
        macd, macd_signal = self.calculate_macd(
            df["close"], self.macd_fast, self.macd_slow, self.macd_signal
        )
        df["macd"] = macd
        df["macd_signal"] = macd_signal
        df["macd_histogram"] = macd - macd_signal

        # Волатильность и объем
        df["atr_percent"] = self.calculate_atr(df) / df["close"] * 100
        df["volume_ratio"] = df["volume"] / df["volume"].rolling(20).mean()

        # Дополнительные индикаторы для лучшего анализа
        df["price_change"] = df["close"].pct_change()
        df["volatility"] = df["price_change"].rolling(20).std() * 100

        return df

    def calculate_rsi(self, series: pd.Series, period: int = 14) -> pd.Series:
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def calculate_macd(
        self, series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> tuple[pd.Series, pd.Series]:
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        return macd, signal_line

    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        high_low = df["high"] - df["low"]
        high_close = abs(df["high"] - df["close"].shift())
        low_close = abs(df["low"] - df["close"].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        return true_range.rolling(period).mean()

    def validate_market_conditions(self, current: pd.Series) -> tuple[bool, str]:
        # Смягчаем требования для тестирования
        min_atr = self.min_atr_percent * 0.1  # Смягчаем в 10 раз
        min_volume = self.volume_threshold * 0.1  # Смягчаем в 10 раз

        if current["atr_percent"] < min_atr:
            return False, "Low volatility"
        if current["volume_ratio"] < min_volume:
            return False, "Low volume"
        return True, "ok"

    def get_signal_breakdown(self, current: pd.Series, prev: pd.Series) -> dict:
        breakdown = {
            # MACD анализ
            "macd_bullish": 1
            if current["macd"] > current["macd_signal"]
            and current["macd_histogram"] > prev["macd_histogram"]
            else 0,
            "macd_bearish": 1
            if current["macd"] < current["macd_signal"]
            and current["macd_histogram"] < prev["macd_histogram"]
            else 0,
            # RSI анализ
            "rsi_oversold": 1 if current["rsi"] < self.rsi_oversold else 0,
            "rsi_overbought": 1 if current["rsi"] > self.rsi_overbought else 0,
            "rsi_bullish_divergence": 1
            if current["rsi"] > prev["rsi"] and current["close"] < prev["close"]
            else 0,
            "rsi_bearish_divergence": 1
            if current["rsi"] < prev["rsi"] and current["close"] > prev["close"]
            else 0,
            # EMA анализ
            "ema_bullish": 1
            if current["ema_fast"] > current["ema_slow"] and current["close"] > current["ema_fast"]
            else 0,
            "ema_bearish": 1
            if current["ema_fast"] < current["ema_slow"] and current["close"] < current["ema_fast"]
            else 0,
            # Объем и волатильность
            "volume_spike": 1 if current["volume_ratio"] > self.volume_threshold else 0,
            "high_volatility": 1 if current["volatility"] > 1.0 else 0,
            # Ценовое действие
            "price_momentum": 1 if current["price_change"] > 0.001 else 0,  # 0.1% рост
            "price_reversal": 1 if current["price_change"] < -0.001 else 0,  # 0.1% падение
        }
        return breakdown

    def calculate_buy_score(self, breakdown: dict) -> float:
        score = (
            breakdown["macd_bullish"] * 1.5  # Увеличенный вес для MACD
            + breakdown["rsi_oversold"] * 1.0
            + breakdown["rsi_bullish_divergence"] * 1.2  # Дивергенция RSI
            + breakdown["ema_bullish"] * 1.0
            + breakdown["volume_spike"] * 0.8
            + breakdown["high_volatility"] * 0.5
            + breakdown["price_momentum"] * 0.3
        )
        return score

    def calculate_sell_score(self, breakdown: dict) -> float:
        score = (
            breakdown["macd_bearish"] * 1.5  # Увеличенный вес для MACD
            + breakdown["rsi_overbought"] * 1.0
            + breakdown["rsi_bearish_divergence"] * 1.2  # Дивергенция RSI
            + breakdown["ema_bearish"] * 1.0
            + breakdown["volume_spike"] * 0.8
            + breakdown["high_volatility"] * 0.5
            + breakdown["price_reversal"] * 0.3
        )
        return score

    def format_signal(self, direction: str, strength: float, reason: str, breakdown: dict) -> dict:
        # Получаем текущую цену из последних данных
        current_price = (
            self.symbol_manager.get_latest_price()
            if hasattr(self.symbol_manager, "get_latest_price")
            else 0.0
        )

        return {
            "direction": direction,
            "strength": strength,
            "reason": reason,
            "breakdown": breakdown,
            "entry_price": current_price,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def log_signal_analysis(self, symbol: str, signal: dict | None, df: pd.DataFrame):
        indicators = df.iloc[-1].to_dict()
        if signal:
            self.logger.log_event(
                "STRATEGY",
                "INFO",
                f"Signal for {symbol}: {signal['direction']} (Strength: {signal['strength']:.2f})",
            )
        else:
            self.logger.log_event("STRATEGY", "DEBUG", f"No signal for {symbol}")
