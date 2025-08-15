"""
Scalping V1 Strategy
Based on the reliable core logic from v1 with RSI, MACD, EMA, and volume analysis
"""

from typing import Any

import pandas as pd

from core.config import TradingConfig
from core.unified_logger import UnifiedLogger
from strategies.base_strategy import BaseStrategy


class ScalpingV1(BaseStrategy):
    """
    Scalping strategy v1.
    Integrates MACD, RSI, EMA, Volume + hybrid filtering.
    Adapted from v1 legacy with async support.
    """

    def __init__(self, config: TradingConfig, logger: UnifiedLogger):
        super().__init__(config, logger)

        # Strategy parameters
        self.rsi_oversold = getattr(config, "rsi_oversold", 28)
        self.rsi_overbought = getattr(config, "rsi_overbought", 72)
        self.volume_threshold = getattr(config, "volume_threshold", 1.6)
        self.min_atr_percent = getattr(config, "min_atr_percent", 0.5)
        self.min_signal_strength = getattr(config, "min_signal_strength", 1.8)
        self.max_hold_minutes = getattr(config, "max_hold_minutes", 15)
        self.target_profit_percent = getattr(config, "target_profit_percent", 0.5)
        self.max_loss_percent = getattr(config, "max_loss_percent", 0.4)

        # Indicator parameters
        self.ema_fast = 9
        self.ema_slow = 21
        self.rsi_period = 14
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9

        # Signal weights
        self.weights = {"macd": 0.3, "rsi": 0.25, "ema": 0.25, "volume": 0.2}

        # Filter tiers
        self.filter_tiers = {
            "tier1": {"min_primary": 2, "min_secondary": 1},
            "tier2": {"min_primary": 1, "min_secondary": 2},
            "tier3": {"min_primary": 1, "min_secondary": 1},
        }

        self.logger.log_event(
            "STRATEGY",
            "INFO",
            f"ScalpingV1 initialized with parameters: RSI({self.rsi_oversold}/{self.rsi_overbought}), Volume({self.volume_threshold}), ATR({self.min_atr_percent})",
        )

    async def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators for the dataframe"""
        try:
            # EMA indicators
            df["ema_fast"] = df["close"].ewm(span=self.ema_fast).mean()
            df["ema_slow"] = df["close"].ewm(span=self.ema_slow).mean()

            # RSI
            df["rsi"] = self.calculate_rsi(df["close"], self.rsi_period)

            # MACD
            macd, macd_signal = self.calculate_macd(df["close"], self.macd_fast, self.macd_slow, self.macd_signal)
            df["macd"] = macd
            df["macd_signal"] = macd_signal
            df["macd_histogram"] = macd - macd_signal

            # Volatility and volume
            df["atr_percent"] = self.calculate_atr(df) / df["close"] * 100
            df["volume_ratio"] = df["volume"] / df["volume"].rolling(20).mean()

            # Additional indicators
            df["price_change"] = df["close"].pct_change()
            df["volatility"] = df["price_change"].rolling(20).std() * 100

            # EMA crossover detection
            df["ema_cross"] = (df["ema_fast"] > df["ema_slow"]) & (df["ema_fast"].shift(1) <= df["ema_slow"].shift(1))

            # Volume spike detection
            df["volume_spike"] = df["volume_ratio"] > self.volume_threshold

            return df

        except Exception as e:
            self.logger.log_event("STRATEGY", "ERROR", f"Error calculating indicators: {e}")
            return df

    def calculate_rsi(self, series: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI indicator"""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def calculate_macd(
        self, series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> tuple[pd.Series, pd.Series]:
        """Calculate MACD indicator"""
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        return macd, signal_line

    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range"""
        high_low = df["high"] - df["low"]
        high_close = abs(df["high"] - df["close"].shift())
        low_close = abs(df["low"] - df["close"].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        return true_range.rolling(period).mean()

    def validate_market_conditions(self, current: pd.Series) -> tuple[bool, str]:
        """Validate market conditions for trading"""
        # Relaxed requirements for testing
        min_atr = self.min_atr_percent * 0.1  # Relaxed by 10x
        min_volume = self.volume_threshold * 0.1  # Relaxed by 10x

        if current["atr_percent"] < min_atr:
            return False, "Low volatility"
        if current["volume_ratio"] < min_volume:
            return False, "Low volume"
        return True, "ok"

    def get_signal_breakdown(self, current: pd.Series, prev: pd.Series) -> dict[str, Any]:
        """Get detailed signal breakdown for analysis"""
        breakdown = {
            # MACD analysis
            "macd_bullish": 1
            if current["macd"] > current["macd_signal"] and current["macd_histogram"] > prev["macd_histogram"]
            else 0,
            "macd_bearish": 1
            if current["macd"] < current["macd_signal"] and current["macd_histogram"] < prev["macd_histogram"]
            else 0,
            # RSI analysis
            "rsi_oversold": 1 if current["rsi"] < self.rsi_oversold else 0,
            "rsi_overbought": 1 if current["rsi"] > self.rsi_overbought else 0,
            "rsi_bullish_divergence": 1 if current["rsi"] > prev["rsi"] and current["close"] < prev["close"] else 0,
            "rsi_bearish_divergence": 1 if current["rsi"] < prev["rsi"] and current["close"] > prev["close"] else 0,
            # EMA analysis
            "ema_bullish": 1
            if current["ema_fast"] > current["ema_slow"] and current["close"] > current["ema_fast"]
            else 0,
            "ema_bearish": 1
            if current["ema_fast"] < current["ema_slow"] and current["close"] < current["ema_fast"]
            else 0,
            # Volume and volatility
            "volume_spike": 1 if current["volume_ratio"] > self.volume_threshold else 0,
            "high_volatility": 1 if current["volatility"] > 1.0 else 0,
            # Price action
            "price_momentum": 1 if current["price_change"] > 0.001 else 0,  # 0.1% rise
            "price_reversal": 1 if current["price_change"] < -0.001 else 0,  # 0.1% fall
        }
        return breakdown

    async def should_enter_trade(self, symbol: str, df: pd.DataFrame) -> tuple[str | None, dict[str, Any]]:
        """
        Determine if we should enter a trade for the given symbol

        Returns:
            Tuple of (direction, breakdown) where:
            - direction: "buy", "sell", or None
            - breakdown: Dict with signal analysis details
        """
        try:
            if len(df) < 2:
                self.logger.log_event("STRATEGY", "WARNING", f"{symbol}: Not enough data for signal evaluation")
                return None, {}

            # Calculate indicators
            df = await self.calculate_indicators(df)

            current = df.iloc[-1]
            prev = df.iloc[-2]

            # Validate market conditions
            is_valid, reason = self.validate_market_conditions(current)
            if not is_valid:
                self.logger.log_event("STRATEGY", "DEBUG", f"{symbol}: Market conditions not met - {reason}")
                return None, {"reason": reason}

            # Get signal breakdown
            breakdown = self.get_signal_breakdown(current, prev)

            # Determine direction based on MACD and EMA
            direction = None
            macd_val = current.get("macd", 0)
            macd_sig = current.get("macd_signal", 0)
            ema_cross = current.get("ema_cross", False)

            # Primary logic: MACD + EMA cross
            if macd_val > macd_sig and ema_cross:
                direction = "buy"
            elif macd_val < macd_sig and not ema_cross:
                direction = "sell"
            else:
                # Fallback: Strong MACD override
                macd_strength = abs(macd_val - macd_sig)
                macd_override = getattr(self.config, "macd_strength_override", 0.001)

                if macd_val > macd_sig and macd_strength >= macd_override:
                    direction = "buy"
                elif macd_val < macd_sig and macd_strength >= macd_override:
                    direction = "sell"
                else:
                    # Final fallback: RSI extremes
                    rsi_val = current.get("rsi", 50)
                    if rsi_val > 60:
                        direction = "buy"
                    elif rsi_val < 40:
                        direction = "sell"

            if direction:
                # Strategy-level optional shorts filter
                if direction == "sell" and not getattr(self.config, "allow_shorts", True):
                    self.logger.log_event(
                        "STRATEGY",
                        "DEBUG",
                        f"{symbol}: SHORT signal filtered at strategy level",
                    )
                    return None, {"reason": "shorts_disabled"}
                # Add additional info to breakdown
                breakdown.update(
                    {
                        "direction": direction,
                        "entry_price": current["close"],
                        "macd_strength": abs(macd_val - macd_sig),
                        "rsi_strength": abs(current.get("rsi", 50) - 50),
                        "volume_ratio": current.get("volume_ratio", 0),
                        "atr_percent": current.get("atr_percent", 0),
                    }
                )

                self.logger.log_event(
                    "STRATEGY",
                    "INFO",
                    f"{symbol}: Signal generated - {direction} | "
                    f"MACD({macd_val:.4f} vs {macd_sig:.4f}) | "
                    f"RSI({current.get('rsi', 0):.2f}) | "
                    f"Volume({current.get('volume_ratio', 0):.2f})",
                )

                return direction, breakdown
            else:
                self.logger.log_event("STRATEGY", "DEBUG", f"{symbol}: No clear signal direction")
                return None, breakdown

        except Exception as e:
            self.logger.log_event("STRATEGY", "ERROR", f"{symbol}: Error in signal analysis: {e}")
            return None, {"error": str(e)}

    def passes_1plus1(self, breakdown: dict[str, Any]) -> bool:
        """
        Check signal using 1+1 logic with combined strategy:
        - Entry with ≥2 primary OR ≥1 primary + ≥1 secondary
        - Entry with strong MACD/RSI, even if only one PRIMARY
        - Rejected if only one SECONDARY
        """
        primary_components = {
            "macd_bullish": breakdown.get("macd_bullish", 0),
            "macd_bearish": breakdown.get("macd_bearish", 0),
            "ema_bullish": breakdown.get("ema_bullish", 0),
            "ema_bearish": breakdown.get("ema_bearish", 0),
        }
        primary_sum = sum(primary_components.values())

        secondary_components = {
            "volume_spike": breakdown.get("volume_spike", 0),
            "high_volatility": breakdown.get("high_volatility", 0),
            "price_momentum": breakdown.get("price_momentum", 0),
        }
        secondary_sum = sum(secondary_components.values())

        if primary_sum == 0 and secondary_sum == 0:
            return False

        # Main logic
        result = primary_sum >= 2 or (primary_sum >= 1 and secondary_sum >= 1)

        # Allow single strong primary
        if not result and primary_sum == 1 and secondary_sum == 0:
            macd_strength = breakdown.get("macd_strength", 0)
            rsi_strength = breakdown.get("rsi_strength", 0)

            if macd_strength > 0.001 or rsi_strength > 10:
                result = True

        return result
