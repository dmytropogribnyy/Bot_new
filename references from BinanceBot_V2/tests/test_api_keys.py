#!/usr/bin/env python3
"""
Простой тест API ключей Binance
"""

import asyncio
import os
import sys

# Добавляем корневую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.config import TradingConfig
from core.unified_logger import UnifiedLogger


async def test_api_keys():
    """Тестирует API ключи"""
    try:
        print("🔑 Тестирование API ключей Binance...")

        # Загружаем конфигурацию
        config = TradingConfig.load_optimized_for_profit_target(0.7)

        print("📋 Конфигурация:")
        print(f"   • API Key: {config.api_key[:10]}...")
        print(f"   • API Secret: {config.api_secret[:10]}...")
        print(f"   • Exchange Mode: {config.exchange_mode}")
        print(f"   • Use Testnet: {getattr(config, 'use_testnet', False)}")

        # Создаем логгер
        logger = UnifiedLogger(config)

        # Тестируем подключение к Binance
        print("\n🔗 Тестирование подключения к Binance...")

        try:
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

            # Тестируем публичный API (не требует ключей)
            print("📊 Тестирование публичного API...")
            ticker = exchange.fetch_ticker('BTC/USDT')
            print(f"✅ BTC/USDT цена: ${ticker['last']}")

            # Тестируем приватный API
            print("\n🔐 Тестирование приватного API...")
            balance = exchange.fetch_balance()
            print(f"✅ Баланс получен: {len(balance['total'])} активов")

            # Показываем основные активы
            usdt_balance = balance['total'].get('USDT', 0)
            btc_balance = balance['total'].get('BTC', 0)
            print(f"   • USDT: {usdt_balance}")
            print(f"   • BTC: {btc_balance}")

            # Тестируем Futures API
            print("\n📈 Тестирование Futures API...")
            positions = exchange.fetch_positions()
            print(f"✅ Позиции получены: {len(positions)} позиций")

            # Показываем открытые позиции
            open_positions = [p for p in positions if float(p['contracts']) > 0]
            print(f"   • Открытых позиций: {len(open_positions)}")

            for pos in open_positions[:3]:  # Показываем первые 3
                print(f"   • {pos['symbol']}: {pos['contracts']} контрактов")

            print("\n✅ Все тесты прошли успешно!")

        except Exception as e:
            print(f"❌ Ошибка при тестировании: {e}")
            import traceback
            traceback.print_exc()

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_api_keys())
