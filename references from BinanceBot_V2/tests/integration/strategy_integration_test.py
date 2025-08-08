# strategy_integration_test.py

import asyncio
from unittest.mock import Mock

from core.config import TradingConfig
from core.exchange_client import ExchangeClient
from core.symbol_manager import SymbolManager
from core.unified_logger import UnifiedLogger
from strategies.strategy_manager import MarketRegimeDetector, StrategyManager


async def test_market_regime_detection():
    """Тест детекции режима рынка"""
    print("🧪 Testing Market Regime Detection...")

    # Мокаем компоненты
    config = TradingConfig.from_file()
    logger = UnifiedLogger(config)

    detector = MarketRegimeDetector(config, logger)

    # Тест трендового рынка
    trending_data = {"atr_percent": 0.015, "price_change_percent": 2.5, "volume_ratio": 1.5}
    regime = await detector.detect_regime("BTCUSDC", trending_data)
    assert regime == "trending", f"Expected trending, got {regime}"

    # Тест волатильного рынка
    volatile_data = {"atr_percent": 0.05, "price_change_percent": 1.0, "volume_ratio": 1.0}
    regime = await detector.detect_regime("BTCUSDC", volatile_data)
    assert regime == "volatile", f"Expected volatile, got {regime}"

    # Тест бокового рынка
    ranging_data = {"atr_percent": 0.01, "price_change_percent": 0.5, "volume_ratio": 1.0}
    regime = await detector.detect_regime("BTCUSDC", ranging_data)
    assert regime == "ranging", f"Expected ranging, got {regime}"

    print("✅ Market regime detection test passed")


async def test_strategy_selection():
    """Тест выбора стратегий"""
    print("🧪 Testing Strategy Selection...")

    # Мокаем компоненты
    config = TradingConfig.from_file()
    logger = UnifiedLogger(config)

    # Мокаем exchange и symbol_manager
    exchange = Mock()
    symbol_manager = Mock()

    strategy_manager = StrategyManager(config, exchange, symbol_manager, logger)

    # Тест выбора стратегии для трендового рынка
    trending_data = {"atr_percent": 0.015, "price_change_percent": 2.5, "volume_ratio": 1.5}

    strategy = await strategy_manager.get_optimal_strategy("BTCUSDC", trending_data)
    assert strategy is not None, "Strategy should not be None"

    print("✅ Strategy selection test passed")


async def test_hybrid_signal_generation():
    """Тест генерации гибридных сигналов"""
    print("🧪 Testing Hybrid Signal Generation...")

    # Мокаем компоненты
    config = TradingConfig.from_file()
    logger = UnifiedLogger(config)

    exchange = Mock()
    symbol_manager = Mock()

    strategy_manager = StrategyManager(config, exchange, symbol_manager, logger)

    # Мокаем рыночные данные
    market_data = {
        "atr_percent": 0.02,
        "price_change_percent": 1.0,
        "volume_ratio": 1.2,
        "last_price": 50000.0,
    }

    # Тест гибридного сигнала
    signal = await strategy_manager.get_hybrid_signal("BTCUSDC", market_data)
    # Сигнал может быть None если нет данных, это нормально
    print(f"Hybrid signal: {signal}")

    print("✅ Hybrid signal generation test passed")


async def test_strategy_performance_tracking():
    """Тест отслеживания производительности стратегий"""
    print("🧪 Testing Strategy Performance Tracking...")

    # Мокаем компоненты
    config = TradingConfig.from_file()
    logger = UnifiedLogger(config)

    exchange = Mock()
    symbol_manager = Mock()

    strategy_manager = StrategyManager(config, exchange, symbol_manager, logger)

    # Симулируем успешную сделку
    trade_result = {"win": True, "pnl": 0.02}

    await strategy_manager.update_strategy_performance("scalping", trade_result)

    # Проверяем обновление статистики
    status = await strategy_manager.get_strategy_status()
    assert "scalping" in status["performance"], "Scalping performance should be tracked"

    print("✅ Strategy performance tracking test passed")


async def test_force_strategy_switch():
    """Тест принудительного переключения стратегий"""
    print("🧪 Testing Force Strategy Switch...")

    # Мокаем компоненты
    config = TradingConfig.from_file()
    logger = UnifiedLogger(config)

    exchange = Mock()
    symbol_manager = Mock()

    strategy_manager = StrategyManager(config, exchange, symbol_manager, logger)

    # Тест переключения на существующую стратегию
    result = await strategy_manager.force_strategy_switch("BTCUSDC", "scalping")
    assert result, "Strategy switch should succeed"

    # Тест переключения на несуществующую стратегию
    result = await strategy_manager.force_strategy_switch("BTCUSDC", "nonexistent")
    assert not result, "Strategy switch should fail for nonexistent strategy"

    print("✅ Force strategy switch test passed")


async def test_strategy_manager_integration():
    """Интеграционный тест StrategyManager"""
    print("🧪 Testing Strategy Manager Integration...")

    # Загружаем конфигурацию
    config = TradingConfig.from_file()
    logger = UnifiedLogger(config)

    # Инициализируем exchange client
    exchange = ExchangeClient(config, logger=logger)

    # Инициализируем symbol manager
    symbol_manager = SymbolManager(exchange, logger=logger)

    # Создаем StrategyManager
    strategy_manager = StrategyManager(config, exchange, symbol_manager, logger)

    # Проверяем инициализацию
    assert len(strategy_manager.strategies) == 2, "Should have 2 strategies"
    assert "scalping" in strategy_manager.strategies, "Should have scalping strategy"
    assert "tp_optimizer" in strategy_manager.strategies, "Should have tp_optimizer strategy"

    # Проверяем статус
    status = await strategy_manager.get_strategy_status()
    assert status["total_strategies"] == 2, "Should report 2 total strategies"

    print("✅ Strategy Manager integration test passed")


async def main():
    """Основная функция тестирования"""
    print("🚀 Starting Strategy Integration Tests...\n")

    try:
        await test_market_regime_detection()
        await test_strategy_selection()
        await test_hybrid_signal_generation()
        await test_strategy_performance_tracking()
        await test_force_strategy_switch()
        await test_strategy_manager_integration()

        print("\n🎉 All strategy integration tests passed!")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
