#!/usr/bin/env python3
"""
Простой тест для Position History Reporter
"""

import asyncio
import os
import sys

# Добавляем корневую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.config import TradingConfig
from core.position_history_reporter import PositionHistoryReporter
from core.unified_logger import UnifiedLogger


async def test_position_history():
    """Тестирует Position History Reporter"""
    try:
        print("🧪 Тестирование Position History Reporter...")

        # Загружаем конфигурацию
        config = TradingConfig.load_optimized_for_profit_target(0.7)
        logger = UnifiedLogger(config)

        # Создаем репортер
        reporter = PositionHistoryReporter(config, logger)

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

        # Очистка
        await reporter.cleanup()
        print("\n✅ Тестирование завершено успешно")

    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_position_history())
