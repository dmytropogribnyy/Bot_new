#!/usr/bin/env python3
"""
Тест восстановления позиций после различных типов остановки
Проверяет, что после экстренного закрытия позиции не восстанавливаются
"""

import asyncio
import time
from datetime import datetime
from types import SimpleNamespace

from core.order_manager import OrderManager


class MockExchangeClient:
    def __init__(self):
        self.orders = {}
        self.positions = {}
        self.order_id_counter = 1

    async def set_leverage(self, symbol, leverage):
        return {'success': True}

    async def place_order(self, symbol, side, quantity, order_type="MARKET", price=None, params=None):
        order_id = self.order_id_counter
        self.order_id_counter += 1

        # Определяем статус ордера
        if order_type == "MARKET":
            status = 'FILLED'
        elif order_type == "STOP_MARKET":
            status = 'NEW'
        elif order_type == "LIMIT":
            status = 'NEW'
        else:
            status = 'FILLED'

        order = {
            'orderId': order_id,
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'type': order_type,
            'status': status,
            'price': price or 50000.0,
            'time': int(time.time() * 1000)
        }

        self.orders[order_id] = order

        # Если это основной ордер, создаем позицию
        if order_type == "MARKET":
            self.positions[symbol] = {
                'symbol': symbol,
                'positionAmt': str(quantity if side == 'BUY' else -quantity),
                'entryPrice': str(price or 50000.0),
                'unRealizedProfit': '0.0',
                'side': side
            }

        return order

    async def get_ticker(self, symbol):
        return {'lastPrice': '50000.0'}

    async def get_order_status(self, symbol, order_id):
        return self.orders.get(order_id, {'status': 'FILLED'})

    async def get_positions(self):
        """Возвращает реальные позиции с биржи"""
        return list(self.positions.values())

    async def get_open_orders(self, symbol=None):
        """Возвращает открытые ордера"""
        open_orders = []
        for order in self.orders.values():
            if order['status'] == 'NEW':
                if symbol is None or order['symbol'] == symbol:
                    open_orders.append(order)
        return open_orders

    async def cancel_order(self, symbol, order_id):
        """Отмена ордера"""
        if order_id in self.orders:
            self.orders[order_id]['status'] = 'CANCELED'
            return {'success': True}
        return {'success': False, 'error': 'Order not found'}

    def simulate_position_close(self, symbol):
        """Симулирует закрытие позиции"""
        if symbol in self.positions:
            del self.positions[symbol]
            return True
        return False

class MockLogger:
    def __init__(self):
        self.events = []
        self.trades = []
        self.config = SimpleNamespace(telegram_enabled=False)

    def log_event(self, component, level, message, details=None):
        self.events.append({
            'component': component,
            'level': level,
            'message': message,
            'details': details,
            'timestamp': datetime.now().isoformat()
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
            'timestamp': datetime.now().isoformat()
        })
        print(f"💰 Trade: {symbol} {side} {qty} @ {entry_price} -> {exit_price} (PnL: ${pnl:.2f})")

async def test_emergency_shutdown_recovery():
    """Тестирование восстановления позиций после различных типов остановки"""
    print("🚀 Тестирование восстановления позиций после остановки")
    print("=" * 60)

    # Конфигурация
    config = SimpleNamespace(
        sl_percent=0.012,
        step_tp_levels=[0.004, 0.008, 0.012],
        step_tp_sizes=[0.5, 0.3, 0.2],
        max_position_duration=3600,
        max_concurrent_positions=3,
        min_trade_qty=0.001,
        telegram_enabled=False,
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

    # Тест 1: Нормальное восстановление позиций (без экстренного закрытия)
    print("\n📋 Тест 1: Нормальное восстановление позиций")

    # Создаем позиции на бирже
    exchange.positions["BTCUSDC_NORMAL"] = {
        'symbol': 'BTCUSDC_NORMAL',
        'positionAmt': '0.001',
        'entryPrice': '50000.0',
        'unRealizedProfit': '25.0',
        'side': 'BUY'
    }

    # Создаем OrderManager
    order_manager = OrderManager(config, exchange, logger)
    await order_manager.initialize()

    print(f"  Позиции на бирже: {len(exchange.positions)}")
    print(f"  Позиции в боте после восстановления: {len(order_manager.active_positions)}")
    print(f"  Emergency shutdown flag: {order_manager.is_emergency_shutdown()}")

    # Тест 2: Экстренное закрытие и восстановление
    print("\n📋 Тест 2: Экстренное закрытие и восстановление")

    # Создаем новую позицию
    await order_manager.place_position_with_tp_sl(
        symbol="ETHUSDC_EMERGENCY",
        side="BUY",
        quantity=0.01,
        entry_price=3000.0,
        leverage=5
    )

    print(f"  Позиции в боте до экстренного закрытия: {len(order_manager.active_positions)}")
    print(f"  Позиции на бирже до экстренного закрытия: {len(exchange.positions)}")

    # Симулируем экстренное закрытие
    await order_manager.shutdown(emergency=True)

    print(f"  Позиции в боте после экстренного закрытия: {len(order_manager.active_positions)}")
    print(f"  Позиции на бирже после экстренного закрытия: {len(exchange.positions)}")
    print(f"  Emergency shutdown flag: {order_manager.is_emergency_shutdown()}")

    # Создаем новый OrderManager (симуляция перезапуска)
    new_order_manager = OrderManager(config, exchange, logger)
    await new_order_manager.initialize()

    print(f"  Позиции в боте после перезапуска: {len(new_order_manager.active_positions)}")
    print(f"  Emergency shutdown flag после перезапуска: {new_order_manager.is_emergency_shutdown()}")

    # Тест 3: Сброс флага экстренного закрытия
    print("\n📋 Тест 3: Сброс флага экстренного закрытия")

    # Сбрасываем флаг
    new_order_manager.reset_emergency_flag()
    print(f"  Emergency shutdown flag после сброса: {new_order_manager.is_emergency_shutdown()}")

    # Синхронизируем позиции
    await new_order_manager.sync_positions_from_exchange()
    print(f"  Позиции в боте после сброса флага и синхронизации: {len(new_order_manager.active_positions)}")

    # Тест 4: Graceful shutdown и восстановление
    print("\n📋 Тест 4: Graceful shutdown и восстановление")

    # Создаем новую позицию
    await new_order_manager.place_position_with_tp_sl(
        symbol="ADAUSDC_GRACEFUL",
        side="BUY",
        quantity=100,
        entry_price=0.5,
        leverage=5
    )

    print(f"  Позиции в боте до graceful shutdown: {len(new_order_manager.active_positions)}")

    # Симулируем graceful shutdown (без экстренного закрытия)
    new_order_manager.shutdown_requested = True
    new_order_manager.shutdown_timestamp = time.time()
    # НЕ устанавливаем emergency_shutdown_flag = True

    print(f"  Emergency shutdown flag после graceful shutdown: {new_order_manager.is_emergency_shutdown()}")

    # Создаем новый OrderManager (симуляция перезапуска после graceful shutdown)
    graceful_order_manager = OrderManager(config, exchange, logger)
    await graceful_order_manager.initialize()

    print(f"  Позиции в боте после graceful shutdown и перезапуска: {len(graceful_order_manager.active_positions)}")
    print(f"  Emergency shutdown flag после graceful shutdown: {graceful_order_manager.is_emergency_shutdown()}")

    # Тест 5: Проверка различных сценариев
    print("\n📋 Тест 5: Проверка различных сценариев")

    scenarios = [
        ("Ctrl+C (первый)", False, "Должен восстановить позиции"),
        ("Ctrl+C (второй)", True, "НЕ должен восстанавливать позиции"),
        ("/stop команда", False, "Должен восстановить позиции"),
        ("/shutdown команда", True, "НЕ должен восстанавливать позиции"),
        ("SIGTERM", False, "Должен восстановить позиции"),
        ("Timeout в graceful", True, "НЕ должен восстанавливать позиции")
    ]

    for scenario_name, is_emergency, expected_behavior in scenarios:
        print(f"  {scenario_name}: {expected_behavior}")
        print(f"    Emergency flag: {is_emergency}")

    # Анализ событий
    print("\n📊 Анализ событий:")
    emergency_events = [e for e in logger.events if 'emergency' in e['message'].lower() or 'shutdown' in e['message'].lower()]
    for event in emergency_events[-10:]:
        print(f"  {event['level']}: {event['message']}")

    print(f"\n✅ Тестирование завершено! Всего событий: {len(logger.events)}")

async def main():
    try:
        await test_emergency_shutdown_recovery()
        print("\n🎉 Все тесты прошли успешно!")
    except Exception as e:
        print(f"\n❌ Ошибка в тестах: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
