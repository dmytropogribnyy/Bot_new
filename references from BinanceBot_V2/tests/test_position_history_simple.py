#!/usr/bin/env python3
"""
Простой тест Position History Reporter с прямым использованием ccxt
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta

# Добавляем корневую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.config import TradingConfig
from core.unified_logger import UnifiedLogger


async def test_position_history_simple():
    """Тестирует Position History Reporter с прямым использованием ccxt"""
    try:
        print("🧪 Тестирование Position History Reporter (простая версия)...")

        # Загружаем конфигурацию
        config = TradingConfig.load_optimized_for_profit_target(0.7)

        # Создаем логгер
        logger = UnifiedLogger(config)

        # Создаем экземпляр биржи напрямую
        import ccxt

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

        # Определяем временной диапазон
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=24)

        # Тестируем получение сделок
        print("\n📈 Получение сделок пользователя...")
        try:
            params = {
                'limit': 50,
                'startTime': int(start_time.timestamp() * 1000),
                'endTime': int(end_time.timestamp() * 1000)
            }

            trades = exchange.fapiPrivateGetUserTrades(params)
            print(f"✅ Получено {len(trades)} сделок")

            if trades:
                print("📋 Примеры сделок:")
                for i, trade in enumerate(trades[:5], 1):
                    print(f"   {i}. {trade['symbol']} {trade['side']} {trade['qty']} @ {trade['price']}")
                    print(f"      Время: {datetime.fromtimestamp(trade['time']/1000)}")
                    print(f"      Комиссия: {trade['commission']}")

        except Exception as e:
            print(f"❌ Ошибка при получении сделок: {e}")

        # Тестируем получение позиций
        print("\n📊 Получение позиций...")
        try:
            positions = exchange.fetch_positions()
            open_positions = [pos for pos in positions if float(pos.get('contracts', 0)) != 0]
            print(f"✅ Получено {len(positions)} позиций, открытых: {len(open_positions)}")

            if open_positions:
                print("📋 Открытые позиции:")
                for pos in open_positions:
                    print(f"   • {pos['symbol']}: {pos['contracts']} контрактов (PnL: {pos.get('unrealizedPnl', 'N/A')})")

        except Exception as e:
            print(f"❌ Ошибка при получении позиций: {e}")

        # Тестируем получение доходов
        print("\n💰 Получение доходов...")
        try:
            income = exchange.fapiPrivateGetIncome({
                'limit': 50,
                'startTime': int(start_time.timestamp() * 1000),
                'endTime': int(end_time.timestamp() * 1000)
            })
            print(f"✅ Получено {len(income)} записей доходов")

            if income:
                print("📋 Примеры доходов:")
                for i, inc in enumerate(income[:5], 1):
                    print(f"   {i}. {inc['symbol']} {inc['incomeType']}: {inc['income']}")

        except Exception as e:
            print(f"❌ Ошибка при получении доходов: {e}")

        # Тестируем получение информации об аккаунте
        print("\n🏦 Получение информации об аккаунте...")
        try:
            balance = exchange.fetch_balance()
            print("✅ Информация об аккаунте получена")
            print(f"   • USDT Balance: {balance.get('total', {}).get('USDT', 0)}")
            print(f"   • BTC Balance: {balance.get('total', {}).get('BTC', 0)}")

        except Exception as e:
            print(f"❌ Ошибка при получении информации об аккаунте: {e}")

        print("\n✅ Тестирование завершено успешно!")

    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_position_history_simple())
