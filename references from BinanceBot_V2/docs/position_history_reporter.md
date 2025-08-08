# Position History Reporter

## Обзор

Position History Reporter - это модуль для получения точной сводки позиций и торговых данных из Binance API. Он предназначен для перепроверки статистики по рану перед завершением бота.

## Основные возможности

### 📊 Получение данных из Binance API

- **User Trades** - история всех сделок пользователя
- **Position Risk** - информация о текущих позициях и рисках
- **Income History** - история доходов (funding fees, комиссии)
- **Account Info** - общая информация об аккаунте

### 📈 Анализ позиций

- Группировка сделок в позиции (вход/выход)
- Расчет реализованного PnL для каждой позиции
- Учет комиссий и funding fees
- Анализ по символам

### 📋 Генерация отчетов

- Детальная сводка по позициям
- Финансовые показатели
- Статистика производительности
- Анализ по символам

## Использование

### Основной класс

```python
from core.position_history_reporter import PositionHistoryReporter
from core.config import TradingConfig
from core.unified_logger import UnifiedLogger

# Создание репортера
config = TradingConfig.load_optimized_for_profit_target(0.7)
logger = UnifiedLogger(config)
reporter = PositionHistoryReporter(config, logger)

# Инициализация
await reporter.initialize()

# Генерация отчета
summary, positions = await reporter.generate_position_report(hours=24)

# Форматирование отчета
report = reporter.format_position_report(summary, positions)
print(report)

# Очистка
await reporter.cleanup()
```

### Telegram команда

```
/position_history [hours]
```

Где `hours` - количество часов для анализа (по умолчанию 24).

## API методы

### `get_user_trades()`
Получает историю сделок пользователя.

**Параметры:**
- `symbol` (optional) - символ для фильтрации
- `start_time` (optional) - время начала
- `end_time` (optional) - время окончания
- `limit` (optional) - максимальное количество записей

### `get_position_risk()`
Получает информацию о риске позиций.

### `get_income_history()`
Получает историю доходов (funding fees, комиссии).

### `get_account_info()`
Получает общую информацию об аккаунте.

### `generate_position_report(hours)`
Генерирует полный отчет о позициях.

**Параметры:**
- `hours` - количество часов для анализа

**Возвращает:**
- `PositionSummary` - сводка по позициям
- `List[TradePosition]` - список позиций

## Структуры данных

### TradePosition
```python
@dataclass
class TradePosition:
    symbol: str
    side: str  # 'buy' или 'sell'
    entry_price: float
    exit_price: float
    quantity: float
    entry_time: datetime
    exit_time: datetime
    entry_order_id: str
    exit_order_id: str
    entry_fee: float
    exit_fee: float
    realized_pnl: float
    hold_duration_minutes: float
```

### PositionSummary
```python
@dataclass
class PositionSummary:
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_pnl: float
    total_fees: float
    win_rate: float
    avg_profit_per_trade: float
    avg_loss_per_trade: float
    max_profit: float
    max_loss: float
    avg_hold_duration_minutes: float
    best_symbol: Optional[str]
    worst_symbol: Optional[str]
    symbol_performance: Dict[str, Dict[str, float]]
    funding_fees: float
    net_pnl: float
```

## Интеграция с основным ботом

### Автоматическое использование при остановке

При остановке бота (Ctrl+C, SIGTERM) автоматически генерируется финальный анализ с использованием Position History Reporter.

### Telegram интеграция

Добавлена команда `/position_history` для получения сводки позиций через Telegram.

## Тестирование

### Простой тест
```bash
python test_position_history.py
```

### Детальный тест
```bash
python scripts/test_position_report.py --hours 48
```

### Тест только API
```bash
python scripts/test_position_report.py --api-only
```

## Примеры отчетов

### Краткая сводка
```
📊 Position History Report (24h)

📈 Trading Summary:
• Total Trades: 15
• Winning Trades: 9
• Losing Trades: 6
• Win Rate: 60.0%

💰 Financial Summary:
• Total PnL: $12.45
• Total Fees: $3.20
• Funding Fees: $0.50
• Net PnL: $8.75

📊 Performance Metrics:
• Avg Profit/Trade: $2.15
• Avg Loss/Trade: -$1.80
• Max Profit: $5.20
• Max Loss: -$3.10
• Avg Hold Time: 8.5 min

🏆 Symbol Analysis:
• Best Symbol: BTCUSDT
• Worst Symbol: ETHUSDT
```

## Полезные Binance API эндпоинты

1. **GET /fapi/v1/userTrades** - сделки пользователя
2. **GET /fapi/v1/positionRisk** - информация о позициях
3. **GET /fapi/v1/income** - история доходов
4. **GET /fapi/v1/account** - информация об аккаунте

## Обработка ошибок

Модуль включает robust обработку ошибок:
- Retry механизм для API вызовов
- Graceful fallback при ошибках
- Подробное логирование
- Очистка ресурсов

## Производительность

- Кэширование API вызовов
- Rate limiting
- Асинхронная обработка
- Оптимизированные запросы

## Безопасность

- Использование API ключей из конфигурации
- Валидация параметров
- Безопасная обработка данных
- Логирование без чувствительной информации
