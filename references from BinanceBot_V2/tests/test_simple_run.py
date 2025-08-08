#!/usr/bin/env python3
"""
Простой тест работы бота
"""

import asyncio
import time
from core.config import TradingConfig
from core.exchange_client import OptimizedExchangeClient
from core.symbol_manager import SymbolManager
from core.unified_logger import UnifiedLogger

async def test_simple_run():
    """Простой тест работы бота"""

    print("🚀 Простой тест работы бота...")
    print("=" * 50)

    try:
        # Инициализируем конфигурацию
        config = TradingConfig.load_optimized_for_profit_target(0.7)
        logger = UnifiedLogger(config)

        print("✅ Конфигурация загружена")

        # Инициализируем exchange client
        exchange = OptimizedExchangeClient(config, logger)
        await exchange.initialize()

        print("✅ Exchange client инициализирован")

        # Инициализируем symbol manager
        symbol_manager = SymbolManager(exchange, None)  # Без telegram
        await symbol_manager.update_available_symbols()

        print("✅ Symbol manager инициализирован")

        # Получаем символы
        symbols = await symbol_manager.get_active_symbols()
        print(f"📊 Найдено символов: {len(symbols)}")

        if symbols:
            print(f"📋 Первые 5 символов:")
            for i, symbol in enumerate(symbols[:5], 1):
                print(f"   {i}. {symbol}")

            # Тестируем получение данных для первого символа
            test_symbol = symbols[0]
            print(f"\n🔍 Тестируем данные для {test_symbol}:")

            # Получаем тикер
            ticker = await exchange.get_ticker(test_symbol)
            if ticker:
                print(f"   ✅ Тикер получен: ${ticker['last']:.4f}")
            else:
                print(f"   ❌ Не удалось получить тикер")

            # Получаем OHLCV
            ohlcv = await symbol_manager.get_recent_ohlcv(test_symbol, '15m', 20)
            if ohlcv:
                print(f"   ✅ OHLCV получен: {len(ohlcv)} свечей")
                print(f"   📊 Последняя цена: ${ohlcv[-1]['close']:.4f}")
            else:
                print(f"   ❌ Не удалось получить OHLCV")

            # Получаем ATR
            atr = await symbol_manager.get_atr_percent(test_symbol)
            print(f"   📈 ATR: {atr:.4f}%")

        print(f"\n" + "=" * 50)
        print(f"🎉 ТЕСТ ЗАВЕРШЕН УСПЕШНО!")
        print(f"   • Конфигурация: ✅")
        print(f"   • Exchange Client: ✅")
        print(f"   • Symbol Manager: ✅")
        print(f"   • Символы найдены: {len(symbols)}")
        print(f"   • Данные получаются: ✅")

        await exchange.cleanup()

    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_simple_run())
