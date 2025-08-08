#!/usr/bin/env python3
"""
Тест полной системы с IP монитором
"""

import asyncio

from core.config import TradingConfig
from core.exchange_client import ExchangeClient
from core.ip_monitor import IPMonitor
from core.unified_logger import UnifiedLogger


async def test_full_system():
    """Тест полной системы"""

    print("🧪 ТЕСТ ПОЛНОЙ СИСТЕМЫ")
    print("=" * 40)

    # Загружаем конфигурацию
    config = TradingConfig()
    print("✅ Конфигурация загружена")

    # Инициализируем логгер
    logger = UnifiedLogger(config)
    print("✅ Логгер инициализирован")

    # Exchange Client
    exchange = ExchangeClient(config, logger)
    print("✅ Exchange Client создан")

    # IP Monitor
    ip_monitor = IPMonitor(logger)
    print("✅ IP Monitor создан")

    # Инициализируем подключение
    if await exchange.initialize():
        print("✅ Подключение к бирже установлено")

        # Проверяем баланс
        balance = await exchange.get_balance()
        available = await exchange.get_available_balance()
        print(f"💰 Баланс: {balance:.2f} USDC")
        print(f"💰 Доступно: {available:.2f} USDC")

        # Проверяем IP
        current_ip = await ip_monitor.get_current_ip()
        print(f"🌐 IP адрес: {current_ip}")

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
        result = asyncio.run(test_full_system())
        if result:
            print("\n✅ Система полностью готова к работе!")
            print("💡 Теперь можно запускать полный бот")
        else:
            print("\n❌ Есть проблемы с системой")
    except Exception as e:
        print(f"\n❌ Ошибка теста: {e}")
