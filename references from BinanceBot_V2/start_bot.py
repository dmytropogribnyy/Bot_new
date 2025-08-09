#!/usr/bin/env python3
"""
Простой скрипт для запуска OptiFlow HFT Bot
"""

import asyncio
import os
import sys

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.config import TradingConfig
from core.exchange_client import ExchangeClient
from core.ip_monitor import IPMonitor
from core.unified_logger import UnifiedLogger
from telegram.telegram_bot import TelegramBot


async def start_bot():
    """Запуск бота с полным логированием"""

    print("🚀 ЗАПУСК OPTIFLOW HFT BOT")
    print("=" * 50)

    try:
        # Загружаем конфигурацию
        config = TradingConfig()
        print("✅ Конфигурация загружена")

        # Инициализируем логгер
        logger = UnifiedLogger(config)
        print("✅ Логгер инициализирован")

        # Telegram Bot
        telegram_bot = TelegramBot(config.telegram_token)
        telegram_bot.set_chat_id(config.telegram_chat_id)  # Устанавливаем chat_id
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
            await telegram_bot.send_notification(
                f"💰 Баланс: {balance:.2f} USDC\n💰 Доступно: {available:.2f} USDC"
            )

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

            print("\n🎉 БОТ ЗАПУЩЕН УСПЕШНО!")
            print("💡 Проверьте логи в консоли и Telegram")
            print("📱 Telegram: @diplex_trade_alert_bot")
            print("🛑 Для остановки нажмите Ctrl+C")

            # Запускаем мониторинг IP
            await ip_monitor.monitor_loop()

        else:
            logger.log_event("SYSTEM", "ERROR", "❌ Не удалось подключиться к бирже")
            await telegram_bot.send_notification("❌ Ошибка подключения к бирже!")
            return False

    except KeyboardInterrupt:
        print("\n🛑 Остановка бота...")
        logger.log_event("SYSTEM", "INFO", "🛑 Бот остановлен пользователем")
        await telegram_bot.send_notification("🛑 Бот остановлен пользователем")
        return True

    except Exception as e:
        print(f"\n❌ Ошибка запуска: {e}")
        if "logger" in locals():
            logger.log_event("SYSTEM", "ERROR", f"❌ Ошибка запуска: {e}")
        if "telegram_bot" in locals():
            await telegram_bot.send_notification(f"❌ Ошибка запуска: {e}")
        return False


if __name__ == "__main__":
    try:
        result = asyncio.run(start_bot())
        if result:
            print("\n✅ Бот завершил работу корректно")
        else:
            print("\n❌ Бот завершил работу с ошибками")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
