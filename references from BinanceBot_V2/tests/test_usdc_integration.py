#!/usr/bin/env python3
"""
Тестирование полной интеграции с USDC Futures
"""

import asyncio
import json
from core.config import TradingConfig
from core.exchange_client import OptimizedExchangeClient
from core.symbol_manager import SymbolManager
from core.unified_logger import UnifiedLogger

async def test_usdc_integration():
    """Тестируем полную интеграцию с USDC Futures"""

    print("🔍 Тестирование полной интеграции с USDC Futures...")
    print("=" * 60)

    try:
        # Инициализируем конфигурацию
        config = TradingConfig.load_optimized_for_profit_target(0.7)
        logger = UnifiedLogger(config)

        # Инициализируем exchange client
        exchange_client = OptimizedExchangeClient(config, logger)
        await exchange_client.initialize()

        print("✅ Exchange client инициализирован")

        # Инициализируем symbol manager
        symbol_manager = SymbolManager(exchange_client)

        # Загружаем символы из файла
        symbols_from_file = symbol_manager.load_usdc_symbols_from_file()
        print(f"📊 Загружено символов из файла: {len(symbols_from_file)}")

        # Получаем доступные символы через API
        available_symbols = await symbol_manager.update_available_symbols()
        print(f"📊 Доступно на бирже: {len(available_symbols)}")

        # Получаем символы через exchange client
        usdc_symbols_api = await exchange_client.get_usdc_symbols()
        print(f"📊 Найдено через API: {len(usdc_symbols_api)}")

        print(f"\n📋 Символы из файла:")
        for i, symbol in enumerate(symbols_from_file[:10], 1):
            print(f"   {i}. {symbol}")
        if len(symbols_from_file) > 10:
            print(f"   ... и еще {len(symbols_from_file) - 10} символов")

        print(f"\n📋 Доступные на бирже:")
        for i, symbol in enumerate(available_symbols[:10], 1):
            print(f"   {i}. {symbol}")
        if len(available_symbols) > 10:
            print(f"   ... и еще {len(available_symbols) - 10} символов")

        # Тестируем получение тикера для первого символа
        if available_symbols:
            test_symbol = available_symbols[0]
            ticker = await exchange_client.get_ticker(test_symbol)
            if ticker:
                print(f"\n📊 Тест тикера для {test_symbol}:")
                print(f"   • Цена: ${ticker['last']:.4f}")
                print(f"   • Объем: ${ticker['quoteVolume']:,.0f}")
                print(f"   • Bid: ${ticker['bid']:.4f}")
                print(f"   • Ask: ${ticker['ask']:.4f}")
            else:
                print(f"❌ Не удалось получить тикер для {test_symbol}")

        # Тестируем получение OHLCV
        if available_symbols:
            ohlcv = await exchange_client.get_ohlcv(test_symbol, '15m', 20)
            if ohlcv:
                print(f"\n📈 Тест OHLCV для {test_symbol}:")
                print(f"   • Получено свечей: {len(ohlcv)}")
                print(f"   • Последняя цена: ${ohlcv[-1]['close']:.4f}")
                print(f"   • Максимум: ${ohlcv[-1]['high']:.4f}")
                print(f"   • Минимум: ${ohlcv[-1]['low']:.4f}")
            else:
                print(f"❌ Не удалось получить OHLCV для {test_symbol}")

        # Проверяем баланс
        balance = await exchange_client.get_balance()
        if balance is not None:
            print(f"\n💰 Баланс USDC: ${balance:,.2f}")
        else:
            print(f"\n❌ Не удалось получить баланс")

        print(f"\n" + "=" * 60)
        print(f"📈 РЕЗУЛЬТАТЫ ИНТЕГРАЦИИ:")
        print(f"   • Символы в файле: {len(symbols_from_file)}")
        print(f"   • Доступно на бирже: {len(available_symbols)}")
        print(f"   • Найдено через API: {len(usdc_symbols_api)}")

        if len(available_symbols) >= 30:
            print(f"   ✅ Отличная интеграция - найдено {len(available_symbols)} символов")
        elif len(available_symbols) >= 20:
            print(f"   ✅ Хорошая интеграция - найдено {len(available_symbols)} символов")
        elif len(available_symbols) >= 10:
            print(f"   ⚠️ Приемлемая интеграция - найдено {len(available_symbols)} символов")
        else:
            print(f"   ❌ Проблемы с интеграцией - найдено только {len(available_symbols)} символов")

        await exchange_client.cleanup()

    except Exception as e:
        print(f"❌ Ошибка при тестировании интеграции: {e}")

if __name__ == "__main__":
    asyncio.run(test_usdc_integration())
