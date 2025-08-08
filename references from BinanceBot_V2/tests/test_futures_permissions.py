#!/usr/bin/env python3
"""
Тест прав доступа к Futures API
"""

import asyncio
import os
import sys

# Добавляем корневую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.config import TradingConfig


async def test_futures_permissions():
    """Тестирует права доступа к Futures API"""
    try:
        print("🔐 Тестирование прав доступа к Futures API...")

        # Загружаем конфигурацию
        config = TradingConfig.load_optimized_for_profit_target(0.7)

        import ccxt

        # Создаем экземпляр биржи
        exchange = ccxt.binance({
            'apiKey': config.api_key,
            'secret': config.api_secret,
            'sandbox': getattr(config, 'use_testnet', False),
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
            }
        })

        print("✅ Подключение к Binance установлено")

        # Тестируем различные эндпоинты
        endpoints_to_test = [
            ("Публичный API - Ticker", lambda: exchange.fetch_ticker('BTC/USDT')),
            ("Публичный API - OHLCV", lambda: exchange.fetch_ohlcv('BTC/USDT', '1h', limit=1)),
            ("Приватный API - Баланс", lambda: exchange.fetch_balance()),
            ("Futures API - Позиции (fetch_positions)", lambda: exchange.fetch_positions()),
            ("Futures API - Позиции (fapiPrivateGetPositionRisk)", lambda: exchange.fapiPrivateGetPositionRisk()),
            ("Futures API - Аккаунт (fapiPrivateGetAccount)", lambda: exchange.fapiPrivateGetAccount()),
            ("Futures API - Доходы (fapiPrivateGetIncome)", lambda: exchange.fapiPrivateGetIncome({'limit': 1})),
            ("Futures API - Сделки (fapiPrivateGetUserTrades)", lambda: exchange.fapiPrivateGetUserTrades({'limit': 1})),
        ]

        for name, test_func in endpoints_to_test:
            try:
                print(f"\n📊 Тестирование: {name}")
                result = test_func()
                if isinstance(result, list):
                    print(f"✅ Успешно: получено {len(result)} записей")
                elif isinstance(result, dict):
                    print(f"✅ Успешно: получен объект с {len(result)} полями")
                else:
                    print(f"✅ Успешно: {type(result).__name__}")

            except Exception as e:
                error_msg = str(e)
                if "404" in error_msg:
                    print("❌ 404 Not Found - эндпоинт недоступен")
                elif "403" in error_msg:
                    print("❌ 403 Forbidden - нет прав доступа")
                elif "401" in error_msg:
                    print("❌ 401 Unauthorized - неверные ключи")
                else:
                    print(f"❌ Ошибка: {error_msg[:100]}...")

        print("\n📋 РЕЗЮМЕ:")
        print("✅ Если публичные API работают - подключение корректное")
        print("✅ Если приватные API работают - ключи валидные")
        print("❌ Если Futures API не работают - нужны права на Futures")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_futures_permissions())
