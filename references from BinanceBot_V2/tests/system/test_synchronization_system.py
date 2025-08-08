#!/usr/bin/env python3
"""
Тест системы синхронизации позиций и ордеров
Проверяет корректность синхронизации между ботом и Binance
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
        self.position_id_counter = 1

    async def set_leverage(self, symbol, leverage):
        return {'success': True}

    async def place_order(self, symbol, side, quantity, order_type="MARKET", price=None, params=None):
        order_id = self.order_id_counter
        self.order_id_counter += 1

        # Определяем статус ордера
        if order_type == "MARKET":
            status = 'FILLED'
        elif order_type == "STOP_MARKET":
            status = 'NEW'  # SL ордера остаются активными
        elif order_type == "LIMIT":
            status = 'NEW'  # TP ордера остаются активными
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

    def simulate_order_execution(self, order_id, new_status='FILLED'):
        """Симулирует исполнение ордера"""
        if order_id in self.orders:
            self.orders[order_id]['status'] = new_status
            return True
        return False

    def simulate_position_change(self, symbol, new_size=None, new_pnl=None):
        """Симулирует изменение позиции"""
        if symbol in self.positions:
            if new_size is not None:
                self.positions[symbol]['positionAmt'] = str(new_size)
            if new_pnl is not None:
                self.positions[symbol]['unRealizedProfit'] = str(new_pnl)
            return True
        return False

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

async def test_synchronization_scenarios():
    """Тестирование различных сценариев синхронизации"""
    print("🚀 Тестирование системы синхронизации позиций и ордеров")
    print("=" * 70)

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

    order_manager = OrderManager(config, exchange, logger)
    await order_manager.initialize()

    # Тест 1: Синхронизация при открытии позиции
    print("\n📋 Тест 1: Синхронизация при открытии позиции")

    # Открываем позицию
    result = await order_manager.place_position_with_tp_sl(
        symbol="BTCUSDC_SYNC",
        side="BUY",
        quantity=0.001,
        entry_price=50000.0,
        leverage=5
    )

    print(f"  Позиция открыта: {result['success']}")
    print(f"  Позиции в боте: {len(order_manager.active_positions)}")
    print(f"  Позиции на бирже: {len(exchange.positions)}")

    # Проверяем синхронизацию
    await order_manager.sync_positions_from_exchange()
    print(f"  После синхронизации позиции в боте: {len(order_manager.active_positions)}")

    # Тест 2: Синхронизация при исполнении TP ордера
    print("\n📋 Тест 2: Синхронизация при исполнении TP ордера")

    # Симулируем исполнение TP ордера
    if "BTCUSDC_SYNC" in order_manager.tp_orders:
        tp_order = order_manager.tp_orders["BTCUSDC_SYNC"][0]
        print(f"  TP ордер до исполнения: {tp_order}")
        print(f"  Позиции в боте до исполнения: {len(order_manager.active_positions)}")

        exchange.simulate_order_execution(tp_order['order_id'])

        # Проверяем исполнение
        await order_manager.check_order_executions()

        print(f"  TP ордер исполнен: {tp_order['order_id']}")
        print(f"  Позиции в боте после исполнения: {len(order_manager.active_positions)}")
        print(f"  Позиции на бирже: {len(exchange.positions)}")

    # Тест 3: Синхронизация при исполнении SL ордера
    print("\n📋 Тест 3: Синхронизация при исполнении SL ордера")

    # Открываем новую позицию для теста SL
    await order_manager.place_position_with_tp_sl(
        symbol="ETHUSDC_SL",
        side="SELL",
        quantity=0.01,
        entry_price=3000.0,
        leverage=5
    )

    # Симулируем исполнение SL ордера
    if "ETHUSDC_SL" in order_manager.sl_orders:
        sl_order = order_manager.sl_orders["ETHUSDC_SL"]
        print(f"  SL ордер до исполнения: {sl_order}")
        print(f"  Позиции в боте до исполнения: {len(order_manager.active_positions)}")

        exchange.simulate_order_execution(sl_order['order_id'])

        # Проверяем исполнение
        await order_manager.check_order_executions()

        print(f"  SL ордер исполнен: {sl_order['order_id']}")
        print(f"  Позиции в боте после исполнения: {len(order_manager.active_positions)}")
        print(f"  Позиции на бирже: {len(exchange.positions)}")

    # Тест 4: Синхронизация при изменении позиции на бирже
    print("\n📋 Тест 4: Синхронизация при изменении позиции на бирже")

    # Открываем позицию
    await order_manager.place_position_with_tp_sl(
        symbol="ADAUSDC_CHANGE",
        side="BUY",
        quantity=100,
        entry_price=0.5,
        leverage=5
    )

    print(f"  До изменения - позиции в боте: {len(order_manager.active_positions)}")
    print(f"  До изменения - позиции на бирже: {len(exchange.positions)}")
    print(f"  Позиция ADAUSDC_CHANGE в боте: {order_manager.active_positions.get('ADAUSDC_CHANGE', 'НЕ НАЙДЕНА')}")

    # Симулируем изменение позиции на бирже (например, частичное закрытие)
    exchange.simulate_position_change("ADAUSDC_CHANGE", new_size=50, new_pnl=25.0)

    # Синхронизируем
    await order_manager.sync_positions_from_exchange()

    print(f"  После изменения - позиции в боте: {len(order_manager.active_positions)}")
    print(f"  После изменения - позиции на бирже: {len(exchange.positions)}")
    print(f"  Позиция ADAUSDC_CHANGE в боте после синхронизации: {order_manager.active_positions.get('ADAUSDC_CHANGE', 'НЕ НАЙДЕНА')}")

    # Тест 5: Синхронизация при закрытии позиции на бирже
    print("\n📋 Тест 5: Синхронизация при закрытии позиции на бирже")

    # Открываем позицию
    await order_manager.place_position_with_tp_sl(
        symbol="DOTUSDC_CLOSE",
        side="BUY",
        quantity=10,
        entry_price=7.0,
        leverage=5
    )

    print(f"  До закрытия - позиции в боте: {len(order_manager.active_positions)}")
    print(f"  До закрытия - позиции на бирже: {len(exchange.positions)}")
    print(f"  Позиция DOTUSDC_CLOSE в боте: {'НАЙДЕНА' if 'DOTUSDC_CLOSE' in order_manager.active_positions else 'НЕ НАЙДЕНА'}")

    # Симулируем закрытие позиции на бирже
    exchange.simulate_position_close("DOTUSDC_CLOSE")

    # Синхронизируем
    await order_manager.sync_positions_from_exchange()

    print(f"  После закрытия - позиции в боте: {len(order_manager.active_positions)}")
    print(f"  После закрытия - позиции на бирже: {len(exchange.positions)}")
    print(f"  Позиция DOTUSDC_CLOSE в боте после синхронизации: {'НАЙДЕНА' if 'DOTUSDC_CLOSE' in order_manager.active_positions else 'НЕ НАЙДЕНА'}")

    # Тест 6: Восстановление после сбоя
    print("\n📋 Тест 6: Восстановление после сбоя")

    # Симулируем существующие позиции на бирже
    exchange.positions["BTCUSDC_RECOVERY"] = {
        'symbol': 'BTCUSDC_RECOVERY',
        'positionAmt': '0.002',
        'entryPrice': '48000.0',
        'unRealizedProfit': '-40.0',
        'side': 'BUY'
    }

    print(f"  Позиции на бирже перед восстановлением: {len(exchange.positions)}")
    print(f"  Позиции в боте перед восстановлением: {len(order_manager.active_positions)}")

    # Создаем новый OrderManager (симуляция перезапуска)
    new_order_manager = OrderManager(config, exchange, logger)
    await new_order_manager.initialize()

    print(f"  После восстановления - позиции в боте: {len(new_order_manager.active_positions)}")
    print(f"  После восстановления - позиции на бирже: {len(exchange.positions)}")
    print(f"  Восстановленные позиции: {list(new_order_manager.active_positions.keys())}")

    # Тест 7: Очистка висящих ордеров
    print("\n📋 Тест 7: Очистка висящих ордеров")

    # Создаем висящий ордер
    hanging_order = {
        'orderId': 999,
        'symbol': 'BTCUSDC_HANGING',
        'side': 'BUY',
        'quantity': 0.001,
        'type': 'LIMIT',
        'status': 'NEW',
        'price': 50000.0,
        'time': int((time.time() - 400) * 1000)  # 400 секунд назад
    }
    exchange.orders[999] = hanging_order

    print(f"  До очистки - ордеров на бирже: {len(exchange.orders)}")
    print(f"  Висящий ордер: {hanging_order}")

    # Очищаем висящие ордера
    await order_manager.cleanup_hanging_orders()

    print(f"  После очистки - ордеров на бирже: {len(exchange.orders)}")
    print(f"  Статус висящего ордера: {exchange.orders.get(999, {}).get('status', 'НЕ НАЙДЕН')}")

    # Тест 8: Проверка мониторинга позиций
    print("\n📋 Тест 8: Проверка мониторинга позиций")

    # Запускаем мониторинг на короткое время
    monitor_task = asyncio.create_task(order_manager.monitor_positions())

    # Ждем немного для выполнения мониторинга
    await asyncio.sleep(2)

    # Останавливаем мониторинг
    order_manager.shutdown_requested = True
    await asyncio.sleep(1)

    if not monitor_task.done():
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

    print(f"  Мониторинг завершен. Позиции в боте: {len(order_manager.active_positions)}")
    print(f"  Позиции на бирже: {len(exchange.positions)}")

    # Анализ событий
    print("\n📊 Анализ событий синхронизации:")
    sync_events = [e for e in logger.events if 'sync' in e['message'].lower() or 'position' in e['message'].lower()]
    for event in sync_events[-10:]:  # Последние 10 событий
        print(f"  {event['level']}: {event['message']}")

    print(f"\n✅ Тестирование синхронизации завершено! Всего событий: {len(logger.events)}")

async def main():
    try:
        await test_synchronization_scenarios()
        print("\n🎉 Все тесты синхронизации прошли успешно!")
    except Exception as e:
        print(f"\n❌ Ошибка в тестах синхронизации: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
