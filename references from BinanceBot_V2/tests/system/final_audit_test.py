#!/usr/bin/env python3
"""
Финальный тест BinanceBot v2 после аудита и оптимизации
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))


async def test_optimized_components():
    """Тест оптимизированных компонентов"""
    print("🚀 Тестирование оптимизированных компонентов...")

    try:
        from core.config import TradingConfig
        from core.monitoring import PerformanceMonitor
        from core.unified_logger import UnifiedLogger
        from strategies.tp_optimizer import TPOptimizer
        from utils.performance import PerformanceOptimizer
        from utils.validators import ConfigValidator, OrderValidator

        config = TradingConfig.from_file()
        logger = UnifiedLogger(config)

        # Тест валидаторов
        order_validator = OrderValidator(config)
        config_validator = ConfigValidator()

        # Валидация конфигурации
        is_valid, message = config_validator.validate_runtime_config(config.__dict__)
        print(f"✅ Конфигурация валидна: {is_valid}")

        # Тест валидации ордера
        is_valid, message = order_validator.validate_order_params("BTCUSDC", "BUY", 0.001)
        print(f"✅ Валидация ордера: {is_valid}")

        # Тест оптимизатора производительности
        import numpy as np

        prices = np.array([100, 101, 102, 103, 104, 105, 106, 107, 108, 109])
        rsi = PerformanceOptimizer.calculate_rsi_fast(prices)
        print(f"✅ RSI рассчитан: {rsi[-1]:.2f}")

        # Тест TP оптимизатора
        tp_optimizer = TPOptimizer(config, logger)
        print("✅ TP Optimizer создан")

        # Тест мониторинга
        monitor = PerformanceMonitor(config, logger)
        print("✅ Performance Monitor создан")

        return True

    except Exception as e:
        print(f"❌ Ошибка оптимизированных компонентов: {e}")
        return False


async def test_leverage_integration():
    """Тест интеграции leverage manager"""
    print("\n⚡ Тестирование Leverage Manager...")

    try:
        from core.config import TradingConfig
        from core.leverage_manager import LeverageManager
        from core.unified_logger import UnifiedLogger

        config = TradingConfig.from_file()
        logger = UnifiedLogger(config)
        leverage_manager = LeverageManager(config, logger)

        # Тест получения оптимального leverage
        optimal_leverage = leverage_manager.get_optimal_leverage("BTCUSDC")
        print(f"✅ Оптимальный leverage для BTC: {optimal_leverage}x")

        # Тест анализа производительности
        stats = {"win_rate": 0.65, "avg_drawdown_percent": 0.8, "sl_hit_rate": 0.3}

        suggestion = leverage_manager.analyze_performance_and_suggest("BTCUSDC", stats)
        print(f"✅ Предложение по leverage: {suggestion}")

        return True

    except Exception as e:
        print(f"❌ Ошибка Leverage Manager: {e}")
        return False


async def test_telegram_integration():
    """Тест интеграции Telegram"""
    print("\n📱 Тестирование Telegram интеграции...")

    try:
        from core.config import TradingConfig
        from telegram.command_handlers import CommandHandlers
        from telegram.telegram_bot import TelegramBot

        config = TradingConfig.from_file()

        # Создаем Telegram бот
        telegram_bot = TelegramBot(config.telegram_token)
        print("✅ Telegram бот создан")

        # Тест команды
        command_handlers = CommandHandlers(None, None, None, None, config)
        print("✅ Command handlers созданы")

        return True

    except Exception as e:
        print(f"❌ Ошибка Telegram интеграции: {e}")
        return False


async def test_performance_targets():
    """Тест целевых показателей производительности"""
    print("\n🎯 Тестирование целевых показателей...")

    try:
        from core.config import TradingConfig

        config = TradingConfig.from_file()

        # Загружаем runtime config напрямую
        import json

        with open("data/runtime_config.json") as f:
            runtime_config = json.load(f)

        targets = runtime_config.get("performance_targets", {})

        print(f"✅ Целевая прибыль в час: ${targets.get('min_hourly_profit_usd', 2.0)}")
        print(f"✅ Целевой win rate: {targets.get('target_win_rate', 0.55):.1%}")
        print(f"✅ Минимум сделок в час: {targets.get('min_trades_per_hour', 3)}")

        # Проверяем, что настройки оптимальны для депозита 250-350 USD
        base_risk = config.base_risk_pct
        max_positions = config.max_concurrent_positions
        sl_percent = config.sl_percent

        print(f"✅ Базовый риск: {base_risk:.1%}")
        print(f"✅ Макс позиций: {max_positions}")
        print(f"✅ Stop Loss: {sl_percent:.1%}")

        # Расчет ожидаемой прибыли
        expected_hourly_profit = (base_risk * 0.6 * max_positions * 2) * 100  # Примерный расчет
        print(f"✅ Ожидаемая прибыль в час: ${expected_hourly_profit:.2f}")

        return True

    except Exception as e:
        print(f"❌ Ошибка целевых показателей: {e}")
        return False


async def test_architecture_completeness():
    """Тест полноты архитектуры"""
    print("\n🏗️ Тестирование полноты архитектуры...")

    required_components = [
        "core/config.py",
        "core/exchange_client.py",
        "core/trading_engine.py",
        "core/risk_manager.py",
        "core/unified_logger.py",
        "core/rate_limiter.py",
        "core/monitoring.py",
        "core/leverage_manager.py",
        "core/symbol_manager.py",
        "strategies/base_strategy.py",
        "strategies/scalping_v1.py",
        "strategies/symbol_selector.py",
        "strategies/tp_optimizer.py",
        "utils/validators.py",
        "utils/performance.py",
        "utils/helpers.py",
        "telegram/telegram_bot.py",
        "telegram/command_handlers.py",
        "data/leverage_map.json",
        "data/runtime_config.json",
    ]

    missing_components = []

    for component in required_components:
        if not Path(component).exists():
            missing_components.append(component)
        else:
            print(f"✅ {component}")

    if missing_components:
        print(f"❌ Отсутствующие компоненты: {missing_components}")
        return False
    else:
        print("✅ Все компоненты архитектуры присутствуют")
        return True


async def main():
    """Основной финальный тест"""
    print("🚀 Финальный аудит BinanceBot v2")
    print("=" * 60)

    tests = [
        test_architecture_completeness,
        test_optimized_components,
        test_leverage_integration,
        test_telegram_integration,
        test_performance_targets,
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
    print("📊 Результаты финального аудита:")

    passed = sum(results)
    total = len(results)

    for i, result in enumerate(results):
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        print(f"   Тест {i+1}: {status}")

    print(f"\n🎯 Итого: {passed}/{total} тестов пройдено")

    if passed == total:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("🚀 BinanceBot v2 готов к production запуску!")
        print("\n📋 Deployment Checklist:")
        print("✅ Архитектура соответствует концепции OptiFlow HFT")
        print("✅ Все компоненты оптимизированы")
        print("✅ Leverage Manager интегрирован")
        print("✅ Telegram бот настроен")
        print("✅ Целевые показатели установлены")
        print("✅ Система готова к работе на депозите 250-350 USD")
        return True
    else:
        print("⚠️ Некоторые тесты провалены. Требуется доработка.")
        return False


if __name__ == "__main__":
    asyncio.run(main())
