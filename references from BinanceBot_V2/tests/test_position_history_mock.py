#!/usr/bin/env python3
"""
Тестовый скрипт с мок-данными для Position History Reporter
Проверяет функциональность без реальных API ключей
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import patch

# Добавляем корневую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.config import TradingConfig
from core.position_history_reporter import PositionHistoryReporter, PositionSummary, TradePosition
from core.unified_logger import UnifiedLogger


def create_mock_trades():
    """Создает мок-данные для тестирования"""
    return [
        {
            'symbol': 'BTCUSDT',
            'orderId': '12345',
            'side': 'BUY',
            'price': '45000.00',
            'qty': '0.001',
            'commission': '0.045',
            'time': int((datetime.now() - timedelta(hours=2)).timestamp() * 1000)
        },
        {
            'symbol': 'BTCUSDT',
            'orderId': '12345',
            'side': 'SELL',
            'price': '45100.00',
            'qty': '0.001',
            'commission': '0.045',
            'time': int((datetime.now() - timedelta(hours=1)).timestamp() * 1000)
        },
        {
            'symbol': 'ETHUSDT',
            'orderId': '67890',
            'side': 'BUY',
            'price': '3000.00',
            'qty': '0.01',
            'commission': '0.03',
            'time': int((datetime.now() - timedelta(hours=3)).timestamp() * 1000)
        },
        {
            'symbol': 'ETHUSDT',
            'orderId': '67890',
            'side': 'SELL',
            'price': '2990.00',
            'qty': '0.01',
            'commission': '0.03',
            'time': int((datetime.now() - timedelta(hours=2.5)).timestamp() * 1000)
        }
    ]


def create_mock_income():
    """Создает мок-данные для income history"""
    return [
        {
            'symbol': 'BTCUSDT',
            'incomeType': 'FUNDING_FEE',
            'income': '0.05',
            'time': int((datetime.now() - timedelta(hours=1)).timestamp() * 1000)
        },
        {
            'symbol': 'ETHUSDT',
            'incomeType': 'FUNDING_FEE',
            'income': '-0.02',
            'time': int((datetime.now() - timedelta(hours=1)).timestamp() * 1000)
        }
    ]


async def test_position_history_mock():
    """Тестирует Position History Reporter с мок-данными"""
    try:
        print("🧪 Тестирование Position History Reporter с мок-данными...")

        # Загружаем конфигурацию
        config = TradingConfig.load_optimized_for_profit_target(0.7)
        logger = UnifiedLogger(config)

        # Создаем репортер
        reporter = PositionHistoryReporter(config, logger)

        # Мокаем API вызовы
        with patch.object(reporter, 'get_user_trades', return_value=create_mock_trades()), \
             patch.object(reporter, 'get_income_history', return_value=create_mock_income()), \
             patch.object(reporter, 'get_position_risk', return_value=[]), \
             patch.object(reporter, 'get_account_info', return_value={}), \
             patch.object(reporter.exchange_client, 'initialize', return_value=True):

            # Инициализируем
            if not await reporter.initialize():
                print("❌ Не удалось инициализировать репортер")
                return

            print("✅ Репортер инициализирован")

            # Тестируем отдельные API
            print("\n📈 Тестирование API вызовов...")

            # Тест получения сделок
            trades = await reporter.get_user_trades(limit=5)
            print(f"✅ Получено {len(trades)} сделок")

            # Тест получения позиций
            positions = await reporter.get_position_risk()
            print(f"✅ Получено {len(positions)} позиций")

            # Тест получения доходов
            income = await reporter.get_income_history(limit=5)
            print(f"✅ Получено {len(income)} записей доходов")

            # Тест получения информации об аккаунте
            account = await reporter.get_account_info()
            if account:
                print("✅ Информация об аккаунте получена")
            else:
                print("⚠️ Информация об аккаунте не получена")

            # Тестируем полный отчет
            print("\n📊 Генерация полного отчета...")
            summary, positions = await reporter.generate_position_report(hours=24)

            print("✅ Отчет сгенерирован:")
            print(f"   • Сделок: {summary.total_trades}")
            print(f"   • PnL: ${summary.total_pnl:.2f}")
            print(f"   • Винрейт: {summary.win_rate:.1%}")
            print(f"   • Чистый PnL: ${summary.net_pnl:.2f}")

            # Форматируем отчет
            report = reporter.format_position_report(summary, positions)
            print("\n📋 ФОРМАТИРОВАННЫЙ ОТЧЕТ:")
            print(report)

            # Тестируем группировку сделок
            print("\n🔍 Тестирование группировки сделок...")
            mock_trades = create_mock_trades()
            positions = reporter._group_trades_into_positions(mock_trades)
            print(f"✅ Создано {len(positions)} позиций из {len(mock_trades)} сделок")

            for i, pos in enumerate(positions, 1):
                print(f"   {i}. {pos.symbol} {pos.side.upper()}: ${pos.realized_pnl:.2f}")

            # Тестируем расчет сводки
            print("\n📊 Тестирование расчета сводки...")
            summary = reporter._calculate_position_summary(positions, funding_fees=0.03)
            print("✅ Сводка рассчитана:")
            print(f"   • Общий PnL: ${summary.total_pnl:.2f}")
            print(f"   • Винрейт: {summary.win_rate:.1%}")
            print(f"   • Чистый PnL: ${summary.net_pnl:.2f}")

            # Очистка
            await reporter.cleanup()
            print("\n✅ Тестирование завершено успешно")

    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()


async def test_dataclasses():
    """Тестирует dataclasses"""
    print("\n🧪 Тестирование dataclasses...")

    # Тест TradePosition
    position = TradePosition(
        symbol='BTCUSDT',
        side='buy',
        entry_price=45000.0,
        exit_price=45100.0,
        quantity=0.001,
        entry_time=datetime.now() - timedelta(hours=2),
        exit_time=datetime.now() - timedelta(hours=1),
        entry_order_id='12345',
        exit_order_id='12345',
        entry_fee=0.045,
        exit_fee=0.045,
        realized_pnl=0.055,
        hold_duration_minutes=60.0
    )

    print(f"✅ TradePosition создан: {position.symbol} {position.side}")
    print(f"   PnL: ${position.realized_pnl:.3f}")
    print(f"   Время удержания: {position.hold_duration_minutes:.1f} мин")

    # Тест PositionSummary
    summary = PositionSummary(
        total_trades=2,
        winning_trades=1,
        losing_trades=1,
        total_pnl=0.055,
        total_fees=0.09,
        win_rate=0.5,
        avg_profit_per_trade=0.055,
        avg_loss_per_trade=-0.01,
        max_profit=0.055,
        max_loss=-0.01,
        avg_hold_duration_minutes=60.0,
        best_symbol='BTCUSDT',
        worst_symbol='ETHUSDT',
        symbol_performance={'BTCUSDT': {'trades': 1, 'pnl': 0.055, 'fees': 0.09, 'win_rate': 1.0}},
        funding_fees=0.03,
        net_pnl=0.085
    )

    print("✅ PositionSummary создан:")
    print(f"   Сделок: {summary.total_trades}")
    print(f"   Винрейт: {summary.win_rate:.1%}")
    print(f"   Чистый PnL: ${summary.net_pnl:.3f}")


if __name__ == "__main__":
    asyncio.run(test_dataclasses())
    asyncio.run(test_position_history_mock())
