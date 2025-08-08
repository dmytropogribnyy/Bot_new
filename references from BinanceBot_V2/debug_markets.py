#!/usr/bin/env python3
"""
Отладка доступных рынков на Binance
"""

import ccxt
import os
from dotenv import load_dotenv

load_dotenv()

def debug_markets():
    """Отлаживаем доступные рынки на Binance"""

    exchange = ccxt.binance({
        'apiKey': os.getenv('BINANCE_API_KEY'),
        'secret': os.getenv('BINANCE_API_SECRET'),
        'sandbox': False,
        'options': {
            'defaultType': 'future',
        }
    })

    print("🔍 Отладка доступных рынков на Binance...")
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

        print(f"\n📋 USDC фьючерсы:")
        for symbol in list(usdc_futures.keys())[:20]:
            print(f"   • {symbol}")
        if len(usdc_futures) > 20:
            print(f"   ... и еще {len(usdc_futures) - 20} символов")

        print(f"\n📋 USDT фьючерсы (первые 10):")
        for symbol in list(usdt_futures.keys())[:10]:
            print(f"   • {symbol}")

        # Проверяем наши символы
        print(f"\n🔍 Проверяем наши символы:")
        with open('data/valid_usdc_symbols.json', 'r') as f:
            our_symbols = json.load(f)

        found_symbols = []
        not_found_symbols = []

        for symbol in our_symbols:
            if symbol in markets:
                found_symbols.append(symbol)
            else:
                not_found_symbols.append(symbol)

        print(f"✅ Найдено на бирже: {len(found_symbols)}")
        print(f"❌ Не найдено: {len(not_found_symbols)}")

        if found_symbols:
            print(f"\n✅ Найденные символы:")
            for symbol in found_symbols[:10]:
                print(f"   • {symbol}")
            if len(found_symbols) > 10:
                print(f"   ... и еще {len(found_symbols) - 10} символов")

        if not_found_symbols:
            print(f"\n❌ Ненайденные символы:")
            for symbol in not_found_symbols[:10]:
                print(f"   • {symbol}")
            if len(not_found_symbols) > 10:
                print(f"   ... и еще {len(not_found_symbols) - 10} символов")

    except Exception as e:
        print(f"❌ Ошибка при отладке: {e}")

if __name__ == "__main__":
    import json
    debug_markets()
