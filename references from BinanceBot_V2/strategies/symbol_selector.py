# strategies/symbol_selector.py

import asyncio
import time
from collections import defaultdict
from typing import Any

import numpy as np


class SymbolSelector:
    """
    🚀 Продвинутый умный селектор символов с машинным обучением и адаптивными алгоритмами
    """

    def __init__(self, config, symbol_manager, exchange_client, logger):
        self.config = config
        self.symbol_manager = symbol_manager
        self.exchange = exchange_client
        self.logger = logger

        self.selected_symbols: list[str] = []
        self.symbol_stats: dict[str, dict[str, Any]] = {}

        # 🚀 ОПТИМИЗАЦИЯ: Кэширование для ускорения
        self._stats_cache = {}
        self._cache_time = {}
        self._cache_duration = 30  # 30 секунд кэш

        self.rotation_interval = config.symbol_rotation_minutes * 60  # в секундах
        self.max_symbols = config.max_symbols_to_trade

        # 🚀 ОПТИМИЗАЦИЯ: Адаптивные веса на основе производительности
        self.adaptive_weights = {
            "volume": 30,
            "volatility": 25,
            "trend": 20,
            "win_rate": 15,
            "avg_pnl": 10
        }

        # 🚀 ОПТИМИЗАЦИЯ: Исторические данные для ML
        self.symbol_performance_history = defaultdict(list)
        self.market_regime = "normal"  # normal, volatile, trending

        # 🚀 ОПТИМИЗАЦИЯ: Анализ трендов
        self.trend_analysis = {}
        self.volatility_regime = {}

    async def symbol_rotation_loop(self):
        """Основной цикл ротации символов с адаптивными алгоритмами"""
        while True:
            try:
                await self.update_selected_symbols()
                await self.update_market_regime()
                await self.optimize_weights()
                await asyncio.sleep(self.rotation_interval)
            except Exception as e:
                self.logger.log_event("SYMBOL_SELECTOR", "ERROR", f"Symbol rotation error: {e}")
                await asyncio.sleep(60)  # Пауза при ошибке

    async def update_selected_symbols(self):
        """Обновляет выбранные символы с продвинутыми алгоритмами"""
        
        # 🚀 АДАПТАЦИЯ: Принудительно обновляем символы из менеджера
        try:
            await self.symbol_manager.update_available_symbols()
        except Exception as e:
            self.logger.log_event("SYMBOL_SELECTOR", "ERROR", f"Failed to update symbols: {e}")
        
        available_symbols = list(self.symbol_manager.active_symbols)
        
        # 🚀 ДЕБАГ: Добавляем отладочную информацию
        self.logger.log_event("SYMBOL_SELECTOR", "DEBUG", f"Available symbols from manager: {len(available_symbols)}")
        if available_symbols:
            self.logger.log_event("SYMBOL_SELECTOR", "DEBUG", f"First 5 symbols: {available_symbols[:5]}")
            
        # 🚀 ДЕБАГ: Проверяем фильтры
        self.logger.log_event("SYMBOL_SELECTOR", "DEBUG", f"Config filters: min_volume={self.config.min_volume_24h_usdc}, min_atr={self.config.min_atr_percent}")

        # 🚀 АДАПТАЦИЯ: Добавляем fallback логику из старого бота
        if not available_symbols:
            self.logger.log_event("SYMBOL_SELECTOR", "WARNING", "No available symbols, using fallback")
            # Fallback к базовым символам
            self.selected_symbols = ["BTC/USDC:USDC", "ETH/USDC:USDC", "BNB/USDC:USDC"]
            return

        # 🚀 ОПТИМИЗАЦИЯ: Параллельная обработка символов
        tasks = []
        for symbol in available_symbols:
            if symbol in self.config.blacklisted_symbols:
                continue
            tasks.append(self.analyze_symbol(symbol))

        # Выполняем анализ параллельно
        symbol_analyses = await asyncio.gather(*tasks, return_exceptions=True)

        ranked_symbols = []
        for i, symbol in enumerate(available_symbols):
            if symbol in self.config.blacklisted_symbols:
                continue

            analysis = symbol_analyses[i]
            if isinstance(analysis, Exception):
                self.logger.log_event("SYMBOL_SELECTOR", "WARNING", f"Failed to analyze {symbol}: {analysis}")
                continue

            # 🚀 АДАПТАЦИЯ: Более мягкие фильтры
            if analysis:
                score = analysis.get("score", 0)
                # Принимаем символы даже с низким скором, но с базовыми требованиями
                if score > 0 or (analysis.get("volume", 0) > 100000 and analysis.get("atr_percent", 0) > 0.1):
                    ranked_symbols.append((symbol, score, analysis))

        # 🚀 ОПТИМИЗАЦИЯ: Сортировка с учетом рыночного режима
        ranked_symbols.sort(key=lambda x: x[1], reverse=True)

        # Адаптивный выбор количества символов
        optimal_count = self.calculate_optimal_symbol_count()
        
        # 🚀 АДАПТАЦИЯ: Fallback если нет подходящих символов
        if not ranked_symbols:
            self.logger.log_event("SYMBOL_SELECTOR", "WARNING", "No symbols passed filters, using fallback")
            self.selected_symbols = ["BTC/USDC:USDC", "ETH/USDC:USDC", "BNB/USDC:USDC"]
        else:
            self.selected_symbols = [s[0] for s in ranked_symbols[:optimal_count]]

        self.logger.log_event(
            "SYMBOL_SELECTOR",
            "INFO",
            f"🚀 Advanced symbol rotation complete. Selected {len(self.selected_symbols)} symbols: {self.selected_symbols}",
        )

    async def analyze_symbol(self, symbol: str) -> dict[str, Any] | None:
        """Продвинутый анализ символа с ML-компонентами"""
        try:
            # 🚀 ОПТИМИЗАЦИЯ: Кэширование анализа
            current_time = time.time()
            if (symbol in self._stats_cache and
                current_time - self._cache_time.get(symbol, 0) < self._cache_duration):
                return self._stats_cache[symbol]

            # Получаем базовую статистику
            stats = await self.fetch_symbol_stats(symbol)
            if not stats:
                return None

            # 🚀 ОПТИМИЗАЦИЯ: Анализ трендов
            trend_analysis = await self.analyze_trend(symbol)

            # 🚀 ОПТИМИЗАЦИЯ: Анализ волатильности
            volatility_analysis = await self.analyze_volatility(symbol)

            # 🚀 ОПТИМИЗАЦИЯ: ML-предсказание производительности
            ml_score = await self.predict_performance(symbol, stats)

            # Комплексный анализ
            analysis = {
                **stats,
                "trend_strength": trend_analysis.get("strength", 0),
                "trend_direction": trend_analysis.get("direction", 0),
                "volatility_regime": volatility_analysis.get("regime", "normal"),
                "ml_score": ml_score,
                "market_fit": self.calculate_market_fit(stats, trend_analysis, volatility_analysis)
            }

            # Вычисляем финальный скор
            analysis["score"] = self.calculate_advanced_symbol_score(analysis)

            # Кэшируем результат
            self._stats_cache[symbol] = analysis
            self._cache_time[symbol] = current_time

            return analysis

        except Exception as e:
            self.logger.log_event("SYMBOL_SELECTOR", "ERROR", f"Analysis failed for {symbol}: {e}")
            return None

    async def fetch_symbol_stats(self, symbol: str) -> dict[str, Any] | None:
        """Получает статистику символа с оптимизированным API"""
        try:
            # Используем оптимизированный метод из ExchangeClient
            ticker = await self.exchange.get_ticker(symbol)
            if not ticker:
                self.logger.log_event("SYMBOL_SELECTOR", "DEBUG", f"Symbol {symbol}: No ticker data")
                return None

            # Получаем исторические данные для анализа
            ohlcv = await self.exchange.get_ohlcv(symbol, "15m", 100)

            # Вычисляем дополнительные метрики
            volume_ma = self.calculate_volume_ma(ohlcv) if ohlcv else ticker.get("volume", 0)
            price_volatility = self.calculate_price_volatility(ohlcv) if ohlcv else 0

            # Получаем производительность из логгера
            performance = self.logger.get_symbol_performance(symbol, days=7) if hasattr(self.logger, 'get_symbol_performance') else None

            return {
                "volume": ticker.get("volume", 0),
                "quote_volume": ticker.get("quoteVolume", 0),
                "last_price": ticker.get("last", 0),
                "bid": ticker.get("bid", 0),
                "ask": ticker.get("ask", 0),
                "volume_ma": volume_ma,
                "price_volatility": price_volatility,
                "win_rate": performance.get("win_rate", 0.5) if performance else 0.5,
                "avg_pnl": performance.get("avg_pnl", 0.0) if performance else 0.0,
                "atr_percent": await self.symbol_manager.get_atr_percent(symbol),
                "ohlcv_data": ohlcv
            }

        except Exception as e:
            self.logger.log_event("SYMBOL_SELECTOR", "ERROR", f"Failed to fetch stats for {symbol}: {e}")
            return None

    async def analyze_trend(self, symbol: str) -> dict[str, Any]:
        """Анализ трендов с использованием технических индикаторов"""
        try:
            ohlcv = await self.exchange.get_ohlcv(symbol, "15m", 100)
            if not ohlcv or len(ohlcv) < 20:
                return {"strength": 0, "direction": 0}

            closes = [candle["close"] for candle in ohlcv]

            # 🚀 ОПТИМИЗАЦИЯ: Множественные индикаторы тренда
            sma_20 = np.mean(closes[-20:])
            sma_50 = np.mean(closes[-50:]) if len(closes) >= 50 else sma_20

            # RSI
            rsi = self.calculate_rsi(closes)

            # MACD
            macd = self.calculate_macd(closes)

            # Определяем силу и направление тренда
            trend_strength = abs(sma_20 - sma_50) / sma_50
            trend_direction = 1 if sma_20 > sma_50 else -1

            # Корректируем на основе RSI и MACD
            if rsi > 70:
                trend_direction *= 0.5  # Перекупленность
            elif rsi < 30:
                trend_direction *= 1.5  # Перепроданность

            return {
                "strength": min(trend_strength * 100, 100),
                "direction": trend_direction,
                "rsi": rsi,
                "macd": macd
            }

        except Exception as e:
            self.logger.log_event("SYMBOL_SELECTOR", "ERROR", f"Trend analysis failed for {symbol}: {e}")
            return {"strength": 0, "direction": 0}

    async def analyze_volatility(self, symbol: str) -> dict[str, Any]:
        """Анализ волатильности для определения торговых возможностей"""
        try:
            ohlcv = await self.exchange.get_ohlcv(symbol, "15m", 100)
            if not ohlcv or len(ohlcv) < 20:
                return {"regime": "normal", "value": 0}

            # Вычисляем ATR
            atr_values = []
            for i in range(1, len(ohlcv)):
                high = ohlcv[i]["high"]
                low = ohlcv[i]["low"]
                prev_close = ohlcv[i-1]["close"]

                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                atr_values.append(tr)

            atr = np.mean(atr_values[-14:])  # 14-периодный ATR
            atr_percent = (atr / ohlcv[-1]["close"]) * 100

            # Определяем режим волатильности
            if atr_percent > 3.0:
                regime = "high"
            elif atr_percent < 1.0:
                regime = "low"
            else:
                regime = "normal"

            return {
                "regime": regime,
                "value": atr_percent,
                "atr": atr
            }

        except Exception as e:
            self.logger.log_event("SYMBOL_SELECTOR", "ERROR", f"Volatility analysis failed for {symbol}: {e}")
            return {"regime": "normal", "value": 0}

    async def predict_performance(self, symbol: str, stats: dict[str, Any]) -> float:
        """ML-предсказание производительности символа"""
        try:
            # 🚀 ОПТИМИЗАЦИЯ: Простая ML-модель на основе исторических данных
            historical_performance = self.symbol_performance_history.get(symbol, [])

            if len(historical_performance) < 5:
                return 0.5  # Нейтральный скор для новых символов

            # Вычисляем тренд производительности
            recent_performance = np.mean(historical_performance[-5:])
            long_term_performance = np.mean(historical_performance)

            # Предсказание на основе тренда
            performance_trend = recent_performance - long_term_performance
            predicted_score = 0.5 + (performance_trend * 0.3)  # Ограничиваем влияние

            return max(0.0, min(1.0, predicted_score))

        except Exception as e:
            self.logger.log_event("SYMBOL_SELECTOR", "ERROR", f"Performance prediction failed for {symbol}: {e}")
            return 0.5

    def calculate_advanced_symbol_score(self, analysis: dict[str, Any]) -> float:
        """Продвинутый расчет скора символа с адаптивными весами"""
        try:
            # 🚀 АДАПТАЦИЯ: Более мягкие фильтры из старого бота
            volume = analysis.get("volume", 0)
            atr_percent = analysis.get("atr_percent", 0)
            
            # Базовые требования (адаптированы из старого бота)
            min_volume = 10000  # $10k - очень мягкий фильтр
            min_atr = 0.05  # 0.05% - очень мягкий фильтр
            
            # 🚀 ДЕБАГ: Проверяем фильтры
            if volume < min_volume:
                self.logger.log_event("SYMBOL_SELECTOR", "DEBUG", f"Symbol filtered: volume {volume} < {min_volume}")
                return 0.0
                
            if atr_percent < min_atr:
                self.logger.log_event("SYMBOL_SELECTOR", "DEBUG", f"Symbol filtered: atr {atr_percent} < {min_atr}")
                return 0.0
            
            # Базовые метрики с более мягкими требованиями
            volume_score = min(volume / min_volume, 2.0) * self.adaptive_weights["volume"]
            volatility_score = min(atr_percent / min_atr, 2.0) * self.adaptive_weights["volatility"]

            # Трендовые метрики
            trend_score = analysis.get("trend_strength", 0) * self.adaptive_weights["trend"]
            trend_direction = analysis.get("trend_direction", 0)

            # Производительность
            win_rate_score = analysis.get("win_rate", 0.5) * self.adaptive_weights["win_rate"]
            pnl_score = analysis.get("avg_pnl", 0.0) * self.adaptive_weights["avg_pnl"]

            # ML-скор
            ml_score = analysis.get("ml_score", 0.5) * 20

            # Рыночная пригодность
            market_fit = analysis.get("market_fit", 0.5) * 15

            # Корректировка на основе рыночного режима
            regime_multiplier = self.get_regime_multiplier()

            total_score = (
                volume_score +
                volatility_score +
                trend_score * trend_direction +
                win_rate_score +
                pnl_score +
                ml_score +
                market_fit
            ) * regime_multiplier

            return max(0.0, total_score)

        except Exception as e:
            self.logger.log_event("SYMBOL_SELECTOR", "ERROR", f"Score calculation failed: {e}")
            return 0.0

    def calculate_market_fit(self, stats: dict[str, Any], trend: dict[str, Any], volatility: dict[str, Any]) -> float:
        """Вычисляет соответствие символа текущему рыночному режиму"""
        try:
            fit_score = 0.5  # Базовый скор

            # Корректировка на основе волатильности
            if self.market_regime == "volatile" and volatility.get("regime") == "high":
                fit_score += 0.3
            elif self.market_regime == "normal" and volatility.get("regime") == "normal":
                fit_score += 0.2
            elif self.market_regime == "trending" and trend.get("strength", 0) > 50:
                fit_score += 0.3

            return min(1.0, fit_score)

        except Exception as e:
            self.logger.log_event("SYMBOL_SELECTOR", "ERROR", f"Market fit calculation failed: {e}")
            return 0.5

    async def update_market_regime(self):
        """Обновляет определение рыночного режима"""
        try:
            # Анализируем общую волатильность рынка
            total_volatility = 0
            symbol_count = 0

            # Convert set to list for indexing
            active_symbols_list = list(self.symbol_manager.active_symbols)
            for symbol in active_symbols_list[:20]:  # Топ-20 символов
                volatility = await self.analyze_volatility(symbol)
                if volatility.get("value", 0) > 0:
                    total_volatility += volatility["value"]
                    symbol_count += 1

            avg_volatility = total_volatility / symbol_count if symbol_count > 0 else 0

            # Определяем режим
            if avg_volatility > 2.5:
                self.market_regime = "volatile"
            elif avg_volatility < 1.0:
                self.market_regime = "low_volatility"
            else:
                self.market_regime = "normal"

            self.logger.log_event("SYMBOL_SELECTOR", "INFO", f"Market regime updated: {self.market_regime} (avg volatility: {avg_volatility:.2f}%)")

        except Exception as e:
            self.logger.log_event("SYMBOL_SELECTOR", "ERROR", f"Market regime update failed: {e}")

    async def optimize_weights(self):
        """Адаптивная оптимизация весов на основе производительности"""
        try:
            # Анализируем производительность последних символов
            recent_performance = []
            for symbol in self.selected_symbols[-5:]:
                performance = self.logger.get_symbol_performance(symbol, days=1) if hasattr(self.logger, 'get_symbol_performance') else None
                if performance:
                    recent_performance.append(performance.get("avg_pnl", 0))

            if recent_performance:
                avg_performance = np.mean(recent_performance)

                # Корректируем веса на основе производительности
                if avg_performance > 0.5:  # Хорошая производительность
                    self.adaptive_weights["win_rate"] = min(25, self.adaptive_weights["win_rate"] + 2)
                    self.adaptive_weights["avg_pnl"] = min(15, self.adaptive_weights["avg_pnl"] + 1)
                elif avg_performance < -0.5:  # Плохая производительность
                    self.adaptive_weights["volume"] = min(35, self.adaptive_weights["volume"] + 2)
                    self.adaptive_weights["volatility"] = min(30, self.adaptive_weights["volatility"] + 2)

                self.logger.log_event("SYMBOL_SELECTOR", "INFO", f"Weights optimized. Performance: {avg_performance:.2f}")

        except Exception as e:
            self.logger.log_event("SYMBOL_SELECTOR", "ERROR", f"Weight optimization failed: {e}")

    def calculate_optimal_symbol_count(self) -> int:
        """Вычисляет оптимальное количество символов на основе рыночных условий"""
        base_count = self.max_symbols

        # Корректировка на основе рыночного режима
        if self.market_regime == "volatile":
            return max(5, base_count - 3)  # Меньше символов в волатильном рынке
        elif self.market_regime == "low_volatility":
            return min(20, base_count + 2)  # Больше символов в спокойном рынке
        else:
            return base_count

    def get_regime_multiplier(self) -> float:
        """Возвращает множитель скора на основе рыночного режима"""
        multipliers = {
            "volatile": 0.8,      # Снижаем риск в волатильном рынке
            "low_volatility": 1.2, # Увеличиваем активность в спокойном рынке
            "normal": 1.0,
            "trending": 1.1
        }
        return multipliers.get(self.market_regime, 1.0)

    # Вспомогательные методы для технического анализа
    def calculate_rsi(self, prices: list[float], period: int = 14) -> float:
        """Вычисляет RSI"""
        try:
            if len(prices) < period + 1:
                return 50.0

            deltas = np.diff(prices)
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)

            avg_gain = np.mean(gains[-period:])
            avg_loss = np.mean(losses[-period:])

            if avg_loss == 0:
                return 100.0

            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

            return rsi
        except Exception:
            return 50.0

    def calculate_macd(self, prices: list[float]) -> float:
        """Вычисляет MACD"""
        try:
            if len(prices) < 26:
                return 0.0

            ema12 = np.mean(prices[-12:])
            ema26 = np.mean(prices[-26:])

            return ema12 - ema26
        except Exception:
            return 0.0

    def calculate_volume_ma(self, ohlcv: list[dict[str, Any]], period: int = 20) -> float:
        """Вычисляет скользящее среднее объема"""
        try:
            if not ohlcv or len(ohlcv) < period:
                return 0.0

            volumes = [candle["volume"] for candle in ohlcv[-period:]]
            return np.mean(volumes)
        except Exception:
            return 0.0

    def calculate_price_volatility(self, ohlcv: list[dict[str, Any]]) -> float:
        """Вычисляет волатильность цены"""
        try:
            if not ohlcv or len(ohlcv) < 20:
                return 0.0

            returns = []
            for i in range(1, len(ohlcv)):
                prev_close = ohlcv[i-1]["close"]
                curr_close = ohlcv[i]["close"]
                returns.append((curr_close - prev_close) / prev_close)

            return np.std(returns) * 100  # В процентах
        except Exception:
            return 0.0

    def get_selected_symbols(self) -> list[str]:
        return self.selected_symbols

    async def manual_refresh(self):
        await self.update_selected_symbols()
        return f"🔄 Advanced manual refresh complete. Selected symbols: {self.selected_symbols}"

    async def get_symbols_for_trading(self) -> list[str]:
        if not self.selected_symbols:
            await self.update_selected_symbols()
        return self.selected_symbols

    @staticmethod
    def integrate_into_main(symbol_selector, task_list):
        task_list.append(symbol_selector.symbol_rotation_loop())


__all__ = ["SymbolSelector"]
