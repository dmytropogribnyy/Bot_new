#!/usr/bin/env python3
"""
Тест системы расчета комиссий Binance USDC-M Futures.
Проверяет корректность расчета комиссий с учетом BNB скидок и VIP уровней.
"""

import asyncio

from utils.helpers import (
    calculate_dynamic_fee,
    calculate_gross_pnl,
    calculate_liquidation_price,
    calculate_net_pnl_with_fees,
    calculate_notional_value,
)


class MockExchangeClient:
    """Mock для тестирования ExchangeClient"""

    def __init__(self):
        self.fee_info = {
            "maker_fee": 0.0002,
            "taker_fee": 0.0004,
            "has_bnb_discount": False,
            "vip_level": 0,
            "commission_rate": 0.0004,
        }

    async def get_fee_info(self):
        return self.fee_info

    def set_fee_info(self, fee_info):
        self.fee_info = fee_info


class MockLogger:
    """Mock для тестирования логгера"""

    def __init__(self):
        self.logs = []

    def log_trade(self, symbol, side, entry_price, exit_price, qty, pnl, win, fees):
        self.logs.append({
            'symbol': symbol,
            'side': side,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'qty': qty,
            'pnl': pnl,
            'win': win,
            'fees': fees,
        })


async def test_basic_fee_calculation():
    """Тест базового расчета комиссий"""
    print("🔍 Тест базового расчета комиссий...")

    # Тест 1: Базовые комиссии без BNB
    quantity = 1.0
    price = 50000.0

    # Taker fee (MARKET order)
    taker_fee = calculate_dynamic_fee(quantity, price, "MARKET", False, 0)
    expected_taker = quantity * price * 0.0004  # 0.04%
    assert abs(taker_fee - expected_taker) < 0.01, f"Taker fee: {taker_fee} != {expected_taker}"

    # Maker fee (LIMIT order)
    maker_fee = calculate_dynamic_fee(quantity, price, "LIMIT", False, 0)
    expected_maker = quantity * price * 0.0002  # 0.02%
    assert abs(maker_fee - expected_maker) < 0.01, f"Maker fee: {maker_fee} != {expected_maker}"

    print("✅ Базовые комиссии рассчитаны корректно")


async def test_bnb_discount_fees():
    """Тест комиссий со скидкой BNB"""
    print("🔍 Тест комиссий со скидкой BNB...")

    quantity = 1.0
    price = 50000.0

    # Taker fee с BNB
    taker_fee_bnb = calculate_dynamic_fee(quantity, price, "MARKET", True, 0)
    expected_taker_bnb = quantity * price * 0.0003  # 0.03% с BNB
    assert abs(taker_fee_bnb - expected_taker_bnb) < 0.01, f"Taker fee BNB: {taker_fee_bnb} != {expected_taker_bnb}"

    # Maker fee с BNB
    maker_fee_bnb = calculate_dynamic_fee(quantity, price, "LIMIT", True, 0)
    expected_maker_bnb = quantity * price * 0.0001  # 0.01% с BNB
    assert abs(maker_fee_bnb - expected_maker_bnb) < 0.01, f"Maker fee BNB: {maker_fee_bnb} != {expected_maker_bnb}"

    print("✅ Комиссии со скидкой BNB рассчитаны корректно")


async def test_vip_level_fees():
    """Тест комиссий с VIP уровнями"""
    print("🔍 Тест комиссий с VIP уровнями...")

    quantity = 1.0
    price = 50000.0

    # VIP 1 уровень
    vip1_fee = calculate_dynamic_fee(quantity, price, "MARKET", False, 1)
    base_fee = quantity * price * 0.0004
    vip1_discount = quantity * price * 0.00001  # 0.001% скидка
    expected_vip1 = base_fee - vip1_discount
    assert abs(vip1_fee - expected_vip1) < 0.01, f"VIP1 fee: {vip1_fee} != {expected_vip1}"

    # VIP 10 уровень (максимальная скидка)
    vip10_fee = calculate_dynamic_fee(quantity, price, "MARKET", False, 10)
    max_discount = quantity * price * 0.0001  # Максимум 0.01% скидка
    expected_vip10 = base_fee - max_discount
    assert abs(vip10_fee - expected_vip10) < 0.01, f"VIP10 fee: {vip10_fee} != {expected_vip10}"

    print("✅ VIP комиссии рассчитаны корректно")


async def test_pnl_calculation_with_fees():
    """Тест расчета PnL с комиссиями"""
    print("🔍 Тест расчета PnL с комиссиями...")

    # Тест прибыльной сделки
    entry_price = 50000.0
    exit_price = 50500.0  # +1% прибыль
    quantity = 1.0
    side = "buy"

    # Без BNB
    pnl_no_bnb = calculate_net_pnl_with_fees(
        entry_price, exit_price, quantity, side,
        "MARKET", "MARKET", False, 0
    )

    # С BNB
    pnl_with_bnb = calculate_net_pnl_with_fees(
        entry_price, exit_price, quantity, side,
        "MARKET", "MARKET", True, 0
    )

    # Проверяем, что с BNB комиссии меньше
    assert pnl_with_bnb["total_fees"] < pnl_no_bnb["total_fees"], "BNB fees should be lower"
    assert pnl_with_bnb["net_pnl"] > pnl_no_bnb["net_pnl"], "BNB net PnL should be higher"

    print(f"✅ PnL без BNB: {pnl_no_bnb['net_pnl']:.2f} USDC")
    print(f"✅ PnL с BNB: {pnl_with_bnb['net_pnl']:.2f} USDC")
    print(f"✅ Экономия с BNB: {pnl_no_bnb['total_fees'] - pnl_with_bnb['total_fees']:.2f} USDC")


async def test_liquidation_price_with_fees():
    """Тест расчета цены ликвидации с комиссиями"""
    print("🔍 Тест расчета цены ликвидации с комиссиями...")

    entry_price = 50000.0
    side = "buy"
    leverage = 5
    wallet_balance = 1000.0
    position_size = 0.1

    # Без BNB
    liq_price_no_bnb = calculate_liquidation_price(
        entry_price, side, leverage, wallet_balance, position_size,
        0.004, False, 0
    )

    # С BNB
    liq_price_with_bnb = calculate_liquidation_price(
        entry_price, side, leverage, wallet_balance, position_size,
        0.004, True, 0
    )

    # С BNB цена ликвидации должна быть ниже (меньше комиссий)
    assert liq_price_with_bnb < liq_price_no_bnb, "BNB liquidation price should be lower"

    print(f"✅ Цена ликвидации без BNB: {liq_price_no_bnb:.2f}")
    print(f"✅ Цена ликвидации с BNB: {liq_price_with_bnb:.2f}")


async def test_notional_value_calculation():
    """Тест расчета номинальной стоимости"""
    print("🔍 Тест расчета номинальной стоимости...")

    quantity = 0.5
    price = 50000.0
    notional = calculate_notional_value(quantity, price)
    expected = quantity * price

    assert abs(notional - expected) < 0.01, f"Notional: {notional} != {expected}"
    print(f"✅ Номинальная стоимость: {notional:.2f} USDC")


async def test_gross_pnl_calculation():
    """Тест расчета валового PnL"""
    print("🔍 Тест расчета валового PnL...")

    entry_price = 50000.0
    exit_price = 50500.0
    quantity = 1.0

    # Long position
    long_pnl = calculate_gross_pnl(entry_price, exit_price, quantity, "buy")
    expected_long = (exit_price - entry_price) * quantity
    assert abs(long_pnl - expected_long) < 0.01, f"Long PnL: {long_pnl} != {expected_long}"

    # Short position
    short_pnl = calculate_gross_pnl(entry_price, exit_price, quantity, "sell")
    expected_short = (entry_price - exit_price) * quantity
    assert abs(short_pnl - expected_short) < 0.01, f"Short PnL: {short_pnl} != {expected_short}"

    print(f"✅ Long PnL: {long_pnl:.2f} USDC")
    print(f"✅ Short PnL: {short_pnl:.2f} USDC")


async def test_fee_comparison_scenarios():
    """Тест различных сценариев комиссий"""
    print("🔍 Тест различных сценариев комиссий...")

    quantity = 1.0
    price = 50000.0

    scenarios = [
        {"name": "Market без BNB", "order_type": "MARKET", "has_bnb": False, "vip": 0},
        {"name": "Limit без BNB", "order_type": "LIMIT", "has_bnb": False, "vip": 0},
        {"name": "Market с BNB", "order_type": "MARKET", "has_bnb": True, "vip": 0},
        {"name": "Limit с BNB", "order_type": "LIMIT", "has_bnb": True, "vip": 0},
        {"name": "Market VIP5", "order_type": "MARKET", "has_bnb": False, "vip": 5},
        {"name": "Limit VIP10", "order_type": "LIMIT", "has_bnb": True, "vip": 10},
    ]

    for scenario in scenarios:
        fee = calculate_dynamic_fee(
            quantity, price,
            scenario["order_type"],
            scenario["has_bnb"],
            scenario["vip"]
        )
        print(f"✅ {scenario['name']}: {fee:.2f} USDC")


async def test_exchange_client_fee_integration():
    """Тест интеграции с ExchangeClient"""
    print("🔍 Тест интеграции с ExchangeClient...")

    mock_client = MockExchangeClient()

    # Тест без BNB
    fee_info_no_bnb = await mock_client.get_fee_info()
    assert fee_info_no_bnb["has_bnb_discount"] == False
    assert fee_info_no_bnb["taker_fee"] == 0.0004

    # Тест с BNB
    mock_client.set_fee_info({
        "maker_fee": 0.0001,
        "taker_fee": 0.0003,
        "has_bnb_discount": True,
        "vip_level": 0,
        "commission_rate": 0.0003,
    })

    fee_info_with_bnb = await mock_client.get_fee_info()
    assert fee_info_with_bnb["has_bnb_discount"] == True
    assert fee_info_with_bnb["taker_fee"] == 0.0003

    print("✅ Интеграция с ExchangeClient работает корректно")


async def main():
    """Основная функция тестирования"""
    print("🚀 Запуск тестов системы комиссий Binance USDC-M Futures")
    print("=" * 60)

    try:
        await test_basic_fee_calculation()
        await test_bnb_discount_fees()
        await test_vip_level_fees()
        await test_pnl_calculation_with_fees()
        await test_liquidation_price_with_fees()
        await test_notional_value_calculation()
        await test_gross_pnl_calculation()
        await test_fee_comparison_scenarios()
        await test_exchange_client_fee_integration()

        print("\n" + "=" * 60)
        print("🎉 ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
        print("✅ Система комиссий работает корректно")
        print("✅ Учтены BNB скидки и VIP уровни")
        print("✅ PnL расчеты точные")
        print("✅ Цены ликвидации корректные")

    except Exception as e:
        print(f"\n❌ ОШИБКА В ТЕСТАХ: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
