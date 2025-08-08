#!/usr/bin/env python3
"""
Проверка реалистичности настроек для USDC Futures на Binance
"""

import ccxt
import asyncio
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

def check_binance_reality():
    """Проверяем реалистичность настроек на основе реальных данных Binance"""
    
    # Инициализируем подключение к Binance
    exchange = ccxt.binance({
        'apiKey': os.getenv('BINANCE_API_KEY'),
        'secret': os.getenv('BINANCE_API_SECRET'),
        'sandbox': False,
        'options': {
            'defaultType': 'future',
        }
    })
    
    print("🔍 Проверка реалистичности настроек для USDC Futures...")
    print("=" * 60)
    
    try:
        # Получаем информацию о рынках
        markets = exchange.load_markets()
        
        # Фильтруем только USDC-M фьючерсы
        usdc_futures = {symbol: market for symbol, market in markets.items() 
                       if market['quote'] == 'USDC' and market['future']}
        
        print(f"📊 Найдено USDC-M фьючерсов: {len(usdc_futures)}")
        
        # Анализируем объемы торгов
        volumes = []
        prices = []
        tick_sizes = []
        
        for symbol, market in usdc_futures.items():
            try:
                ticker = exchange.fetch_ticker(symbol)
                volumes.append(ticker['quoteVolume'])
                prices.append(ticker['last'])
                
                # Получаем информацию о лимитах
                if 'limits' in market and 'amount' in market['limits']:
                    min_amount = market['limits']['amount']['min']
                    tick_sizes.append(min_amount)
                    
            except Exception as e:
                print(f"⚠️ Ошибка получения данных для {symbol}: {e}")
        
        if volumes:
            avg_volume = sum(volumes) / len(volumes)
            max_volume = max(volumes)
            min_volume = min(volumes)
            
            print(f"\n📈 Анализ объемов (24h):")
            print(f"   • Средний объем: ${avg_volume:,.0f}")
            print(f"   • Максимальный объем: ${max_volume:,.0f}")
            print(f"   • Минимальный объем: ${min_volume:,.0f}")
            
            # Проверяем настройку min_volume_24h_usdc
            current_setting = 1000000.0  # 1M USDC
            volume_threshold = current_setting
            
            symbols_above_threshold = sum(1 for v in volumes if v >= volume_threshold)
            print(f"   • Символов с объемом > ${volume_threshold:,.0f}: {symbols_above_threshold}")
            
            if symbols_above_threshold < 5:
                print(f"   ⚠️ РЕКОМЕНДАЦИЯ: Снизить min_volume_24h_usdc до ${volume_threshold/2:,.0f}")
        
        if prices:
            avg_price = sum(prices) / len(prices)
            print(f"\n💰 Анализ цен:")
            print(f"   • Средняя цена: ${avg_price:.4f}")
            print(f"   • Диапазон цен: ${min(prices):.4f} - ${max(prices):.4f}")
        
        if tick_sizes:
            avg_tick = sum(tick_sizes) / len(tick_sizes)
            print(f"\n📏 Анализ минимальных размеров:")
            print(f"   • Средний min_amount: {avg_tick:.6f}")
            print(f"   • Диапазон: {min(tick_sizes):.6f} - {max(tick_sizes):.6f}")
        
        # Проверяем настройки позиций
        print(f"\n🎯 Анализ настроек позиций:")
        print(f"   • max_position_size_usdc: $50")
        print(f"   • min_position_size_usdc: $15")
        print(f"   • base_risk_pct: 15%")
        
        # Проверяем настройки Stop Loss
        print(f"\n🛑 Анализ Stop Loss:")
        print(f"   • sl_percent: 80% (слишком высоко!)")
        print(f"   • РЕКОМЕНДАЦИЯ: Снизить до 1-5%")
        
        # Проверяем настройки Take Profit
        print(f"\n📈 Анализ Take Profit:")
        print(f"   • step_tp_levels: [0.4%, 0.8%, 1.2%, 1.6%]")
        print(f"   • РЕКОМЕНДАЦИЯ: Увеличить до [1%, 2%, 3%, 4%]")
        
        # Проверяем настройки времени
        print(f"\n⏰ Анализ временных настроек:")
        print(f"   • max_hold_minutes: 15 минут")
        print(f"   • weak_position_minutes: 20 минут")
        print(f"   • РЕКОМЕНДАЦИЯ: Увеличить до 30-60 минут")
        
        print(f"\n" + "=" * 60)
        print("📋 ИТОГОВЫЕ РЕКОМЕНДАЦИИ:")
        print("1. Снизить sl_percent с 80% до 1-5%")
        print("2. Увеличить step_tp_levels до [1%, 2%, 3%, 4%]")
        print("3. Увеличить max_hold_minutes до 30-60 минут")
        print("4. Снизить min_volume_24h_usdc если символов мало")
        
    except Exception as e:
        print(f"❌ Ошибка при проверке: {e}")

if __name__ == "__main__":
    check_binance_reality() 