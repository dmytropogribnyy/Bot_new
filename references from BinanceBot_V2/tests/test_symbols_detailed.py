#!/usr/bin/env python3
"""
Детальный тест для анализа проблемы с получением символов USDC фьючерсов
"""

import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.config import TradingConfig
from core.exchange_client import OptimizedExchangeClient
from core.unified_logger import UnifiedLogger


async def test_symbols_detailed():
    """Детальный тест получения символов"""

    print("🔍 Детальный анализ получения символов USDC фьючерсов...")

    try:
        # Инициализируем компоненты
        config = TradingConfig()
        logger = UnifiedLogger(config)
        exchange = OptimizedExchangeClient(config, logger)

        # Инициализируем exchange
        await exchange.initialize()

        # Очищаем кеш
        exchange._cache.pop('usdc_symbols', None)
        exchange._cache.pop('markets', None)

        # Загружаем рынки заново
        await exchange._load_markets_with_retry()

        # Получаем все рынки
        markets = exchange._cache.get('markets', {})
        print(f"📊 Всего загружено рынков: {len(markets)}")

        # Анализируем типы рынков
        market_types = {}
        quote_currencies = {}

        for symbol, market_info in markets.items():
            market_type = market_info.get('type', 'unknown')
            quote = market_info.get('quote', 'unknown')

            market_types[market_type] = market_types.get(market_type, 0) + 1
            quote_currencies[quote] = quote_currencies.get(quote, 0) + 1

        print(f"\n📈 Типы рынков:")
        for market_type, count in sorted(market_types.items()):
            print(f"  {market_type}: {count}")

        print(f"\n💰 Валюты котировок:")
        for quote, count in sorted(quote_currencies.items()):
            print(f"  {quote}: {count}")

        # Ищем USDC фьючерсы
        usdc_swap_symbols = []
        usdc_spot_symbols = []
        all_usdc_symbols = []

        for symbol, market_info in markets.items():
            if market_info.get('quote') == 'USDC':
                all_usdc_symbols.append(symbol)

            if (symbol.endswith(':USDC') and
                market_info.get('type') == 'swap' and
                market_info.get('quote') == 'USDC' and
                market_info.get('active', True)):
                usdc_swap_symbols.append(symbol)
            elif (symbol.endswith('/USDC') and
                  market_info.get('type') == 'spot' and
                  market_info.get('quote') == 'USDC' and
                  market_info.get('active', True)):
                usdc_spot_symbols.append(symbol)

        print(f"\n🎯 Все USDC рынки: {len(all_usdc_symbols)}")
        print(f"🎯 USDC фьючерсы (swap): {len(usdc_swap_symbols)}")
        print(f"🎯 USDC споты: {len(usdc_spot_symbols)}")

        if all_usdc_symbols:
            print(f"\n📋 Все USDC рынки (первые 20):")
            for i, symbol in enumerate(all_usdc_symbols[:20], 1):
                market_info = markets.get(symbol, {})
                market_type = market_info.get('type', 'unknown')
                active = market_info.get('active', False)
                print(f"  {i:2d}. {symbol} (тип: {market_type}, активен: {active})")

        if usdc_swap_symbols:
            print(f"\n📋 USDC фьючерсы (swap):")
            for i, symbol in enumerate(usdc_swap_symbols, 1):
                print(f"  {i:2d}. {symbol}")

        # Проверяем, что возвращает get_usdc_symbols
        symbols = await exchange.get_usdc_symbols()
        print(f"\n🔍 get_usdc_symbols() вернул: {len(symbols)} символов")

        if symbols:
            print(f"📋 Первые 10 из get_usdc_symbols():")
            for i, symbol in enumerate(symbols[:10], 1):
                print(f"  {i:2d}. {symbol}")

        await exchange.cleanup()
        print("\n✅ Детальный тест завершен!")

    except Exception as e:
        print(f"❌ Ошибка теста: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(test_symbols_detailed())
        if success:
            print("🎉 Детальный анализ завершен успешно!")
        else:
            print("💥 Анализ завершился с ошибками")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n🛑 Анализ прерван пользователем")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        sys.exit(1)
