#!/usr/bin/env python3
"""
Детальный анализ структуры markets
"""

import ccxt
import os
import json
from dotenv import load_dotenv

load_dotenv()

def debug_market_details():
    """Детально анализируем структуру markets"""

    exchange = ccxt.binance({
        'apiKey': os.getenv('BINANCE_API_KEY'),
        'secret': os.getenv('BINANCE_API_SECRET'),
        'sandbox': False,
        'options': {
            'defaultType': 'future',
        }
    })

    print("🔍 Детальный анализ структуры markets...")
    print("=" * 60)

    try:
        markets = exchange.load_markets()

        # Загружаем наши символы
        with open('data/valid_usdc_symbols.json', 'r') as f:
            our_symbols = json.load(f)

        print(f"📊 Всего рынков: {len(markets)}")
        print(f"📊 Наших символов: {len(our_symbols)}")

        # Анализируем первые несколько наших символов
        for symbol in our_symbols[:5]:
            if symbol in markets:
                market = markets[symbol]
                print(f"\n📋 Анализ {symbol}:")
                print(f"   • Тип: {market.get('type', 'N/A')}")
                print(f"   • Spot: {market.get('spot', 'N/A')}")
                print(f"   • Future: {market.get('future', 'N/A')}")
                print(f"   • Swap: {market.get('swap', 'N/A')}")
                print(f"   • Quote: {market.get('quote', 'N/A')}")
                print(f"   • Base: {market.get('base', 'N/A')}")
                print(f"   • Active: {market.get('active', 'N/A')}")
                print(f"   • Contract: {market.get('contract', 'N/A')}")
                print(f"   • ContractType: {market.get('contractType', 'N/A')}")
                print(f"   • Expiry: {market.get('expiry', 'N/A')}")
                print(f"   • Strike: {market.get('strike', 'N/A')}")
                print(f"   • SettleType: {market.get('settleType', 'N/A')}")
                print(f"   • Linear: {market.get('linear', 'N/A')}")
                print(f"   • Inverse: {market.get('inverse', 'N/A')}")
            else:
                print(f"\n❌ {symbol} не найден в markets")

        # Проверяем все символы с USDC
        usdc_symbols = [s for s in markets.keys() if 'USDC' in s]
        print(f"\n📊 Всего символов с USDC: {len(usdc_symbols)}")

        for symbol in usdc_symbols[:10]:
            market = markets[symbol]
            print(f"   • {symbol}: type={market.get('type')}, future={market.get('future')}, quote={market.get('quote')}")

        # Проверяем фильтры
        print(f"\n🔍 Проверяем фильтры:")

        # Фильтр 1: USDC в названии
        usdc_in_name = [s for s in markets.keys() if 'USDC' in s]
        print(f"   • USDC в названии: {len(usdc_in_name)}")

        # Фильтр 2: quote == 'USDC'
        usdc_quote = [s for s in markets.keys() if markets[s].get('quote') == 'USDC']
        print(f"   • quote == 'USDC': {len(usdc_quote)}")

        # Фильтр 3: future == True
        future_markets = [s for s in markets.keys() if markets[s].get('future')]
        print(f"   • future == True: {len(future_markets)}")

        # Фильтр 4: комбинация
        usdc_futures = [s for s in markets.keys()
                       if markets[s].get('quote') == 'USDC' and markets[s].get('future')]
        print(f"   • quote == 'USDC' AND future == True: {len(usdc_futures)}")

        if usdc_futures:
            print(f"\n📋 USDC Futures (по фильтру):")
            for symbol in usdc_futures[:10]:
                print(f"   • {symbol}")
            if len(usdc_futures) > 10:
                print(f"   ... и еще {len(usdc_futures) - 10} символов")

    except Exception as e:
        print(f"❌ Ошибка при анализе: {e}")

if __name__ == "__main__":
    debug_market_details()
