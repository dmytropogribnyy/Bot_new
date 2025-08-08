#!/usr/bin/env python3
"""
Тест для проверки получения символов USDC фьючерсов
"""

import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.config import TradingConfig
from core.exchange_client import OptimizedExchangeClient
from core.unified_logger import UnifiedLogger


async def test_symbols():
    """Тестирует получение символов USDC фьючерсов"""

    print("🔍 Тестирование получения символов USDC фьючерсов...")

    try:
        # Инициализируем компоненты
        config = TradingConfig()
        logger = UnifiedLogger(config)
        exchange = OptimizedExchangeClient(config, logger)

        # Инициализируем exchange
        await exchange.initialize()

        # Очищаем кеш символов для получения свежих данных
        exchange._cache.pop('usdc_symbols', None)

        # Получаем символы
        symbols = await exchange.get_usdc_symbols()

        print(f"✅ Найдено {len(symbols)} символов USDC фьючерсов")

        if symbols:
            print("\n📊 Первые 20 символов:")
            for i, symbol in enumerate(symbols[:20], 1):
                print(f"{i:2d}. {symbol}")

            if len(symbols) > 20:
                print(f"... и еще {len(symbols) - 20} символов")

        # Проверяем тикеры для первых 5 символов
        print("\n🔍 Проверка тикеров для первых 5 символов:")
        for symbol in symbols[:5]:
            try:
                ticker = await exchange.get_ticker(symbol)
                if ticker:
                    volume = ticker.get('quoteVolume', 0)
                    price = ticker.get('last', 0)
                    print(f"✅ {symbol}: цена=${price:.4f}, объем={volume:.0f} USDC")
                else:
                    print(f"❌ {symbol}: тикер недоступен")
            except Exception as e:
                print(f"❌ {symbol}: ошибка - {e}")

        await exchange.cleanup()
        print("\n✅ Тест завершен успешно!")

    except Exception as e:
        print(f"❌ Ошибка теста: {e}")
        return False

    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(test_symbols())
        if success:
            print("🎉 Все тесты прошли успешно!")
        else:
            print("💥 Тесты завершились с ошибками")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n🛑 Тест прерван пользователем")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        sys.exit(1)
