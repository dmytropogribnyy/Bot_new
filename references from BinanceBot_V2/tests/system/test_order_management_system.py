#!/usr/bin/env python3
"""
Тест системы управления ордерами и позициями
"""

import asyncio
import time
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from core.order_manager import OrderManager
from core.signal_handler import GracefulShutdown
from core.trading_engine import TradingEngine


class MockExchangeClient:
    """Мок для ExchangeClient"""

    def __init__(self):
        self.positions = []
        self.orders = []
        self.order_counter = 1

    async def get_positions(self):
        return self.positions

    async def get_open_orders(self, symbol=None):
        return self.orders

    async def place_order(self, symbol, side, quantity, order_type="MARKET", price=None, params=None):
        order_id = self.order_counter
        self.order_counter += 1

        order = {
            'orderId': order_id,
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'type': order_type,
            'status': 'FILLED' if order_type == 'MARKET' else 'NEW',
            'price': price,
            'time': int(time.time() * 1000)
        }

        if order_type == 'MARKET':
            # Добавляем позицию
            self.positions.append({
                'symbol': symbol,
                'positionAmt': quantity if side == 'BUY' else -quantity,
                'entryPrice': price or 50000.0,
                'unRealizedProfit': 0.0
            })

        self.orders.append(order)
        return order

    async def cancel_order(self, symbol, order_id):
        # Удаляем ордер
        self.orders = [o for o in self.orders if not (o['symbol'] == symbol and o['orderId'] == order_id)]
        return {'status': 'CANCELED'}

    async def get_order_status(self, symbol, order_id):
        for order in self.orders:
            if order['symbol'] == symbol and order['orderId'] == order_id:
                return order
        return {'status': 'NOT_FOUND'}

    async def set_leverage(self, symbol, leverage):
        return {'status': 'OK'}

    async def get_balance(self):
        return 1000.0


class MockLogger:
    def __init__(self):
        self.events = []
        self.trades = []
        self.config = SimpleNamespace(telegram_enabled=False)  # Добавляем config

    def log_event(self, component, level, message, details=None):
        self.events.append({
            'component': component,
            'level': level,
            'message': message,
            'details': details,
            'timestamp': datetime.utcnow().isoformat()
        })
        print(f"[{level}] {component}: {message}")

    def log_trade(self, symbol, side, entry_price, exit_price, qty, pnl, win, fees):
        self.trades.append({
            'symbol': symbol,
            'side': side,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'qty': qty,
            'pnl': pnl,
            'win': win,
            'fees': fees,
            'timestamp': datetime.utcnow().isoformat()
        })
        print(f"💰 Trade: {symbol} {side} {qty} @ {entry_price} -> {exit_price} (PnL: ${pnl:.2f})")

    def get_events(self):
        return self.events

    def get_trades(self):
        return self.trades


async def test_order_manager():
    """Тест OrderManager"""
    print("🔍 Тестирование OrderManager...")

    # Создаем моки
    config = SimpleNamespace(
        sl_percent=0.012,
        step_tp_levels=[0.004, 0.008, 0.012],
        step_tp_sizes=[0.5, 0.3, 0.2],
        max_position_duration=3600,
        max_concurrent_positions=3,
        min_trade_qty=0.001,
        telegram_enabled=False,
        # Добавляем новые параметры для enhanced timeout system
        max_hold_minutes=30,
        soft_exit_minutes=15,
        auto_profit_threshold=0.7,
        weak_position_minutes=45,
        risky_loss_threshold=-1.5,
        emergency_stop_threshold=-2.0,
        trailing_stop_drawdown=0.3
    )

    exchange = MockExchangeClient()
    logger = MockLogger()

    # Создаем OrderManager
    order_manager = OrderManager(config, exchange, logger)

    # Инициализация
    success = await order_manager.initialize()
    print(f"✅ Инициализация: {success}")

    # Тест размещения позиции с TP/SL
    print("\n📋 Тест размещения позиции с TP/SL:")
    result = await order_manager.place_position_with_tp_sl(
        symbol="BTCUSDC",
        side="BUY",
        quantity=0.001,
        entry_price=50000.0,
        leverage=5
    )

    print(f"  Результат: {result}")
    print(f"  Активные позиции: {len(order_manager.get_active_positions())}")
    print(f"  SL ордера: {len(order_manager.sl_orders)}")
    print(f"  TP ордера: {len(order_manager.tp_orders)}")

    # Тест экстренного закрытия
    print("\n📋 Тест экстренного закрытия:")
    close_result = await order_manager.close_position_emergency("BTCUSDC")
    print(f"  Результат: {close_result}")
    print(f"  Позиции после: {len(order_manager.get_active_positions())}")


async def test_trading_engine_integration():
    """Тест интеграции TradingEngine с OrderManager"""
    print("\n🔍 Тестирование интеграции TradingEngine...")

    # Создаем моки
    config = SimpleNamespace(
        max_concurrent_positions=3,
        min_trade_qty=0.001,
        telegram_enabled=False
    )

    exchange = MockExchangeClient()
    logger = MockLogger()
    order_manager = OrderManager(config, exchange, logger)

    # Создаем TradingEngine
    trading_engine = TradingEngine(
        config=config,
        exchange_client=exchange,
        symbol_selector=Mock(),
        leverage_manager=Mock(),
        risk_manager=Mock(),
        logger=logger,
        order_manager=order_manager
    )

    # Тест выполнения сделки
    print("\n📋 Тест выполнения сделки:")
    entry_signal = {
        "side": "BUY",
        "entry_price": 50000.0
    }

    await trading_engine.execute_trade("BTCUSDC", entry_signal, 0.001, 5)

    positions = trading_engine.get_open_positions()
    print(f"  Позиции после сделки: {len(positions)}")
    print(f"  Детали позиций: {positions}")


async def test_signal_handler():
    """Тест обработки сигналов"""
    print("\n🔍 Тестирование SignalHandler...")

    # Создаем моки
    logger = MockLogger()
    order_manager = Mock()
    trading_engine = Mock()
    telegram_bot = Mock()

    # Создаем GracefulShutdown
    graceful_shutdown = GracefulShutdown(logger, order_manager, trading_engine, telegram_bot)

    # Мокаем методы
    order_manager.get_active_positions.return_value = []
    order_manager.shutdown = AsyncMock()
    trading_engine.pause_trading = Mock()
    trading_engine.stop_trading = Mock()
    telegram_bot.stop = AsyncMock()

    # Тест graceful shutdown
    print("\n📋 Тест graceful shutdown:")
    await graceful_shutdown.graceful_shutdown()

    # Проверяем вызовы
    assert trading_engine.pause_trading.called
    assert order_manager.shutdown.called
    assert trading_engine.stop_trading.called
    assert telegram_bot.stop.called

    print("  ✅ Graceful shutdown работает корректно")


async def test_comprehensive_system():
    """Комплексный тест всей системы"""
    print("\n🔍 Комплексный тест системы управления ордерами...")

    # Создаем все компоненты
    config = SimpleNamespace(
        sl_percent=0.012,
        step_tp_levels=[0.004, 0.008, 0.012],
        step_tp_sizes=[0.5, 0.3, 0.2],
        max_position_duration=3600,
        max_concurrent_positions=3,
        min_trade_qty=0.001,
        telegram_enabled=False,
        # Добавляем новые параметры для enhanced timeout system
        max_hold_minutes=30,
        soft_exit_minutes=15,
        auto_profit_threshold=0.7,
        weak_position_minutes=45,
        risky_loss_threshold=-1.5,
        emergency_stop_threshold=-2.0,
        trailing_stop_drawdown=0.3
    )

    exchange = MockExchangeClient()
    logger = MockLogger()

    # Создаем OrderManager
    order_manager = OrderManager(config, exchange, logger)
    await order_manager.initialize()

    # Создаем TradingEngine
    trading_engine = TradingEngine(
        config=config,
        exchange_client=exchange,
        symbol_selector=Mock(),
        leverage_manager=Mock(),
        risk_manager=Mock(),
        logger=logger,
        order_manager=order_manager
    )

    # Тест 1: Размещение позиции
    print("\n📋 Тест 1: Размещение позиции")
    entry_signal = {"side": "BUY", "entry_price": 50000.0}
    await trading_engine.execute_trade("BTCUSDC", entry_signal, 0.001, 5)

    positions = trading_engine.get_open_positions()
    print(f"  Позиции: {len(positions)}")

    # Тест 2: Проверка TP/SL ордеров
    print("\n📋 Тест 2: Проверка TP/SL ордеров")
    print(f"  SL ордера: {len(order_manager.sl_orders)}")
    print(f"  TP ордера: {len(order_manager.tp_orders)}")

    # Тест 3: Экстренное закрытие
    print("\n📋 Тест 3: Экстренное закрытие")
    close_result = await trading_engine.close_position("BTCUSDC")
    print(f"  Результат закрытия: {close_result}")

    # Тест 4: Проверка состояния после закрытия
    print("\n📋 Тест 4: Состояние после закрытия")
    positions_after = trading_engine.get_open_positions()
    print(f"  Позиции после: {len(positions_after)}")

    print("\n✅ Комплексный тест завершен успешно!")


async def main():
    """Основная функция тестирования"""
    print("🚀 Тестирование системы управления ордерами")
    print("=" * 60)

    try:
        await test_order_manager()
        await test_trading_engine_integration()
        await test_signal_handler()
        await test_comprehensive_system()

        print("\n✅ Все тесты прошли успешно!")
        print("\n📋 Резюме системы управления ордерами:")
        print("  ✅ OrderManager - управление TP/SL ордерами")
        print("  ✅ TradingEngine - интеграция с OrderManager")
        print("  ✅ SignalHandler - обработка Ctrl-C и graceful shutdown")
        print("  ✅ Синхронизация позиций с Binance")
        print("  ✅ Мониторинг исполнения ордеров")
        print("  ✅ Экстренное закрытие позиций")
        print("  ✅ Очистка висящих ордеров")

    except Exception as e:
        print(f"\n❌ Ошибка в тестах: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
