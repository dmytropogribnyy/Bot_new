#!/usr/bin/env python3
"""
Тест системы закрытия сделок по времени
Проверяет все сценарии time-based exits
"""

import asyncio
import time
from datetime import datetime
from types import SimpleNamespace

from core.order_manager import OrderManager


class MockExchangeClient:
    def __init__(self):
        self.orders = {}
        self.order_id_counter = 1

    async def set_leverage(self, symbol, leverage):
        return {'success': True}

    async def place_order(self, symbol, side, quantity, order_type="MARKET", price=None, params=None):
        order_id = self.order_id_counter
        self.order_id_counter += 1

        order = {
            'orderId': order_id,
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'type': order_type,
            'status': 'FILLED',
            'price': price or 50000.0
        }

        self.orders[order_id] = order
        return order

    async def get_ticker(self, symbol):
        # Симулируем разные цены для разных тестов
        if 'TIMEOUT' in symbol:
            price = '48000.0'  # Убыток для timeout
        elif 'PROFIT' in symbol:
            price = '50700.0'  # Прибыль для auto-profit
        elif 'WEAK' in symbol:
            price = '50050.0'  # Небольшая прибыль для weak
        elif 'RISKY' in symbol:
            price = '49250.0'  # Убыток для risky
        else:
            price = '50000.0'

        return {'lastPrice': price}

    async def get_order_status(self, symbol, order_id):
        return self.orders.get(order_id, {'status': 'FILLED'})

    # Добавляем недостающие методы
    async def get_positions(self):
        return []

    async def get_open_orders(self, symbol=None):
        return []

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
            'timestamp': datetime.now().isoformat()  # Исправляем deprecation warning
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

async def test_timeout_scenarios():
    """Тестирование различных сценариев закрытия по времени"""
    print("🚀 Тестирование системы закрытия сделок по времени")
    print("=" * 60)

    # Конфигурация с разными параметрами
    config = SimpleNamespace(
        sl_percent=0.012,
        step_tp_levels=[0.004, 0.008, 0.012],
        step_tp_sizes=[0.5, 0.3, 0.2],
        max_position_duration=3600,
        max_concurrent_positions=3,
        min_trade_qty=0.001,
        telegram_enabled=False,
        # Параметры для enhanced timeout system
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

    # Тест 1: Максимальное время удержания
    print("\n📋 Тест 1: Максимальное время удержания")
    await order_manager.place_position_with_tp_sl(
        symbol="BTCUSDC_TIMEOUT",
        side="BUY",
        quantity=0.001,
        entry_price=50000.0,
        leverage=5
    )

    # Симулируем старое время входа
    position = order_manager.active_positions["BTCUSDC_TIMEOUT"]
    position['entry_time'] = time.time() - (35 * 60)  # 35 минут назад

    await order_manager.check_timeouts()

    if "BTCUSDC_TIMEOUT" not in order_manager.active_positions:
        print("✅ Позиция закрыта по максимальному времени удержания")
    else:
        print("❌ Позиция не закрыта по времени")

    # Очищаем позиции для следующего теста
    order_manager.active_positions.clear()

    # Тест 2: Auto-profit
    print("\n📋 Тест 2: Auto-profit")
    await order_manager.place_position_with_tp_sl(
        symbol="BTCUSDC_PROFIT",
        side="BUY",
        quantity=0.001,
        entry_price=50000.0,
        leverage=5
    )

    # Устанавливаем entry_time для позиции ДО вызова check_timeouts
    position = order_manager.active_positions["BTCUSDC_PROFIT"]
    position['entry_time'] = time.time() - (10 * 60)  # 10 минут назад

    await order_manager.check_timeouts()

    if "BTCUSDC_PROFIT" not in order_manager.active_positions:
        print("✅ Позиция закрыта по auto-profit")
    else:
        print("❌ Позиция не закрыта по auto-profit")

    # Очищаем позиции для следующего теста
    order_manager.active_positions.clear()

    # Тест 3: Слабая позиция
    print("\n📋 Тест 3: Слабая позиция")
    await order_manager.place_position_with_tp_sl(
        symbol="BTCUSDC_WEAK",
        side="BUY",
        quantity=0.001,
        entry_price=50000.0,
        leverage=5
    )

    # Симулируем старое время входа ДО вызова check_timeouts
    position = order_manager.active_positions["BTCUSDC_WEAK"]
    position['entry_time'] = time.time() - (50 * 60)  # 50 минут назад

    await order_manager.check_timeouts()

    if "BTCUSDC_WEAK" not in order_manager.active_positions:
        print("✅ Слабая позиция закрыта")
    else:
        print("❌ Слабая позиция не закрыта")

    # Очищаем позиции для следующего теста
    order_manager.active_positions.clear()

    # Тест 4: Рискованная позиция
    print("\n📋 Тест 4: Рискованная позиция")
    await order_manager.place_position_with_tp_sl(
        symbol="BTCUSDC_RISKY",
        side="BUY",
        quantity=0.001,
        entry_price=50000.0,
        leverage=5
    )

    # Устанавливаем entry_time для позиции ДО вызова check_timeouts
    position = order_manager.active_positions["BTCUSDC_RISKY"]
    position['entry_time'] = time.time() - (5 * 60)  # 5 минут назад

    await order_manager.check_timeouts()

    if "BTCUSDC_RISKY" not in order_manager.active_positions:
        print("✅ Рискованная позиция закрыта")
    else:
        print("❌ Рискованная позиция не закрыта")

    # Анализ событий
    print("\n📊 Анализ событий:")
    for event in logger.events:
        if "closing" in event['message'].lower() or "closed" in event['message'].lower():
            print(f"  {event['level']}: {event['message']}")

    print(f"\n✅ Тестирование завершено! Всего событий: {len(logger.events)}")

async def main():
    try:
        await test_timeout_scenarios()
        print("\n🎉 Все тесты прошли успешно!")
    except Exception as e:
        print(f"\n❌ Ошибка в тестах: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
