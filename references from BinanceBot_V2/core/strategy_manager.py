#!/usr/bin/env python3
"""
Упрощенный Strategy Manager - основан на архитектуре старого бота
"""

import asyncio
import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional

from core.config import TradingConfig
from core.unified_logger import UnifiedLogger


class StrategyManager:
    """Упрощенный менеджер стратегий на основе старого бота"""
    
    def __init__(self, config: TradingConfig, logger: UnifiedLogger):
        self.config = config
        self.logger = logger
        self.last_analysis_time = {}
        
    async def initialize(self):
        """Инициализация стратегии"""
        self.logger.log_event("STRATEGY", "INFO", "🚀 Strategy Manager инициализирован")
        
    async def analyze_symbol(self, symbol: str, ohlcv_data: List[Dict]) -> Optional[Dict[str, Any]]:
        """Анализ символа и генерация торгового сигнала"""
        try:
            if not ohlcv_data or len(ohlcv_data) < 50:
                return None
                
            # Конвертируем в DataFrame
            df = pd.DataFrame(ohlcv_data)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # Проверяем минимальный объем
            avg_volume = df['volume'].mean()
            min_volume = getattr(self.config, 'min_volume_24h_usdc', 5000000.0) / 24  # Конвертируем дневной объем в часовой
            if avg_volume < min_volume:
                self.logger.log_event("STRATEGY", "DEBUG", f"Market invalid for {symbol}: Low volume")
                return None
                
            # Рассчитываем технические индикаторы
            signals = self._calculate_signals(df)
            
            # Принимаем решение о входе
            should_enter = self._should_enter_position(signals, symbol)
            
            if should_enter:
                # Определяем сторону входа
                side = self._determine_side(signals)
                
                # Рассчитываем количество
                quantity = self._calculate_position_size(symbol, df['close'].iloc[-1])
                
                return {
                    'should_enter': True,
                    'side': side,
                    'quantity': quantity,
                    'entry_price': df['close'].iloc[-1],
                    'signal_strength': signals.get('strength', 0),
                    'reason': 'scalping_signal'
                }
            
            return None
            
        except Exception as e:
            self.logger.log_event("STRATEGY", "ERROR", f"Ошибка анализа {symbol}: {e}")
            return None
    
    def _calculate_signals(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Рассчитывает технические индикаторы"""
        signals = {}
        
        try:
            # RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            signals['rsi'] = rsi.iloc[-1]
            
            # MACD
            exp1 = df['close'].ewm(span=12).mean()
            exp2 = df['close'].ewm(span=26).mean()
            macd = exp1 - exp2
            signal = macd.ewm(span=9).mean()
            signals['macd'] = macd.iloc[-1]
            signals['macd_signal'] = signal.iloc[-1]
            
            # Bollinger Bands
            bb_period = 20
            bb_std = 2
            bb_middle = df['close'].rolling(window=bb_period).mean()
            bb_std_dev = df['close'].rolling(window=bb_period).std()
            bb_upper = bb_middle + (bb_std_dev * bb_std)
            bb_lower = bb_middle - (bb_std_dev * bb_std)
            
            signals['bb_upper'] = bb_upper.iloc[-1]
            signals['bb_lower'] = bb_lower.iloc[-1]
            signals['bb_middle'] = bb_middle.iloc[-1]
            
            # Volume analysis
            signals['volume_ma'] = df['volume'].rolling(window=20).mean().iloc[-1]
            signals['current_volume'] = df['volume'].iloc[-1]
            
            # Price momentum
            signals['price_change'] = (df['close'].iloc[-1] - df['close'].iloc[-5]) / df['close'].iloc[-5]
            
            # Calculate signal strength
            strength = 0
            
            # RSI conditions
            if signals['rsi'] < 30:
                strength += 2  # Oversold
            elif signals['rsi'] > 70:
                strength -= 2  # Overbought
                
            # MACD conditions
            if signals['macd'] > signals['macd_signal']:
                strength += 1
            else:
                strength -= 1
                
            # Volume conditions
            if signals['current_volume'] > signals['volume_ma'] * 1.5:
                strength += 1
                
            # Price momentum
            if abs(signals['price_change']) > 0.01:  # 1% change
                strength += 1
                
            signals['strength'] = strength
            
        except Exception as e:
            self.logger.log_event("STRATEGY", "ERROR", f"Ошибка расчета сигналов: {e}")
            signals['strength'] = 0
            
        return signals
    
    def _should_enter_position(self, signals: Dict[str, Any], symbol: str) -> bool:
        """Определяет, следует ли входить в позицию"""
        try:
            # Проверяем минимальную силу сигнала
            min_strength = getattr(self.config, 'min_signal_strength', 1)  # Используем getattr с дефолтным значением
            if signals.get('strength', 0) < min_strength:
                return False
                
            # Проверяем RSI
            rsi = signals.get('rsi', 50)
            if rsi < 20 or rsi > 80:
                return False
                
            # Проверяем объем
            volume_ratio = signals.get('current_volume', 0) / max(signals.get('volume_ma', 1), 1)
            if volume_ratio < 1.2:
                return False
                
            # Проверяем время последнего анализа
            current_time = asyncio.get_event_loop().time()
            last_time = self.last_analysis_time.get(symbol, 0)
            if current_time - last_time < 60:  # Минимум 1 минута между анализами
                return False
                
            self.last_analysis_time[symbol] = current_time
            return True
            
        except Exception as e:
            self.logger.log_event("STRATEGY", "ERROR", f"Ошибка проверки входа: {e}")
            return False
    
    def _determine_side(self, signals: Dict[str, Any]) -> str:
        """Определяет сторону входа (BUY/SELL)"""
        try:
            strength = signals.get('strength', 0)
            rsi = signals.get('rsi', 50)
            
            # Простая логика на основе RSI и силы сигнала
            if strength > 0 and rsi < 50:
                return 'BUY'
            elif strength < 0 and rsi > 50:
                return 'SELL'
            else:
                return 'BUY'  # По умолчанию
                
        except Exception as e:
            self.logger.log_event("STRATEGY", "ERROR", f"Ошибка определения стороны: {e}")
            return 'BUY'
    
    def _calculate_position_size(self, symbol: str, current_price: float) -> float:
        """Рассчитывает размер позиции"""
        try:
            # Простой расчет на основе баланса и риска
            balance = 100  # Упрощенный баланс
            risk_percent = 0.02  # 2% риска на сделку
            risk_amount = balance * risk_percent
            
            # Учитываем кредитное плечо
            leverage = 5
            position_value = risk_amount * leverage
            
            # Рассчитываем количество
            quantity = position_value / current_price
            
            # Округляем до 6 знаков
            return round(quantity, 6)
            
        except Exception as e:
            self.logger.log_event("STRATEGY", "ERROR", f"Ошибка расчета размера позиции: {e}")
            return 0.001  # Минимальное 