#!/usr/bin/env python3
"""
Тестирование USDC Futures символов
"""

import ccxt
import os
import json
from dotenv import load_dotenv

load_dotenv()

def test_usdc_futures():
    """Тестируем USDC Futures символы"""

    exchange = ccxt.binance({
        'apiKey': os.getenv('BINANCE_API_KEY'),
        'secret': os.getenv('BINANCE_API_SECRET'),
        'sandbox': False,
        'options': {
            'defaultType': 'future',
        }
    })

    print("🔍 Тестирование USDC Futures символов...")
    print("=" * 60)

    # Загружаем символы из файла
    try:
        with open('data/valid_usdc_symbols.json', 'r') as f:
            usdc_symbols = json.load(f)
        print(f"📊 Загружено {len(usdc_symbols)} USDC символов из файла")
    except Exception as e:
        print(f"❌ Ошибка загрузки символов: {e}")
        return

    # Настройки от старого бота
    FILTER_TIERS = [
        {"atr": 0.0006, "volume": 5000},
        {"atr": 0.0007, "volume": 3000},
        {"atr": 0.0008, "volume": 2000},
        {"atr": 0.0009, "volume": 1000}
    ]

    try:
        markets = exchange.load_markets()

        # Получаем все USDC фьючерсы
        usdc_futures = {symbol: market for symbol, market in markets.items()
                       if market['quote'] == 'USDC' and market['future']}

        print(f"📊 Найдено USDC фьючерсов на Binance: {len(usdc_futures)}")

        # Тестируем каждый символ из нашего списка
        passed_symbols = []
        available_symbols = []

        for symbol in usdc_symbols:
            try:
                # Проверяем, доступен ли символ на Binance
                if symbol not in markets:
                    print(f"   ⚠️ {symbol}: Недоступен на Binance")
                    continue

                available_symbols.append(symbol)
                ticker = exchange.fetch_ticker(symbol)
                volume = ticker['quoteVolume']

                # Получаем OHLCV для расчета ATR
                ohlcv = exchange.fetch_ohlcv(symbol, '15m', limit=20)
                if len(ohlcv) < 20:
                    print(f"   ⚠️ {symbol}: Недостаточно данных")
                    continue

                # Простой расчет ATR
                highs = [candle[2] for candle in ohlcv]
                lows = [candle[3] for candle in ohlcv]
                closes = [candle[4] for candle in ohlcv]

                # ATR (упрощенный)
                tr_values = []
                for i in range(1, len(ohlcv)):
                    high_low = highs[i] - lows[i]
                    high_close = abs(highs[i] - closes[i-1])
                    low_close = abs(lows[i] - closes[i-1])
                    tr = max(high_low, high_close, low_close)
                    tr_values.append(tr)

                atr = sum(tr_values) / len(tr_values) if tr_values else 0
                atr_percent = (atr / ticker['last']) * 100

                print(f"   📊 {symbol}:")
                print(f"      • Объем: ${volume:,.0f}")
                print(f"      • ATR: {atr_percent:.4f}%")
                print(f"      • Цена: ${ticker['last']:.4f}")

                # Проверяем фильтры
                passed_tier = None
                for tier in FILTER_TIERS:
                    if volume >= tier['volume'] and atr_percent >= tier['atr']:
                        passed_tier = tier
                        break

                if passed_tier:
                    print(f"      ✅ ПРОШЕЛ фильтр: ATR≥{passed_tier['atr']}% / VOL≥${passed_tier['volume']:,.0f}")
                    passed_symbols.append({
                        'symbol': symbol,
                        'volume': volume,
                        'atr_percent': atr_percent,
                        'price': ticker['last'],
                        'tier': passed_tier
                    })
                else:
                    print(f"      ❌ НЕ ПРОШЕЛ фильтры")

            except Exception as e:
                print(f"   ❌ {symbol}: Ошибка - {e}")

        print(f"\n" + "=" * 60)
        print(f"📈 РЕЗУЛЬТАТЫ:")
        print(f"   • Всего символов в списке: {len(usdc_symbols)}")
        print(f"   • Доступно на Binance: {len(available_symbols)}")
        print(f"   • Прошли фильтры: {len(passed_symbols)} символов")

        if passed_symbols:
            print(f"\n✅ ПОДХОДЯЩИЕ СИМВОЛЫ:")
            for symbol_info in passed_symbols:
                print(f"   • {symbol_info['symbol']}: ${symbol_info['volume']:,.0f} / {symbol_info['atr_percent']:.4f}%")

        # Рекомендации
        print(f"\n🎯 РЕКОМЕНДАЦИИ:")
        if len(passed_symbols) >= 20:
            print(f"   ✅ Отличные настройки - найдено {len(passed_symbols)} символов")
        elif len(passed_symbols) >= 10:
            print(f"   ✅ Хорошие настройки - найдено {len(passed_symbols)} символов")
        elif len(passed_symbols) >= 5:
            print(f"   ⚠️ Приемлемые настройки - найдено {len(passed_symbols)} символов")
        else:
            print(f"   ❌ Настройки слишком строгие - найдено только {len(passed_symbols)} символов")
            print(f"   💡 Рекомендуется снизить требования к объему или ATR")

    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")

if __name__ == "__main__":
    test_usdc_futures()
