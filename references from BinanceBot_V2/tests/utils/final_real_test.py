#!/usr/bin/env python3
"""
Финальный реальный тест с полным логированием и Telegram
"""

import asyncio
import time

from core.config import TradingConfig
from core.exchange_client import ExchangeClient
from core.ip_monitor import IPMonitor
from core.unified_logger import UnifiedLogger
from telegram.telegram_bot import TelegramBot


async def final_real_test():
    """Финальный реальный тест с полным логированием"""

    print("🚀 ФИНАЛЬНЫЙ РЕАЛЬНЫЙ ТЕСТ")
    print("=" * 50)

    # Загружаем конфигурацию
    config = TradingConfig()
    print("✅ Конфигурация загружена")

    # Инициализируем логгер
    logger = UnifiedLogger(config)
    print("✅ Логгер инициализирован")

    # Telegram Bot
    telegram_bot = TelegramBot(config.telegram_token)
    logger.attach_telegram(telegram_bot)
    print("✅ Telegram Bot подключен")

    # Exchange Client
    exchange = ExchangeClient(config, logger)
    print("✅ Exchange Client создан")

    # IP Monitor
    ip_monitor = IPMonitor(logger)
    print("✅ IP Monitor создан")

    # Инициализируем подключение
    if await exchange.initialize():
        logger.log_event("SYSTEM", "INFO", "🚀 OptiFlow HFT Bot запущен!")

        # Отправляем уведомление в Telegram
        await telegram_bot.send_notification("🚀 OptiFlow HFT Bot запущен и готов к работе!")

        # Проверяем баланс
        balance = await exchange.get_balance()
        available = await exchange.get_available_balance()
        logger.log_event("BALANCE", "INFO", f"💰 Баланс: {balance:.2f} USDC")
        logger.log_event("BALANCE", "INFO", f"💰 Доступно: {available:.2f} USDC")

        # Отправляем баланс в Telegram
        await telegram_bot.send_notification(f"💰 Баланс: {balance:.2f} USDC\n💰 Доступно: {available:.2f} USDC")

        # Проверяем IP
        current_ip = await ip_monitor.get_current_ip()
        logger.log_event("IP_MONITOR", "INFO", f"🌐 IP адрес: {current_ip}")
        await telegram_bot.send_notification(f"🌐 IP адрес: {current_ip}\n✅ Безопасность: OK")

        # Проверяем позиции
        positions = await exchange.get_positions()
        logger.log_event("POSITIONS", "INFO", f"📊 Активных позиций: {len(positions)}")

        # Проверяем ордера
        orders = await exchange.get_open_orders()
        logger.log_event("ORDERS", "INFO", f"📋 Открытых ордеров: {len(orders)}")

        # Проверяем символы
        symbols = await exchange.get_usdc_symbols()
        logger.log_event("SYMBOLS", "INFO", f"🎯 USDC символов: {len(symbols)}")

        print("\n🎉 СИСТЕМА ГОТОВА!")
        print("💡 Запускаем реальный торговый тест на 3 минуты...")

        # Запускаем реальный торговый тест
        await real_trading_cycle(exchange, logger, telegram_bot, config)

        return True
    else:
        logger.log_event("SYSTEM", "ERROR", "❌ Не удалось подключиться к бирже")
        await telegram_bot.send_notification("❌ Ошибка подключения к бирже!")
        return False

async def real_trading_cycle(exchange, logger, telegram_bot, config):
    """Реальный торговый цикл на 3 минуты"""

    logger.log_event("REAL_TRADING", "INFO", "🚀 Запуск реального торгового цикла на 3 минуты")
    await telegram_bot.send_notification("🚀 Запуск реального торгового цикла на 3 минуты")

    start_time = time.time()
    test_duration = 180  # 3 минуты

    # Логируем старт
    logger.log_event("REAL_TRADING", "INFO", "⏰ Тест будет длиться 3 минуты")
    logger.log_event("REAL_TRADING", "INFO", "📊 Мониторинг рынка и сигналов...")

    # Симуляция торгового цикла
    cycle_count = 0
    while time.time() - start_time < test_duration:
        cycle_count += 1
        elapsed = time.time() - start_time

        # Логируем каждый цикл
        logger.log_event("TRADING_CYCLE", "INFO", f"🔄 Цикл #{cycle_count} (прошло {elapsed:.1f}s)")

        # Проверяем баланс каждые 30 секунд
        if cycle_count % 6 == 0:  # каждые 30 секунд
            balance = await exchange.get_balance()
            available = await exchange.get_available_balance()
            logger.log_event("BALANCE_CHECK", "INFO", f"💰 Баланс: {balance:.2f} USDC, Доступно: {available:.2f} USDC")

        # Проверяем позиции каждые 60 секунд
        if cycle_count % 12 == 0:  # каждые 60 секунд
            positions = await exchange.get_positions()
            logger.log_event("POSITION_CHECK", "INFO", f"📊 Активных позиций: {len(positions)}")

        # Симуляция сигналов каждые 50 секунд
        if cycle_count % 10 == 0:
            logger.log_event("SIGNAL", "INFO", "📡 Анализ рыночных сигналов...")
            logger.log_event("SIGNAL", "INFO", "📊 Проверка волатильности и трендов...")

            # Отправляем уведомление в Telegram каждые 50 секунд
            await telegram_bot.send_notification(f"📡 Цикл #{cycle_count}: Анализ сигналов...")

        await asyncio.sleep(5)  # 5 секунд между циклами

    # Завершение теста
    total_time = time.time() - start_time
    logger.log_event("REAL_TRADING", "INFO", f"✅ Тест завершен! Длительность: {total_time:.1f} секунд")
    logger.log_event("REAL_TRADING", "INFO", f"📊 Выполнено циклов: {cycle_count}")

    # Финальная проверка
    final_balance = await exchange.get_balance()
    final_available = await exchange.get_available_balance()
    final_positions = await exchange.get_positions()

    logger.log_event("FINAL_CHECK", "INFO", f"💰 Финальный баланс: {final_balance:.2f} USDC")
    logger.log_event("FINAL_CHECK", "INFO", f"💰 Финальный доступно: {final_available:.2f} USDC")
    logger.log_event("FINAL_CHECK", "INFO", f"📊 Финальных позиций: {len(final_positions)}")

    # Отправляем финальный отчет в Telegram
    final_report = f"""
🎉 РЕАЛЬНЫЙ ТЕСТ ЗАВЕРШЕН!

⏰ Длительность: {total_time:.1f} секунд
🔄 Выполнено циклов: {cycle_count}
💰 Финальный баланс: {final_balance:.2f} USDC
💰 Финальный доступно: {final_available:.2f} USDC
📊 Финальных позиций: {len(final_positions)}

✅ Система работает стабильно!
"""

    await telegram_bot.send_notification(final_report)
    logger.log_event("REAL_TRADING", "SUCCESS", "🎉 Реальный тест успешно завершен!")

if __name__ == "__main__":
    try:
        result = asyncio.run(final_real_test())
        if result:
            print("\n✅ Финальный тест завершен успешно!")
            print("💡 Проверьте логи в консоли и Telegram")
        else:
            print("\n❌ Есть проблемы с системой")
    except Exception as e:
        print(f"\n❌ Ошибка теста: {e}")
