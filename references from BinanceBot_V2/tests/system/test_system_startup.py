#!/usr/bin/env python3
"""
Тест запуска системы - проверяет инициализацию всех компонентов
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent))

from core.config import TradingConfig
from core.exchange_client import ExchangeClient
from core.leverage_manager import LeverageManager
from core.post_run_analyzer import PostRunAnalyzer
from core.risk_manager import RiskManager
from core.symbol_manager import SymbolManager
from core.unified_logger import UnifiedLogger
from core.websocket_manager import WebSocketManager
from strategies.strategy_manager import StrategyManager
from strategies.symbol_selector import SymbolSelector


async def test_system_startup():
    """Тест инициализации всех компонентов системы"""
    print("🚀 Тестирование запуска системы...")
    print("=" * 50)

    try:
        # 1. Загрузка конфигурации
        print("📋 1. Загрузка конфигурации...")
        config = TradingConfig.from_file("data/runtime_config.json")
        print("✅ Конфигурация загружена успешно")

        # 2. Инициализация логгера
        print("📝 2. Инициализация логгера...")
        logger = UnifiedLogger(config)
        print("✅ Логгер инициализирован успешно")

        # 3. Инициализация клиента биржи
        print("🏦 3. Инициализация клиента биржи...")
        exchange = ExchangeClient(config, logger=logger)
        print("✅ Клиент биржи инициализирован успешно")

        # 4. Инициализация менеджера символов
        print("📊 4. Инициализация менеджера символов...")
        symbol_manager = SymbolManager(exchange, logger=logger)
        print("✅ Менеджер символов инициализирован успешно")

        # 5. Инициализация WebSocket менеджера
        print("🔌 5. Инициализация WebSocket менеджера...")
        ws_manager = WebSocketManager(exchange)
        print("✅ WebSocket менеджер инициализирован успешно")

        # 6. Инициализация менеджера кредитного плеча
        print("⚖️ 6. Инициализация менеджера кредитного плеча...")
        leverage_manager = LeverageManager(config, logger)
        print("✅ Менеджер кредитного плеча инициализирован успешно")

        # 7. Инициализация менеджера рисков
        print("🛡️ 7. Инициализация менеджера рисков...")
        risk_manager = RiskManager(config, logger)
        print("✅ Менеджер рисков инициализирован успешно")

        # 8. Инициализация селектора символов
        print("🎯 8. Инициализация селектора символов...")
        symbol_selector = SymbolSelector(config, symbol_manager, exchange, logger)
        print("✅ Селектор символов инициализирован успешно")

        # 9. Инициализация менеджера стратегий
        print("🧠 9. Инициализация менеджера стратегий...")
        strategy_manager = StrategyManager(config, exchange, symbol_manager, logger)
        print("✅ Менеджер стратегий инициализирован успешно")

        # 10. Инициализация анализатора после запуска
        print("📈 10. Инициализация анализатора после запуска...")
        post_run_analyzer = PostRunAnalyzer(logger, config)
        print("✅ Анализатор после запуска инициализирован успешно")

        print("\n" + "=" * 50)
        print("🎉 ВСЕ КОМПОНЕНТЫ ИНИЦИАЛИЗИРОВАНЫ УСПЕШНО!")
        print("✅ Система готова к запуску")
        print("=" * 50)

        # Тест логирования
        print("\n📝 Тест логирования:")
        logger.log_event("TEST", "INFO", "Тест системы запуска")
        logger.log_trade("BTCUSDC", "BUY", 0.001, 50000, "TEST", 10.0, True)

        return True

    except Exception as e:
        print(f"\n❌ Ошибка инициализации: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Основная функция тестирования"""
    success = await test_system_startup()

    if success:
        print("\n🚀 СИСТЕМА ГОТОВА К ПРОДАКШЕНУ!")
        print("\n💡 Для запуска полной системы используйте:")
        print("   python main.py")
    else:
        print("\n⚠️ Требуется исправление ошибок")


if __name__ == "__main__":
    asyncio.run(main())
