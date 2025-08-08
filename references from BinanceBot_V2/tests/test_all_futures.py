#!/usr/bin/env python3
"""
Проверка всех доступных фьючерсов на Binance
"""

import ccxt
import os
from dotenv import load_dotenv

load_dotenv()

def check_all_futures():
    """Проверяем все доступные фьючерсы"""
    
    exchange = ccxt.binance({
        'apiKey': os.getenv('BINANCE_API_KEY'),
        'secret': os.getenv('BINANCE_API_SECRET'),
        'sandbox': False,
        'options': {
            'defaultType': 'future',
        }
    })
    
    print("🔍 Проверка всех фьючерсов на Binance...")
    print("=" * 60)
    
    try:
        markets = exchange.load_markets()
        
        # Группируем по типам
        futures = {symbol: market for symbol, market in markets.items() if market['future']}
        usdt_futures = {symbol: market for symbol, market in futures.items() if market['quote'] == 'USDT'}
        usdc_futures = {symbol: market for symbol, market in futures.items() if market['quote'] == 'USDC'}
        btc_futures = {symbol: market for symbol, market in futures.items() if market['quote'] == 'BTC'}
        
        print(f"📊 Всего фьючерсов: {len(futures)}")
        print(f"📊 USDT фьючерсов: {len(usdt_futures)}")
        print(f"📊 USDC фьючерсов: {len(usdc_futures)}")
        print(f"📊 BTC фьючерсов: {len(btc_futures)}")
        
        if usdt_futures:
            print(f"\n📈 Примеры USDT фьючерсов:")
            for i, symbol in enumerate(list(usdt_futures.keys())[:10]):
                print(f"   • {symbol}")
        
        if usdc_futures:
            print(f"\n📈 Примеры USDC фьючерсов:")
            for symbol in usdc_futures.keys():
                print(f"   • {symbol}")
        
        # Проверяем объемы для USDT фьючерсов
        print(f"\n📊 Анализ объемов USDT фьючерсов:")
        volumes = []
        
        for symbol in list(usdt_futures.keys())[:20]:  # Первые 20
            try:
                ticker = exchange.fetch_ticker(symbol)
                volume = ticker['quoteVolume']
                volumes.append(volume)
                print(f"   • {symbol}: ${volume:,.0f}")
            except Exception as e:
                print(f"   • {symbol}: Ошибка получения данных")
        
        if volumes:
            avg_volume = sum(volumes) / len(volumes)
            print(f"\n📈 Средний объем USDT фьючерсов: ${avg_volume:,.0f}")
            
            # Рекомендации для настроек
            print(f"\n🎯 РЕКОМЕНДАЦИИ ДЛЯ НАСТРОЕК:")
            print(f"   • min_volume_24h_usdc: ${avg_volume/10:,.0f} (10% от среднего)")
            print(f"   • max_symbols_to_trade: 5-10")
            print(f"   • min_position_size_usdc: $20")
            print(f"   • max_position_size_usdc: $100")
        
    except Exception as e:
        print(f"❌ Ошибка при проверке: {e}")

if __name__ == "__main__":
    check_all_futures() 