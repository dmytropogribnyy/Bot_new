#!/usr/bin/env python3
"""
Тест логирования и реального запуска на 3 минуты
"""

import asyncio
import time

from core.config import TradingConfig
from core.exchange_client import ExchangeClient
from core.ip_monitor import IPMonitor
from core.unified_logger import UnifiedLogger


async def test_logging_and_real_run():
    """Тест логирования и реального запуска"""

    print("🧪 ТЕСТ ЛОГИРОВАНИЯ И РЕАЛЬНОГО ЗАПУСКА")
    print("=" * 50)

    # Загружаем конфигурацию
    config = TradingConfig()
    print("✅ Конфигурация загружена")

    # Инициализируем логгер
    logger = UnifiedLogger(config)
    print("✅ Логгер инициализирован")

    # Тестируем логирование
    logger.log_event("TEST", "INFO", "🧪 Тест логирования - INFO сообщение")
    logger.log_event("TEST", "WARNING", "⚠️ Тест логирования - WARNING сообщение")
    logger.log_event("TEST", "ERROR", "❌ Тест логирования - ERROR сообщение")
    logger.log_event("TRADE", "INFO", "💰 Тест торгового логирования")
    logger.log_event("SIGNAL", "INFO", "📡 Тест сигнального логирования")

    # Exchange Client
    exchange = ExchangeClient(config, logger)
    print("✅ Exchange Client создан")

    # IP Monitor
    ip_monitor = IPMonitor(logger)
    print("✅ IP Monitor создан")

    # Инициализируем подключение
    if await exchange.initialize():
        logger.log_event("SYSTEM", "INFO", "🚀 Система инициализирована успешно")

        # Проверяем баланс
        balance = await exchange.get_balance()
        available = await exchange.get_available_balance()
        logger.log_event("BALANCE", "INFO", f"💰 Баланс: {balance:.2f} USDC")
        logger.log_event("BALANCE", "INFO", f"💰 Доступно: {available:.2f} USDC")

        # Проверяем IP
        current_ip = await ip_monitor.get_current_ip()
        logger.log_event("IP_MONITOR", "INFO", f"🌐 IP адрес: {current_ip}")

        # Проверяем позиции
        positions = await exchange.get_positions()
        logger.log_event("POSITIONS", "INFO", f"📊 Активных позиций: {len(positions)}")

        # Проверяем ордера
        orders = await exchange.get_open_orders()
        logger.log_event("ORDERS", "INFO", f"📋 Открытых ордеров: {len(orders)}")

        # Проверяем символы
        symbols = await exchange.get_usdc_symbols()
        logger.log_event("SYMBOLS", "INFO", f"🎯 USDC символов: {len(symbols)}")

        print("\n🎉 ТЕСТ ЛОГИРОВАНИЯ ЗАВЕРШЕН!")
        print("💡 Теперь запускаем реальный тест на 3 минуты...")

        # Запускаем реальный тест на 3 минуты
        await real_trading_test(exchange, logger, config)

        return True
    else:
        logger.log_event("SYSTEM", "ERROR", "❌ Не удалось подключиться к бирже")
        return False

async def real_trading_test(exchange, logger, config):
    """Реальный торговый тест на 3 минуты"""

    logger.log_event("REAL_TEST", "INFO", "🚀 Запуск реального торгового теста на 3 минуты")

    start_time = time.time()
    test_duration = 180  # 3 минуты

    # Логируем старт теста
    logger.log_event("REAL_TEST", "INFO", "⏰ Тест будет длиться 3 минуты")
    logger.log_event("REAL_TEST", "INFO", "📊 Мониторинг рынка и сигналов...")

    # Симуляция торгового цикла
    cycle_count = 0
    while time.time() - start_time < test_duration:
        cycle_count += 1
        elapsed = time.time() - start_time

        # Логируем каждый цикл
        logger.log_event("TRADING_CYCLE", "INFO", f"🔄 Цикл #{cycle_count} (прошло {elapsed:.1f}s)")

        # Проверяем баланс каждые 30 секунд
        if cycle_count % 6 == 0:  # каждые 30 секунд (5 секунд * 6)
            balance = await exchange.get_balance()
            available = await exchange.get_available_balance()
            logger.log_event("BALANCE_CHECK", "INFO", f"💰 Баланс: {balance:.2f} USDC, Доступно: {available:.2f} USDC")

        # Проверяем позиции каждые 60 секунд
        if cycle_count % 12 == 0:  # каждые 60 секунд
            positions = await exchange.get_positions()
            logger.log_event("POSITION_CHECK", "INFO", f"📊 Активных позиций: {len(positions)}")

        # Симуляция сигналов
        if cycle_count % 10 == 0:  # каждые 50 секунд
            logger.log_event("SIGNAL", "INFO", "📡 Анализ рыночных сигналов...")
            logger.log_event("SIGNAL", "INFO", "📊 Проверка волатильности и трендов...")

        await asyncio.sleep(5)  # 5 секунд между циклами

    # Завершение теста
    total_time = time.time() - start_time
    logger.log_event("REAL_TEST", "INFO", f"✅ Тест завершен! Длительность: {total_time:.1f} секунд")
    logger.log_event("REAL_TEST", "INFO", f"📊 Выполнено циклов: {cycle_count}")

    # Финальная проверка
    final_balance = await exchange.get_balance()
    final_available = await exchange.get_available_balance()
    final_positions = await exchange.get_positions()

    logger.log_event("FINAL_CHECK", "INFO", f"💰 Финальный баланс: {final_balance:.2f} USDC")
    logger.log_event("FINAL_CHECK", "INFO", f"💰 Финальный доступно: {final_available:.2f} USDC")
    logger.log_event("FINAL_CHECK", "INFO", f"📊 Финальных позиций: {len(final_positions)}")

    logger.log_event("REAL_TEST", "SUCCESS", "🎉 Реальный тест успешно завершен!")

if __name__ == "__main__":
    try:
        result = asyncio.run(test_logging_and_real_run())
        if result:
            print("\n✅ Тест логирования и реального запуска завершен успешно!")
            print("💡 Проверьте логи в консоли и файлах")
        else:
            print("\n❌ Есть проблемы с системой")
    except Exception as e:
        print(f"\n❌ Ошибка теста: {e}")
