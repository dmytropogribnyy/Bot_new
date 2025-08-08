#!/usr/bin/env python3
"""
Тест Telegram уведомлений
"""

import asyncio

from core.config import TradingConfig
from core.unified_logger import UnifiedLogger
from telegram.telegram_bot import TelegramBot


async def test_telegram_notifications():
    """Тест Telegram уведомлений"""

    print("🧪 ТЕСТ TELEGRAM УВЕДОМЛЕНИЙ")
    print("=" * 40)

    # Загружаем конфигурацию
    config = TradingConfig()
    print("✅ Конфигурация загружена")

    # Инициализируем логгер
    logger = UnifiedLogger(config)
    print("✅ Логгер инициализирован")

    # Telegram Bot
    try:
        telegram_bot = TelegramBot(config.telegram_token)
        print("✅ Telegram Bot создан")

        # Привязываем к логгеру
        logger.attach_telegram(telegram_bot)
        print("✅ Telegram привязан к логгеру")

        # Тестируем отправку сообщений
        print("\n📱 Отправляем тестовые сообщения...")

        # Тест 1: Простое сообщение
        await telegram_bot.send_notification("🧪 Тест 1: Простое уведомление")
        print("✅ Тест 1 отправлен")

        # Тест 2: Сообщение с эмодзи
        await telegram_bot.send_notification("💰 Тест 2: Торговое уведомление")
        print("✅ Тест 2 отправлен")

        # Тест 3: Предупреждение
        await telegram_bot.send_notification("⚠️ Тест 3: Предупреждение")
        print("✅ Тест 3 отправлен")

        # Тест 4: Ошибка
        await telegram_bot.send_notification("❌ Тест 4: Сообщение об ошибке")
        print("✅ Тест 4 отправлен")

        # Тест 5: Успех
        await telegram_bot.send_notification("🎉 Тест 5: Сообщение об успехе")
        print("✅ Тест 5 отправлен")

        # Тест 6: Статус бота
        await telegram_bot.send_notification("🚀 Бот OptiFlow HFT запущен и работает!")
        print("✅ Тест 6 отправлен")

        # Тест 7: Информация о балансе
        await telegram_bot.send_notification("💰 Баланс: 343.00 USDC\n💰 Доступно: 288.97 USDC")
        print("✅ Тест 7 отправлен")

        # Тест 8: IP информация
        await telegram_bot.send_notification("🌐 IP адрес: 178.41.93.39\n✅ Безопасность: OK")
        print("✅ Тест 8 отправлен")

        print("\n🎉 ВСЕ TELEGRAM ТЕСТЫ ОТПРАВЛЕНЫ!")
        print("💡 Проверьте ваш Telegram бот @diplex_trade_alert_bot")

        return True

    except Exception as e:
        print(f"❌ Ошибка Telegram: {e}")
        return False

if __name__ == "__main__":
    try:
        result = asyncio.run(test_telegram_notifications())
        if result:
            print("\n✅ Telegram тесты завершены успешно!")
            print("💡 Проверьте сообщения в Telegram")
        else:
            print("\n❌ Есть проблемы с Telegram")
    except Exception as e:
        print(f"\n❌ Ошибка теста: {e}")
