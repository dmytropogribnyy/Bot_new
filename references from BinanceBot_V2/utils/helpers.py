# BinanceBot_v2/utils/helpers.py

import hashlib
import re
import time
from datetime import datetime
from decimal import Decimal
from typing import Any


def round_down_by_step(value: float, step: float) -> float:
    """
    Точно округляет значение вниз до ближайшего шага с использованием Decimal.
    Критично для соответствия правилам Binance по stepSize.

    Args:
        value: Значение для округления
        step: Шаг округления (stepSize)

    Returns:
        Округленное значение

    Example:
        >>> round_down_by_step(0.123456, 0.001)
        0.123
    """
    if step <= 0 or value <= 0:
        return 0.0

    value_dec = Decimal(str(value))
    step_dec = Decimal(str(step))
    return float((value_dec // step_dec) * step_dec)


def normalize_symbol(symbol: str) -> str:
    """
    Обеспечивает единый формат символа для всей системы.
    BTCUSDC -> BTC/USDC
    BTC/USDC:USDC -> BTC/USDC

    Args:
        symbol: Символ в любом формате

    Returns:
        Нормализованный символ с слэшем
    """
    # Удаляем суффикс :USDC если есть
    symbol = symbol.split(":")[0]

    # Добавляем слэш если его нет
    if "/" not in symbol:
        # Предполагаем что последние 4 символа - это quote asset
        if symbol.endswith("USDC"):
            symbol = f"{symbol[:-4]}/{symbol[-4:]}"
        elif symbol.endswith("USDT"):
            symbol = f"{symbol[:-4]}/{symbol[-4:]}"

    return symbol.upper()


def convert_symbol_for_api(symbol: str) -> str:
    """
    Конвертирует символ из внутреннего формата в формат API.
    BTC/USDC -> BTCUSDC

    Args:
        symbol: Символ с слэшем

    Returns:
        Символ для API без слэша
    """
    return symbol.replace("/", "").replace("-", "")


def calculate_percentage_change(old_value: float, new_value: float) -> float:
    """
    Безопасный расчет процентного изменения.

    Args:
        old_value: Старое значение
        new_value: Новое значение

    Returns:
        Процентное изменение
    """
    if old_value == 0:
        return 0.0
    return ((new_value - old_value) / old_value) * 100


def generate_order_id(symbol: str, side: str) -> str:
    """
    Генерирует уникальный ID для внутреннего трекинга ордеров.

    Args:
        symbol: Торговый символ
        side: buy или sell

    Returns:
        Уникальный ID ордера
    """
    timestamp = str(int(time.time() * 1000))
    data = f"{symbol}_{side}_{timestamp}"
    return hashlib.md5(data.encode()).hexdigest()[:16]


def format_price(price: float, precision: int = 2) -> str:
    """
    Форматирует цену для отображения.

    Args:
        price: Цена
        precision: Количество знаков после запятой

    Returns:
        Отформатированная строка цены
    """
    return f"{price:.{precision}f}"


def format_quantity(qty: float, precision: int = 6) -> str:
    """
    Форматирует количество для отображения.

    Args:
        qty: Количество
        precision: Максимальное количество знаков

    Returns:
        Отформатированная строка
    """
    return f"{qty:.{precision}f}".rstrip("0").rstrip(".")


def safe_float(value: Any, default: float = 0.0) -> float:
    """
    Безопасное преобразование в float.

    Args:
        value: Любое значение
        default: Значение по умолчанию

    Returns:
        Float значение или default
    """
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Безопасное деление.

    Args:
        numerator: Числитель
        denominator: Знаменатель
        default: Значение при делении на 0

    Returns:
        Результат деления или default
    """
    if denominator == 0:
        return default
    return numerator / denominator


def clamp(value: float, min_value: float, max_value: float) -> float:
    """
    Ограничивает значение в заданном диапазоне.

    Args:
        value: Значение
        min_value: Минимум
        max_value: Максимум

    Returns:
        Значение в диапазоне [min_value, max_value]
    """
    return max(min_value, min(value, max_value))


def is_micro_position(quantity: float, price: float, threshold: float = 20.0) -> bool:
    """
    Проверяет, является ли позиция микро-позицией.

    Args:
        quantity: Количество
        price: Цена
        threshold: Порог в USDC

    Returns:
        True если позиция меньше порога
    """
    return (quantity * price) < threshold


def calculate_commission(quantity: float, price: float, rate: float = 0.0004) -> float:
    """
    Рассчитывает комиссию (по умолчанию taker fee 0.04%).

    Args:
        quantity: Количество
        price: Цена
        rate: Ставка комиссии

    Returns:
        Размер комиссии в USDC
    """
    return quantity * price * rate


def calculate_dynamic_fee(
    quantity: float,
    price: float,
    order_type: str = "MARKET",
    has_bnb_discount: bool = False,
    vip_level: int = 0
) -> float:
    """
    Рассчитывает комиссию с учетом типа ордера и скидок.

    Args:
        quantity: Количество
        price: Цена
        order_type: Тип ордера (MARKET/LIMIT)
        has_bnb_discount: Есть ли скидка BNB
        vip_level: VIP уровень (0-10)

    Returns:
        Размер комиссии в USDC
    """
    # Базовые комиссии Binance USDC-M Futures
    if has_bnb_discount:
        maker_fee = 0.0001  # 0.01% с BNB
        taker_fee = 0.0003  # 0.03% с BNB
    else:
        maker_fee = 0.0002  # 0.02% без BNB
        taker_fee = 0.0004  # 0.04% без BNB

    # VIP скидки (упрощенная модель)
    vip_discount = min(vip_level * 0.00001, 0.0001)  # Максимум 0.01% скидка

    # Выбираем комиссию в зависимости от типа ордера
    if order_type == "LIMIT":
        fee_rate = maker_fee - vip_discount
    else:
        fee_rate = taker_fee - vip_discount

    return quantity * price * fee_rate


def calculate_notional_value(quantity: float, price: float) -> float:
    """
    Рассчитывает номинальную стоимость позиции.

    Args:
        quantity: Количество
        price: Цена

    Returns:
        Номинальная стоимость в USDC
    """
    return quantity * price


def calculate_gross_pnl(entry_price: float, exit_price: float, quantity: float, side: str) -> float:
    """
    Рассчитывает валовый PnL без учета комиссий.

    Args:
        entry_price: Цена входа
        exit_price: Цена выхода
        quantity: Количество
        side: 'buy' или 'sell'

    Returns:
        Валовый PnL
    """
    if side.lower() == "buy":
        return (exit_price - entry_price) * quantity
    else:
        return (entry_price - exit_price) * quantity


def calculate_net_pnl_with_fees(
    entry_price: float,
    exit_price: float,
    quantity: float,
    side: str,
    entry_order_type: str = "MARKET",
    exit_order_type: str = "MARKET",
    has_bnb_discount: bool = False,
    vip_level: int = 0,
) -> dict[str, float]:
    """
    Рассчитывает чистый PnL с учетом комиссий Binance USDC-M Futures.

    Args:
        entry_price: Цена входа
        exit_price: Цена выхода
        quantity: Количество
        side: 'buy' или 'sell'
        entry_order_type: Тип ордера входа
        exit_order_type: Тип ордера выхода
        has_bnb_discount: Есть ли скидка BNB
        vip_level: VIP уровень

    Returns:
        Dict с gross_pnl, entry_fee, exit_fee, total_fees, net_pnl, pnl_percent
    """
    # Gross PnL
    gross_pnl = calculate_gross_pnl(entry_price, exit_price, quantity, side)

    # Notional values
    entry_notional = calculate_notional_value(quantity, entry_price)
    exit_notional = calculate_notional_value(quantity, exit_price)

    # Fees
    entry_fee = calculate_dynamic_fee(quantity, entry_price, entry_order_type, has_bnb_discount, vip_level)
    exit_fee = calculate_dynamic_fee(quantity, exit_price, exit_order_type, has_bnb_discount, vip_level)
    total_fees = entry_fee + exit_fee

    # Net PnL
    net_pnl = gross_pnl - total_fees

    # PnL %
    pnl_percent = (net_pnl / entry_notional) * 100 if entry_notional > 0 else 0

    return {
        "gross_pnl": gross_pnl,
        "entry_fee": entry_fee,
        "exit_fee": exit_fee,
        "total_fees": total_fees,
        "net_pnl": net_pnl,
        "pnl_percent": pnl_percent,
        "entry_notional": entry_notional,
        "exit_notional": exit_notional,
    }


# === Дополнительные функции из новых наработок ===


def calculate_position_value(quantity: float, price: float, leverage: int = 1) -> float:
    """
    Рассчитывает полную стоимость позиции с учетом плеча.

    Args:
        quantity: Количество
        price: Цена входа
        leverage: Кредитное плечо

    Returns:
        Полная стоимость позиции
    """
    return quantity * price / leverage


def calculate_required_margin(position_value: float, leverage: int) -> float:
    """
    Рассчитывает требуемую маржу для позиции.

    Args:
        position_value: Полная стоимость позиции
        leverage: Кредитное плечо

    Returns:
        Требуемая маржа в USDC
    """
    return position_value / leverage


def parse_binance_symbol(symbol: str) -> dict[str, str]:
    """
    Парсит символ Binance и извлекает компоненты.

    Args:
        symbol: Символ (например, BTCUSDC или 1000PEPEUSDC)

    Returns:
        Dict с base, quote и prefix
    """
    # Проверяем префиксы (1000, 10000)
    prefix = ""
    if symbol.startswith("10000"):
        prefix = "10000"
        symbol = symbol[5:]
    elif symbol.startswith("1000"):
        prefix = "1000"
        symbol = symbol[4:]

    # Извлекаем quote currency
    quote = ""
    if symbol.endswith("USDC"):
        quote = "USDC"
        base = symbol[:-4]
    elif symbol.endswith("USDT"):
        quote = "USDT"
        base = symbol[:-4]
    else:
        # Fallback
        base = symbol[:-4] if len(symbol) > 4 else symbol
        quote = symbol[-4:] if len(symbol) > 4 else ""

    return {"prefix": prefix, "base": base, "quote": quote, "full": f"{prefix}{base}{quote}"}


def format_telegram_html(text: str) -> str:
    """
    Экранирует HTML для Telegram.

    Args:
        text: Исходный текст

    Returns:
        Экранированный текст для HTML
    """
    escape_chars = {"<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;"}

    for char, escape in escape_chars.items():
        text = text.replace(char, escape)

    return text


def calculate_pnl_with_fees(
    entry_price: float,
    exit_price: float,
    quantity: float,
    side: str,
    entry_fee_rate: float = 0.0004,
    exit_fee_rate: float = 0.0004,
) -> dict[str, float]:
    """
    Рассчитывает PnL с учетом комиссий.

    Args:
        entry_price: Цена входа
        exit_price: Цена выхода
        quantity: Количество
        side: 'buy' или 'sell'
        entry_fee_rate: Комиссия входа
        exit_fee_rate: Комиссия выхода

    Returns:
        Dict с gross_pnl, fees, net_pnl, pnl_percent
    """
    # Gross PnL
    if side == "buy":
        gross_pnl = (exit_price - entry_price) * quantity
    else:
        gross_pnl = (entry_price - exit_price) * quantity

    # Fees
    entry_fee = entry_price * quantity * entry_fee_rate
    exit_fee = exit_price * quantity * exit_fee_rate
    total_fees = entry_fee + exit_fee

    # Net PnL
    net_pnl = gross_pnl - total_fees

    # PnL %
    position_value = entry_price * quantity
    pnl_percent = (net_pnl / position_value) * 100 if position_value > 0 else 0

    return {
        "gross_pnl": gross_pnl,
        "entry_fee": entry_fee,
        "exit_fee": exit_fee,
        "total_fees": total_fees,
        "net_pnl": net_pnl,
        "pnl_percent": pnl_percent,
    }


def time_until_next_candle(timeframe: str = "1m") -> int:
    """
    Рассчитывает секунды до закрытия текущей свечи.

    Args:
        timeframe: Таймфрейм ('1m', '5m', '15m', etc.)

    Returns:
        Секунды до закрытия свечи
    """
    now = datetime.utcnow()

    timeframe_seconds = {
        "1m": 60,
        "3m": 180,
        "5m": 300,
        "15m": 900,
        "30m": 1800,
        "1h": 3600,
        "4h": 14400,
        "1d": 86400,
    }

    seconds = timeframe_seconds.get(timeframe, 60)
    current_timestamp = int(now.timestamp())
    next_candle_timestamp = ((current_timestamp // seconds) + 1) * seconds

    return next_candle_timestamp - current_timestamp


def validate_leverage(leverage: int) -> int:
    """
    Валидирует и ограничивает leverage в допустимых пределах.

    Args:
        leverage: Желаемое плечо

    Returns:
        Валидное плечо (1-20)
    """
    return clamp(int(leverage), 1, 20)


def calculate_liquidation_price(
    entry_price: float,
    side: str,
    leverage: int,
    wallet_balance: float,
    position_size: float,
    maintenance_margin_rate: float = 0.004,  # 0.4% default для USDC-M
    has_bnb_discount: bool = False,
    vip_level: int = 0,
) -> float:
    """
    Точный расчет цены ликвидации для Binance USDC-M Futures.

    Args:
        entry_price: Цена входа
        side: 'buy' (long) или 'sell' (short)
        leverage: Кредитное плечо
        wallet_balance: Баланс кошелька (Wallet Balance)
        position_size: Размер позиции (в контрактах)
        maintenance_margin_rate: MMR (по умолчанию 0.4%)
        has_bnb_discount: Есть ли скидка BNB
        vip_level: VIP уровень

    Returns:
        Цена ликвидации (float)
    """

    # Notional value позиции
    notional_value = position_size * entry_price

    # Maintenance Margin (MM) и Closing Fee
    maintenance_margin = notional_value * maintenance_margin_rate

    # Используем правильную комиссию для закрытия по рынку
    closing_fee = calculate_dynamic_fee(
        position_size,
        entry_price,
        "MARKET",  # Закрытие по рынку
        has_bnb_discount,
        vip_level
    )

    # Формула ликвидации:
    # Ликвидация происходит, когда: WB + Unrealized PnL ≤ MM + Fees
    # Решаем для Liq Price в зависимости от направления позиции

    if side.lower() == "buy":
        # Long position: Unrealized PnL = Size * (Mark Price - Entry Price)
        # Liq Price = Entry Price - (WB - MM - Fees) / Size
        liquidation_price = (
            entry_price - (wallet_balance - maintenance_margin - closing_fee) / position_size
        )

    elif side.lower() == "sell":
        # Short position: Unrealized PnL = Size * (Entry Price - Mark Price)
        # Liq Price = Entry Price + (WB - MM - Fees) / Size
        liquidation_price = (
            entry_price + (wallet_balance - maintenance_margin - closing_fee) / position_size
        )

    else:
        raise ValueError(f"Invalid side '{side}'. Must be 'buy' or 'sell'.")

    # Защита от отрицательных значений
    return max(0.0, liquidation_price)


def format_duration(seconds: int) -> str:
    """
    Форматирует длительность в читаемый вид.

    Args:
        seconds: Количество секунд

    Returns:
        Форматированная строка (например, "2h 15m")
    """
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}m {secs}s" if secs > 0 else f"{minutes}m"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m" if minutes > 0 else f"{hours}h"


def extract_error_code(error_message: str) -> str | None:
    """
    Извлекает код ошибки Binance из сообщения.

    Args:
        error_message: Сообщение об ошибке

    Returns:
        Код ошибки или None
    """
    # Binance error codes обычно в формате: -1021, -2010, etc.
    match = re.search(r"-\d{4}", error_message)
    if match:
        return match.group()

    # Или в формате: "code":-1021
    match = re.search(r'"code":\s*(-?\d+)', error_message)
    if match:
        return match.group(1)

    return None


def is_insufficient_balance_error(error_message: str) -> bool:
    """
    Проверяет, является ли ошибка недостатком баланса.

    Args:
        error_message: Сообщение об ошибке

    Returns:
        True если ошибка связана с балансом
    """
    balance_errors = [
        "-2019",  # Margin insufficient
        "-1111",  # Precision over maximum
        "-2018",  # Balance insufficient
        "Insufficient balance",
        "Account has insufficient balance",
    ]

    error_lower = error_message.lower()
    return any(err.lower() in error_lower for err in balance_errors)


def get_maintenance_margin_rate(notional_value: float) -> float:
    """
    Получает Maintenance Margin Rate на основе Notional Value.
    Тарифы Binance USDC-M (актуальны на 2024).

    Args:
        notional_value: Notional value позиции в USDC

    Returns:
        Maintenance margin rate
    """
    # Binance USDC-M tier system
    if notional_value < 10_000:
        return 0.004  # 0.4%
    elif notional_value < 50_000:
        return 0.005  # 0.5%
    elif notional_value < 250_000:
        return 0.01  # 1.0%
    elif notional_value < 1_000_000:
        return 0.025  # 2.5%
    elif notional_value < 5_000_000:
        return 0.05  # 5.0%
    elif notional_value < 20_000_000:
        return 0.10  # 10.0%
    elif notional_value < 50_000_000:
        return 0.125  # 12.5%
    else:
        return 0.15  # 15.0%


def is_market_open(
    check_maintenance: bool = True, check_high_impact_events: bool = True, symbol: str = None
) -> tuple[bool, str]:
    """
    Продвинутая проверка доступности рынка для торговли.

    Проверяет:
    - Binance maintenance windows
    - Высоковолатильные события (FOMC, CPI, NFP)
    - Системные обновления
    - Специфичные для символа ограничения

    Args:
        check_maintenance: Проверять maintenance windows
        check_high_impact_events: Проверять важные события
        symbol: Опциональный символ для специфичных проверок

    Returns:
        (is_open, reason) - tuple с флагом и причиной
    """
    current_time = datetime.utcnow()

    # 1. Проверка Binance maintenance (обычно среда 06:00-08:00 UTC)
    if check_maintenance:
        # Регулярный maintenance
        if current_time.weekday() == 2:  # Среда
            hour = current_time.hour
            if 6 <= hour < 8:
                return False, "Binance regular maintenance window (Wed 06:00-08:00 UTC)"

        # System upgrade windows (первый вторник месяца)
        if current_time.weekday() == 1:  # Вторник
            if current_time.day <= 7:  # Первая неделя месяца
                if 2 <= current_time.hour < 4:
                    return False, "Binance system upgrade window"

    # 2. Проверка высоковолатильных событий
    if check_high_impact_events:
        high_impact_events = get_high_impact_events()

        for event in high_impact_events:
            event_time = event["time"]

            # Блокируем торговлю за 5 минут до и 15 минут после события
            time_until_event = (event_time - current_time).total_seconds()

            if -300 <= time_until_event <= 900:  # -5 min до +15 min
                return (
                    False,
                    f"High impact event: {event['name']} at {event_time.strftime('%H:%M UTC')}",
                )

    # 3. Проверка специфичных для символа ограничений
    if symbol:
        # Новые листинги - избегаем первые 24 часа
        if is_new_listing(symbol):
            return False, f"{symbol} is a new listing (< 24h)"

        # Делистинг - прекращаем торговлю за 48 часов
        delisting_date = get_delisting_date(symbol)
        if delisting_date:
            hours_until_delisting = (delisting_date - current_time).total_seconds() / 3600
            if hours_until_delisting <= 48:
                return False, f"{symbol} delisting in {hours_until_delisting:.1f} hours"

    return True, "Market is open"


def get_high_impact_events() -> list[dict]:
    """
    Возвращает список важных экономических событий на сегодня.
    В production это должно браться из API экономического календаря.
    """
    # Пример статических событий для демонстрации
    # В реальности нужно интегрировать с forexfactory.com API или similar

    current_date = datetime.utcnow().date()
    events = []

    # FOMC meetings (обычно среда, 18:00 UTC)
    if current_date.weekday() == 2:  # Среда
        # Проверяем, является ли это FOMC средой (каждые 6 недель)
        week_of_year = current_date.isocalendar()[1]
        if week_of_year % 6 == 3:  # Примерная логика
            events.append(
                {
                    "name": "FOMC Interest Rate Decision",
                    "time": datetime.combine(
                        current_date, datetime.strptime("18:00", "%H:%M").time()
                    ),
                    "impact": "high",
                    "currencies": ["USD"],
                }
            )

    # Non-Farm Payrolls (первая пятница месяца, 12:30 UTC)
    if current_date.weekday() == 4 and current_date.day <= 7:
        events.append(
            {
                "name": "US Non-Farm Payrolls",
                "time": datetime.combine(current_date, datetime.strptime("12:30", "%H:%M").time()),
                "impact": "high",
                "currencies": ["USD"],
            }
        )

    # CPI (обычно около 12-15 числа, 12:30 UTC)
    if 12 <= current_date.day <= 15:
        events.append(
            {
                "name": "US CPI m/m",
                "time": datetime.combine(current_date, datetime.strptime("12:30", "%H:%M").time()),
                "impact": "high",
                "currencies": ["USD"],
            }
        )

    return events


def is_new_listing(symbol: str) -> bool:
    """
    Проверяет, является ли символ новым листингом (< 24 часа).
    В production должно проверяться через API или базу данных.
    """
    # Заглушка - в реальности нужно хранить даты листинга
    new_listings = {
        "TRUMPUSDC": datetime(2024, 1, 20),  # Пример
        "KAITOUSDC": datetime(2024, 1, 15),
    }

    listing_date = new_listings.get(symbol.replace("/", ""))
    if listing_date:
        hours_since_listing = (datetime.utcnow() - listing_date).total_seconds() / 3600
        return hours_since_listing < 24

    return False


def get_delisting_date(symbol: str) -> datetime | None:
    """
    Возвращает дату делистинга символа, если объявлено.
    В production должно браться из Binance announcements API.
    """
    # Заглушка - в реальности нужно парсить announcements
    delisting_schedule = {
        "COCOSUSDC": datetime(2024, 2, 1, 8, 0),  # Пример
    }

    return delisting_schedule.get(symbol.replace("/", ""))


def should_avoid_trading(
    symbol: str, current_volatility: float, recent_pnl: float, open_positions: int
) -> tuple[bool, str]:
    """
    Комплексная проверка, стоит ли избегать торговли.

    Args:
        symbol: Торговый символ
        current_volatility: Текущая волатильность (ATR%)
        recent_pnl: PnL за последний час
        open_positions: Количество открытых позиций

    Returns:
        (should_avoid, reason)
    """
    # 1. Проверка рынка
    market_open, market_reason = is_market_open(symbol=symbol)
    if not market_open:
        return True, market_reason

    # 2. Экстремальная волатильность
    if current_volatility > 5.0:  # > 5% ATR
        return True, f"Extreme volatility: {current_volatility:.1f}%"

    # 3. Серия убытков
    if recent_pnl < -50 and open_positions >= 2:  # -$50 и есть позиции
        return True, f"Recent losses: ${recent_pnl:.2f} with {open_positions} open positions"

    # 4. Время суток (опционально - избегать ночной торговли по UTC)
    current_hour = datetime.utcnow().hour
    if 2 <= current_hour <= 5:  # 02:00-05:00 UTC - низкая ликвидность
        if current_volatility < 0.3:  # И низкая волатильность
            return True, "Low liquidity hours with low volatility"

    return False, "OK"


# === Функции для работы с данными ===


def aggregate_ohlcv(ohlcv_data: list[list], target_timeframe: int) -> list[list]:
    """
    Агрегирует OHLCV данные в больший таймфрейм.

    Args:
        ohlcv_data: Список [timestamp, open, high, low, close, volume]
        target_timeframe: Целевой таймфрейм в минутах

    Returns:
        Агрегированные данные
    """
    if not ohlcv_data:
        return []

    aggregated = []
    current_group = []

    for candle in ohlcv_data:
        if not current_group:
            current_group = [candle]
        else:
            # Проверяем, входит ли свеча в текущую группу
            first_timestamp = current_group[0][0]
            current_timestamp = candle[0]

            if (current_timestamp - first_timestamp) < (target_timeframe * 60 * 1000):
                current_group.append(candle)
            else:
                # Агрегируем группу
                aggregated.append(
                    [
                        current_group[0][0],  # timestamp первой свечи
                        current_group[0][1],  # open первой свечи
                        max(c[2] for c in current_group),  # high
                        min(c[3] for c in current_group),  # low
                        current_group[-1][4],  # close последней свечи
                        sum(c[5] for c in current_group),  # сумма volume
                    ]
                )
                current_group = [candle]

    # Не забываем последнюю группу
    if current_group:
        aggregated.append(
            [
                current_group[0][0],
                current_group[0][1],
                max(c[2] for c in current_group),
                min(c[3] for c in current_group),
                current_group[-1][4],
                sum(c[5] for c in current_group),
            ]
        )

    return aggregated


# === Экспорт всех функций ===
__all__ = [
    "round_down_by_step",
    "normalize_symbol",
    "convert_symbol_for_api",
    "calculate_percentage_change",
    "generate_order_id",
    "format_price",
    "format_quantity",
    "safe_float",
    "safe_div",
    "clamp",
    "is_micro_position",
    "calculate_commission",
    "calculate_dynamic_fee",
    "calculate_notional_value",
    "calculate_gross_pnl",
    "calculate_net_pnl_with_fees",
    "calculate_position_value",
    "calculate_required_margin",
    "parse_binance_symbol",
    "format_telegram_html",
    "calculate_pnl_with_fees",
    "is_market_open",
    "time_until_next_candle",
    "validate_leverage",
    "calculate_liquidation_price",
    "format_duration",
    "extract_error_code",
    "is_insufficient_balance_error",
    "aggregate_ohlcv",
]
