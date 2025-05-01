# order_utils.py
def calculate_order_quantity(
    entry_price: float, stop_price: float, balance: float, risk_percent: float
) -> float:
    """
    Вычисляет количество контрактов для ордера.

    Формула: количество = (баланс * риск_percent) / (|entry_price - stop_price|)
    """
    risk_amount = balance * risk_percent
    risk_per_contract = abs(entry_price - stop_price)
    qty = risk_amount / risk_per_contract if risk_per_contract > 0 else 0
    return round(qty, 3)
