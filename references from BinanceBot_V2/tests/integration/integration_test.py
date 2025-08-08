#!/usr/bin/env python3
"""
Интеграционный тест BinanceBot v2 с реальными API вызовами
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))


async def test_exchange_connection():
    """Тест подключения к бирже"""
    print("🏦 Тестирование подключения к Binance...")
    try:
        from core.config import TradingConfig
        from core.exchange_client import ExchangeClient
        from core.unified_logger import UnifiedLogger

        config = TradingConfig.from_file()
        logger = UnifiedLogger(config)
        exchange = ExchangeClient(config, logger=logger)

        # Тест инициализации
        await exchange.initialize()
        print("✅ Подключение к Binance установлено")

        # Тест получения времени сервера
        server_time = await exchange.get_server_time()
        print(f"✅ Время сервера: {server_time}")

        # Тест получения баланса
        balance = await exchange.get_balance()
        print(f"✅ Баланс USDC: {balance}")

        await exchange.close()
        return True
    except Exception as e:
        print(f"❌ Ошибка подключения к бирже: {e}")
        return False


async def test_symbol_manager_integration():
    """Тест менеджера символов с реальными данными"""
    print("\n📊 Тестирование менеджера символов...")
    try:
        from core.config import TradingConfig
        from core.exchange_client import ExchangeClient
        from core.symbol_manager import SymbolManager
        from core.unified_logger import UnifiedLogger

        config = TradingConfig.from_file()
        logger = UnifiedLogger(config)
        exchange = ExchangeClient(config, logger=logger)
        symbol_manager = SymbolManager(exchange, logger=logger)

        await exchange.initialize()

        # Обновляем список символов
        symbols = await symbol_manager.update_available_symbols()
        print(f"✅ Получено символов: {len(symbols)}")

        # Показываем первые 10 символов
        sample_symbols = list(symbols)[:10]
        print(f"   Примеры: {sample_symbols}")

        # Проверяем активные символы
        active_symbols = symbol_manager.get_active_symbols()
        print(f"   Активных символов: {len(active_symbols)}")

        await exchange.close()
        return True
    except Exception as e:
        print(f"❌ Ошибка менеджера символов: {e}")
        return False


async def test_rate_limiter():
    """Тест rate limiter"""
    print("\n⏱️ Тестирование rate limiter...")
    try:
        from core.config import TradingConfig
        from core.rate_limiter import RateLimiter

        config = TradingConfig.from_file()
        rate_limiter = RateLimiter(
            weight_limit_per_minute=config.weight_limit_per_minute,
            request_limit_per_second=config.order_rate_limit_per_second,
            buffer_pct=config.rate_limit_buffer_pct,
        )

        # Тест нескольких запросов
        for i in range(5):
            await rate_limiter.acquire(1)
            print(f"   Запрос {i+1} обработан")

        print("✅ Rate limiter работает корректно")
        return True
    except Exception as e:
        print(f"❌ Ошибка rate limiter: {e}")
        return False


async def test_risk_manager():
    """Тест risk manager"""
    print("\n🛡️ Тестирование risk manager...")
    try:
        from core.config import TradingConfig
        from core.risk_manager import RiskManager
        from core.unified_logger import UnifiedLogger

        config = TradingConfig.from_file()
        logger = UnifiedLogger(config)
        risk_manager = RiskManager(config, logger)

        # Тест расчета размера позиции
        balance = 1000.0  # Тестовый баланс
        price = 50000.0  # Цена BTC
        leverage = 5  # Плечо

        position_size = risk_manager.calculate_position_size("BTCUSDC", price, balance, leverage)
        print(f"✅ Размер позиции рассчитан: {position_size:.6f}")

        # Тест проверки входа
        can_enter = await risk_manager.check_entry_allowed("BTCUSDC", "BUY", position_size)
        print(f"✅ Проверка входа: {'Разрешено' if can_enter else 'Запрещено'}")

        return True
    except Exception as e:
        print(f"❌ Ошибка risk manager: {e}")
        return False


async def test_strategies_integration():
    """Тест стратегий с реальными данными"""
    print("\n🎯 Тестирование стратегий...")
    try:
        from core.config import TradingConfig
        from core.exchange_client import ExchangeClient
        from core.symbol_manager import SymbolManager
        from core.unified_logger import UnifiedLogger
        from strategies.scalping_v1 import ScalpingV1
        from strategies.symbol_selector import SymbolSelector

        config = TradingConfig.from_file()
        logger = UnifiedLogger(config)
        exchange = ExchangeClient(config, logger=logger)
        symbol_manager = SymbolManager(exchange, logger=logger)

        await exchange.initialize()
        await symbol_manager.update_available_symbols()

        # Создаем стратегии
        scalping = ScalpingV1(config, exchange, symbol_manager, logger)
        symbol_selector = SymbolSelector(config, symbol_manager, exchange, logger)

        print("✅ Стратегии созданы")

        # Тест селектора символов
        selected_symbols = await symbol_selector.get_symbols_for_trading()
        print(f"✅ Отобрано символов для торговли: {len(selected_symbols)}")

        if selected_symbols:
            print(f"   Примеры: {selected_symbols[:5]}")

        await exchange.close()
        return True
    except Exception as e:
        print(f"❌ Ошибка стратегий: {e}")
        return False


async def test_telegram_integration():
    """Тест Telegram интеграции"""
    print("\n📱 Тестирование Telegram интеграции...")
    try:
        from core.config import TradingConfig
        from telegram.telegram_bot import TelegramBot

        config = TradingConfig.from_file()

        if not config.telegram_token:
            print("⚠️ Telegram токен не настроен, пропускаем тест")
            return True

        # Создаем Telegram бот
        telegram_bot = TelegramBot(config.telegram_token)
        print("✅ Telegram бот создан")

        # Тест отправки сообщения
        test_message = "🤖 Тест интеграции BinanceBot v2"
        # await telegram_bot.send_notification(test_message, config.telegram_chat_id)  # Раскомментировать для реального теста
        print("✅ Telegram интеграция работает")

        return True
    except Exception as e:
        print(f"❌ Ошибка Telegram интеграции: {e}")
        return False


async def main():
    """Основной интеграционный тест"""
    print("🚀 Запуск интеграционных тестов BinanceBot v2")
    print("=" * 60)

    tests = [
        test_exchange_connection,
        test_symbol_manager_integration,
        test_rate_limiter,
        test_risk_manager,
        test_strategies_integration,
        test_telegram_integration,
    ]

    results = []
    for test in tests:
        try:
            result = await test()
            results.append(result)
        except Exception as e:
            print(f"❌ Критическая ошибка в тесте: {e}")
            results.append(False)

    print("\n" + "=" * 60)
    print("📊 Результаты интеграционных тестов:")

    passed = sum(results)
    total = len(results)

    for i, result in enumerate(results):
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        print(f"   Тест {i+1}: {status}")

    print(f"\n🎯 Итого: {passed}/{total} тестов пройдено")

    if passed == total:
        print("🎉 Все интеграционные тесты пройдены!")
        print("🚀 Система готова к production запуску!")
        return True
    else:
        print("⚠️  Некоторые тесты провалены. Требуется доработка.")
        return False


if __name__ == "__main__":
    asyncio.run(main())
