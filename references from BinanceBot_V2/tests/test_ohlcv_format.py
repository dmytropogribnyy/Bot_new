#!/usr/bin/env python3
"""
Тест формата OHLCV данных
"""

import asyncio
import pandas as pd
from core.config import TradingConfig
from core.exchange_client import OptimizedExchangeClient
from core.symbol_manager import SymbolManager
from core.unified_logger import UnifiedLogger

async def test_ohlcv_format():
    """Тестируем формат OHLCV данных"""

    print("🔍 Тестируем формат OHLCV данных...")
    print("=" * 50)

    try:
        # Инициализируем конфигурацию
        config = TradingConfig.load_optimized_for_profit_target(0.7)
        logger = UnifiedLogger(config)

        # Инициализируем exchange client
        exchange = OptimizedExchangeClient(config, logger)
        await exchange.initialize()

        # Инициализируем symbol manager
        symbol_manager = SymbolManager(exchange, None)
        await symbol_manager.update_available_symbols()

        # Получаем символы
        symbols = await symbol_manager.get_active_symbols()
        if not symbols:
            print("❌ Нет доступных символов")
            return

        test_symbol = symbols[0]
        print(f"📊 Тестируем символ: {test_symbol}")

        # Получаем OHLCV данные
        ohlcv_data = await symbol_manager.get_recent_ohlcv(test_symbol, '15m', 20)

        print(f"📈 Получено данных: {len(ohlcv_data)}")

        if ohlcv_data:
            print(f"📋 Первая запись:")
            print(f"   {ohlcv_data[0]}")

            print(f"\n📋 Последняя запись:")
            print(f"   {ohlcv_data[-1]}")

            # Проверяем структуру
            print(f"\n🔍 Анализ структуры:")
            keys = list(ohlcv_data[0].keys())
            print(f"   Ключи: {keys}")

            # Проверяем типы данных
            print(f"\n📊 Типы данных:")
            for key in keys:
                value = ohlcv_data[0][key]
                print(f"   {key}: {type(value)} = {value}")

            # Пробуем конвертировать в DataFrame
            print(f"\n🔄 Конвертация в DataFrame:")
            try:
                df = pd.DataFrame(ohlcv_data)
                print(f"   ✅ DataFrame создан: {df.shape}")
                print(f"   📋 Колонки: {list(df.columns)}")
                print(f"   📊 Первые 3 строки:")
                print(df.head(3))

                # Проверяем доступ к данным
                if 'close' in df.columns:
                    print(f"   💰 Последняя цена: {df['close'].iloc[-1]}")
                if 'high' in df.columns:
                    print(f"   📈 Максимум: {df['high'].iloc[-1]}")
                if 'low' in df.columns:
                    print(f"   📉 Минимум: {df['low'].iloc[-1]}")

            except Exception as e:
                print(f"   ❌ Ошибка конвертации: {e}")

        await exchange.cleanup()

    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_ohlcv_format())
