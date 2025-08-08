#!/usr/bin/env python3
"""
Простой тест подключения и базовой функциональности
"""

import asyncio

from core.config import TradingConfig
from core.exchange_client import ExchangeClient
from core.unified_logger import UnifiedLogger


async def simple_test():
    """Простой тест подключения"""

    print("🧪 ПРОСТОЙ ТЕСТ ПОДКЛЮЧЕНИЯ")
    print("=" * 40)

    # Загружаем конфигурацию
    config = TradingConfig()
    print("✅ Конфигурация загружена")
    print(f"   • API Key: {config.api_key[:10]}...")
    print(f"   • Exchange Mode: {config.exchange_mode}")
    print(f"   • Telegram: {'Включен' if config.telegram_token else 'Отключен'}")

    # Инициализируем логгер
    logger = UnifiedLogger(config)
    print("✅ Логгер инициализирован")

    # Exchange Client
    exchange = ExchangeClient(config, logger)
    print("✅ Exchange Client создан")

    # Инициализируем подключение
    if await exchange.initialize():
        print("✅ Подключение к бирже установлено")

        # Проверяем баланс
        balance = await exchange.get_balance()
        available = await exchange.get_available_balance()
        print(f"💰 Баланс: {balance:.2f} USDC")
        print(f"💰 Доступно: {available:.2f} USDC")

        # Проверяем позиции
        positions = await exchange.get_positions()
        print(f"📊 Активных позиций: {len(positions)}")

        # Проверяем ордера
        orders = await exchange.get_open_orders()
        print(f"📋 Открытых ордеров: {len(orders)}")

        # Проверяем символы
        symbols = await exchange.get_usdc_symbols()
        print(f"🎯 USDC символов: {len(symbols)}")

        print("\n🎉 ТЕСТ ЗАВЕРШЕН УСПЕШНО!")
        return True
    else:
        print("❌ Не удалось подключиться к бирже")
        return False

if __name__ == "__main__":
    try:
        result = asyncio.run(simple_test())
        if result:
            print("\n✅ Система готова к работе!")
            print("💡 Теперь можно запускать полный бот")
        else:
            print("\n❌ Есть проблемы с подключением")
    except Exception as e:
        print(f"\n❌ Ошибка теста: {e}")
