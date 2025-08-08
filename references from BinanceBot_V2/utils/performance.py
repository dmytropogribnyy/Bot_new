#!/usr/bin/env python3
"""
Оптимизации производительности для BinanceBot v2
Использует Numba JIT для критических вычислений
"""


import numpy as np

try:
    from numba import jit, njit, prange

    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False

    # Заглушки для случаев, когда Numba недоступен
    def jit(*args, **kwargs):
        def decorator(func):
            return func

        return decorator

    def njit(*args, **kwargs):
        def decorator(func):
            return func

        return decorator

    prange = range


class PerformanceOptimizer:
    """Оптимизатор производительности для критических вычислений"""

    @staticmethod
    @jit(nopython=True, cache=True)
    def calculate_rsi_fast(prices: np.ndarray, period: int = 14) -> np.ndarray:
        """Быстрый расчет RSI с Numba JIT"""
        n = len(prices)
        rsi = np.zeros(n)

        for i in range(period, n):
            gains = np.maximum(prices[i - period + 1 : i + 1] - prices[i - period : i], 0)
            losses = np.maximum(prices[i - period : i] - prices[i - period + 1 : i + 1], 0)

            avg_gain = np.mean(gains)
            avg_loss = np.mean(losses)

            if avg_loss == 0:
                rsi[i] = 100
            else:
                rs = avg_gain / avg_loss
                rsi[i] = 100 - (100 / (1 + rs))

        return rsi

    @staticmethod
    @jit(nopython=True, cache=True)
    def calculate_macd_fast(
        prices: np.ndarray, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9
    ) -> tuple[np.ndarray, np.ndarray]:
        """Быстрый расчет MACD с Numba JIT"""
        n = len(prices)
        macd = np.zeros(n)
        signal = np.zeros(n)

        # EMA расчеты
        ema_fast = np.zeros(n)
        ema_slow = np.zeros(n)

        # Инициализация
        ema_fast[0] = prices[0]
        ema_slow[0] = prices[0]

        # Быстрая EMA
        alpha_fast = 2.0 / (fast_period + 1)
        for i in range(1, n):
            ema_fast[i] = alpha_fast * prices[i] + (1 - alpha_fast) * ema_fast[i - 1]

        # Медленная EMA
        alpha_slow = 2.0 / (slow_period + 1)
        for i in range(1, n):
            ema_slow[i] = alpha_slow * prices[i] + (1 - alpha_slow) * ema_slow[i - 1]

        # MACD line
        macd = ema_fast - ema_slow

        # Signal line (EMA of MACD)
        signal[0] = macd[0]
        alpha_signal = 2.0 / (signal_period + 1)
        for i in range(1, n):
            signal[i] = alpha_signal * macd[i] + (1 - alpha_signal) * signal[i - 1]

        return macd, signal

    @staticmethod
    @jit(nopython=True, cache=True)
    def calculate_atr_fast(
        high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14
    ) -> np.ndarray:
        """Быстрый расчет ATR с Numba JIT"""
        n = len(high)
        atr = np.zeros(n)

        # True Range
        tr = np.zeros(n)
        for i in range(1, n):
            hl = high[i] - low[i]
            hc = abs(high[i] - close[i - 1])
            lc = abs(low[i] - close[i - 1])
            tr[i] = max(hl, hc, lc)

        # ATR как EMA от True Range
        atr[0] = tr[0]
        alpha = 2.0 / (period + 1)
        for i in range(1, n):
            atr[i] = alpha * tr[i] + (1 - alpha) * atr[i - 1]

        return atr

    @staticmethod
    @jit(nopython=True, cache=True)
    def calculate_vwap_fast(
        prices: np.ndarray, volumes: np.ndarray, period: int = 20
    ) -> np.ndarray:
        """Быстрый расчет VWAP с Numba JIT"""
        n = len(prices)
        vwap = np.zeros(n)

        for i in range(period - 1, n):
            price_vol_sum = 0.0
            vol_sum = 0.0

            for j in range(i - period + 1, i + 1):
                price_vol_sum += prices[j] * volumes[j]
                vol_sum += volumes[j]

            if vol_sum > 0:
                vwap[i] = price_vol_sum / vol_sum

        return vwap

    @staticmethod
    @jit(nopython=True, cache=True)
    def calculate_bollinger_bands_fast(
        prices: np.ndarray, period: int = 20, std_dev: float = 2.0
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Быстрый расчет Bollinger Bands с Numba JIT"""
        n = len(prices)
        sma = np.zeros(n)
        upper_band = np.zeros(n)
        lower_band = np.zeros(n)

        for i in range(period - 1, n):
            # SMA
            sma[i] = np.mean(prices[i - period + 1 : i + 1])

            # Standard deviation
            variance = 0.0
            for j in range(i - period + 1, i + 1):
                variance += (prices[j] - sma[i]) ** 2
            std = np.sqrt(variance / period)

            # Bands
            upper_band[i] = sma[i] + (std_dev * std)
            lower_band[i] = sma[i] - (std_dev * std)

        return sma, upper_band, lower_band

    @staticmethod
    @jit(nopython=True, cache=True)
    def calculate_order_book_imbalance(
        bids: np.ndarray, asks: np.ndarray, levels: int = 5
    ) -> float:
        """Быстрый расчет Order Book Imbalance с Numba JIT"""
        if len(bids) == 0 or len(asks) == 0:
            return 0.0

        bid_volume = 0.0
        ask_volume = 0.0

        for i in range(min(levels, len(bids))):
            bid_volume += bids[i, 1]  # Volume

        for i in range(min(levels, len(asks))):
            ask_volume += asks[i, 1]  # Volume

        total_volume = bid_volume + ask_volume
        if total_volume == 0:
            return 0.0

        imbalance = (bid_volume - ask_volume) / total_volume
        return imbalance

    @staticmethod
    def optimize_memory_usage():
        """Оптимизация использования памяти"""
        import gc

        # Принудительная сборка мусора
        gc.collect()

        # Очистка кэша numpy
        if hasattr(np, "clear_cache"):
            np.clear_cache()

    @staticmethod
    def get_performance_stats() -> dict:
        """Получает статистику производительности"""
        import os

        import psutil

        process = psutil.Process(os.getpid())

        return {
            "cpu_percent": process.cpu_percent(),
            "memory_mb": process.memory_info().rss / 1024 / 1024,
            "memory_percent": process.memory_percent(),
            "num_threads": process.num_threads(),
            "num_fds": process.num_fds() if hasattr(process, "num_fds") else 0,
        }


class SignalOptimizer:
    """Оптимизатор сигналов для быстрого анализа"""

    @staticmethod
    @jit(nopython=True, cache=True)
    def calculate_signal_strength(indicators: np.ndarray, weights: np.ndarray) -> float:
        """Быстрый расчет силы сигнала"""
        if len(indicators) != len(weights):
            return 0.0

        signal = 0.0
        for i in range(len(indicators)):
            signal += indicators[i] * weights[i]

        return signal

    @staticmethod
    @jit(nopython=True, cache=True)
    def detect_breakout(
        prices: np.ndarray, resistance: np.ndarray, support: np.ndarray, threshold: float = 0.02
    ) -> int:
        """Быстрое обнаружение пробоя"""
        n = len(prices)
        if n < 2:
            return 0

        current_price = prices[-1]
        prev_price = prices[-2]

        # Пробой сопротивления
        if current_price > resistance[-1] * (1 + threshold):
            return 1  # Bullish breakout

        # Пробой поддержки
        if current_price < support[-1] * (1 - threshold):
            return -1  # Bearish breakout

        return 0  # No breakout

    @staticmethod
    @jit(nopython=True, cache=True)
    def calculate_volatility(prices: np.ndarray, period: int = 20) -> float:
        """Быстрый расчет волатильности"""
        if len(prices) < period:
            return 0.0

        returns = np.zeros(len(prices) - 1)
        for i in range(1, len(prices)):
            returns[i - 1] = (prices[i] - prices[i - 1]) / prices[i - 1]

        # Используем последние period значений
        recent_returns = returns[-period:] if len(returns) >= period else returns
        volatility = np.std(recent_returns) * np.sqrt(252)  # Annualized

        return volatility


# Проверка доступности Numba
if NUMBA_AVAILABLE:
    print("✅ Numba JIT optimization available")
else:
    print("⚠️ Numba not available, using fallback implementations")
