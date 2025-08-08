#!/usr/bin/env python3
"""
Тестовый скрипт для проверки Position History Reporter
Позволяет получить сводку позиций из Binance API
"""

import asyncio
import os
import sys
from datetime import datetime

# Добавляем корневую директорию в путь
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import TradingConfig
from core.position_history_reporter import PositionHistoryReporter
from core.unified_logger import UnifiedLogger


async def test_position_report(hours: int = 24):
    """Тестирует получение сводки позиций"""
    try:
        print(f"🧪 Тестирование Position History Reporter для последних {hours} часов...")

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

        # Получаем сводку позиций
        print("📊 Получение сводки позиций...")
        summary, positions = await reporter.generate_position_report(hours)

        # Форматируем отчет
        report = reporter.format_position_report(summary, positions)

        # Выводим результат
        print("\n" + "="*80)
        print("📋 РЕЗУЛЬТАТ ТЕСТИРОВАНИЯ")
        print("="*80)
        print(report)

        # Дополнительная информация
        print("\n🔍 ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ:")
        print(f"• Временной диапазон: {hours} часов")
        print(f"• Количество позиций: {len(positions)}")
        print(f"• Общий PnL: ${summary.total_pnl:.2f}")
        print(f"• Чистый PnL (с funding fees): ${summary.net_pnl:.2f}")
        print(f"• Винрейт: {summary.win_rate:.1%}")

        # Сохраняем отчет в файл
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = f"data/position_reports/position_report_test_{timestamp}.txt"

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("Тест Position History Reporter\n")
            f.write(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Диапазон: {hours} часов\n\n")
            f.write(report)

        print(f"📄 Отчет сохранен: {report_path}")

        # Очистка
        await reporter.cleanup()
        print("✅ Тестирование завершено")

    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()


async def test_individual_apis():
    """Тестирует отдельные API вызовы"""
    try:
        print("🔧 Тестирование отдельных API вызовов...")

        config = TradingConfig.load_optimized_for_profit_target(0.7)
        logger = UnifiedLogger(config)
        reporter = PositionHistoryReporter(config, logger)

        await reporter.initialize()

        # Тест получения сделок
        print("📈 Тест получения сделок...")
        trades = await reporter.get_user_trades(limit=10)
        print(f"✅ Получено {len(trades)} сделок")

        # Тест получения позиций
        print("📊 Тест получения позиций...")
        positions = await reporter.get_position_risk()
        print(f"✅ Получено {len(positions)} позиций")

        # Тест получения доходов
        print("💰 Тест получения доходов...")
        income = await reporter.get_income_history(limit=10)
        print(f"✅ Получено {len(income)} записей доходов")

        # Тест получения информации об аккаунте
        print("🏦 Тест получения информации об аккаунте...")
        account = await reporter.get_account_info()
        if account:
            print("✅ Информация об аккаунте получена")
        else:
            print("⚠️ Информация об аккаунте не получена")

        await reporter.cleanup()
        print("✅ Тестирование API завершено")

    except Exception as e:
        print(f"❌ Ошибка при тестировании API: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Основная функция"""
    import argparse

    parser = argparse.ArgumentParser(description="Тестирование Position History Reporter")
    parser.add_argument("--hours", type=int, default=24, help="Количество часов для анализа")
    parser.add_argument("--api-only", action="store_true", help="Только тестирование API")

    args = parser.parse_args()

    if args.api_only:
        asyncio.run(test_individual_apis())
    else:
        asyncio.run(test_position_report(args.hours))


if __name__ == "__main__":
    main()
