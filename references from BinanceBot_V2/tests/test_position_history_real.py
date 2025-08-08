#!/usr/bin/env python3
"""
Тестовый скрипт с реальными API ключами для Position History Reporter
"""

import asyncio
import os
import sys
from datetime import datetime

# Добавляем корневую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.config import TradingConfig
from core.position_history_reporter import PositionHistoryReporter
from core.unified_logger import UnifiedLogger


async def test_position_history_real():
    """Тестирует Position History Reporter с реальными API ключами"""
    try:
        print("🧪 Тестирование Position History Reporter с реальными API ключами...")

        # Загружаем конфигурацию с реальными ключами
        config = TradingConfig.load_optimized_for_profit_target(0.7)

        # Переопределяем API ключи на реальные
        config.api_key = "w2LwaYZq0x1t50ARb3IP69y9XQLssukr78dSnFcQF9XfbngkELA8hprvtTPAhX5S"
        config.api_secret = "hmG7FVUeyQ8wK09596iDJE8ipQqWvpdlRZ8obwAnCwOa8qlZyHyO9fTvr6oQvMFD"
        config.exchange_mode = "production"
        config.use_testnet = False

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
        print("📈 Получение сделок...")
        trades = await reporter.get_user_trades(limit=10)
        print(f"✅ Получено {len(trades)} сделок")

        if trades:
            print("📋 Примеры сделок:")
            for i, trade in enumerate(trades[:3], 1):
                print(f"   {i}. {trade['symbol']} {trade['side']} {trade['qty']} @ {trade['price']}")

        # Тест получения позиций
        print("\n📊 Получение позиций...")
        positions = await reporter.get_position_risk()
        print(f"✅ Получено {len(positions)} позиций")

        if positions:
            print("📋 Текущие позиции:")
            for pos in positions:
                print(f"   • {pos['symbol']}: {pos['positionAmt']} (PnL: {pos.get('unRealizedProfit', 'N/A')})")

        # Тест получения доходов
        print("\n💰 Получение доходов...")
        income = await reporter.get_income_history(limit=10)
        print(f"✅ Получено {len(income)} записей доходов")

        if income:
            print("📋 Примеры доходов:")
            for i, inc in enumerate(income[:3], 1):
                print(f"   {i}. {inc['symbol']} {inc['incomeType']}: {inc['income']}")

        # Тест получения информации об аккаунте
        print("\n🏦 Получение информации об аккаунте...")
        account = await reporter.get_account_info()
        if account:
            print("✅ Информация об аккаунте получена")
            print(f"   • Total Wallet Balance: {account.get('totalWalletBalance', 'N/A')}")
            print(f"   • Total Unrealized Profit: {account.get('totalUnrealizedProfit', 'N/A')}")
            print(f"   • Available Balance: {account.get('availableBalance', 'N/A')}")
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

        # Сохраняем отчет в файл
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = f"data/position_reports/position_report_real_{timestamp}.txt"

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("Real Position History Report\n")
            f.write(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("Range: 24 hours\n\n")
            f.write(report)

        print(f"📄 Отчет сохранен: {report_path}")

        # Очистка
        await reporter.cleanup()
        print("\n✅ Тестирование завершено успешно")

    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_position_history_real())
