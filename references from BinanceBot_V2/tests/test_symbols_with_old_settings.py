#!/usr/bin/env python3
"""
Тестирование символов с настройками от старого бота
"""

import ccxt
import os
from dotenv import load_dotenv
import json

load_dotenv()

def test_symbols_with_old_settings():
    """Тестируем символы с настройками от старого бота"""

    exchange = ccxt.binance({
        'apiKey': os.getenv('BINANCE_API_KEY'),
        'secret': os.getenv('BINANCE_API_SECRET'),
        'sandbox': False,
        'options': {
            'defaultType': 'future',
        }
    })

    print("🔍 Тестирование символов с настройками от старого бота...")
    print("=" * 60)

    # Настройки от старого бота
    FILTER_TIERS = [
        {"atr": 0.0006, "volume": 5000},
        {"atr": 0.0007, "volume": 3000},
        {"atr": 0.0008, "volume": 2000},
        {"atr": 0.0009, "volume": 1000}
    ]

    try:
        markets = exchange.load_markets()

        # Получаем все USDT фьючерсы
        usdt_futures = {symbol: market for symbol, market in markets.items()
                       if market['quote'] == 'USDT' and market['future']}

        print(f"📊 Найдено USDT фьючерсов: {len(usdt_futures)}")

        # Тестируем каждый символ
        passed_symbols = []

        for symbol in list(usdt_futures.keys())[:10]:  # Тестируем первые 10
            try:
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
        print(f"   • Всего протестировано: 10 символов")
        print(f"   • Прошли фильтры: {len(passed_symbols)} символов")

        if passed_symbols:
            print(f"\n✅ ПОДХОДЯЩИЕ СИМВОЛЫ:")
            for symbol_info in passed_symbols:
                print(f"   • {symbol_info['symbol']}: ${symbol_info['volume']:,.0f} / {symbol_info['atr_percent']:.4f}%")

        # Рекомендации
        print(f"\n🎯 РЕКОМЕНДАЦИИ:")
        if len(passed_symbols) >= 5:
            print(f"   ✅ Настройки подходящие - найдено {len(passed_symbols)} символов")
        elif len(passed_symbols) >= 2:
            print(f"   ⚠️ Настройки приемлемые - найдено {len(passed_symbols)} символов")
        else:
            print(f"   ❌ Настройки слишком строгие - найдено только {len(passed_symbols)} символов")
            print(f"   💡 Рекомендуется снизить требования к объему или ATR")

    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")

if __name__ == "__main__":
    test_symbols_with_old_settings()
