# ⚙️ Конфигурация BinanceBot_V2

## 📋 Обзор конфигурации

Система использует единый класс `TradingConfig` для управления всеми параметрами. Конфигурация загружается из JSON файлов и поддерживает автоматический выбор оптимальных настроек.

## 🗂️ Файлы конфигурации

### Основные файлы

| Файл | Описание | Использование |
|------|----------|---------------|
| `data/runtime_config.json` | Основная конфигурация | Продакшен |
| `data/runtime_config_aggressive.json` | Агрессивная торговля | Высокая прибыль |
| `data/runtime_config_safe.json` | Безопасная торговля | Минимальный риск |
| `data/runtime_config_test.json` | Тестовая торговля | Быстрые сделки |

### Структура конфигурации

```json
{
  "api_key": "ваш_api_key",
  "api_secret": "ваш_api_secret",
  "telegram_token": "ваш_telegram_token",
  "telegram_chat_id": "ваш_chat_id",

  "trading_params": {
    "max_concurrent_positions": 3,
    "base_risk_pct": 0.06,
    "sl_percent": 0.01,
    "step_tp_levels": [0.005, 0.01, 0.015]
  },

  "performance_targets": {
    "profit_target_hourly": 2.0,
    "min_win_rate": 0.65,
    "max_daily_loss": 20.0
  }
}
```

## 🎯 Параметры торговли

### Основные параметры

| Параметр | Значение | Описание |
|----------|----------|----------|
| `max_concurrent_positions` | 3 | Максимум одновременных позиций |
| `base_risk_pct` | 0.06 | Базовый риск на сделку (6%) |
| `sl_percent` | 0.01 | Stop Loss процент (1%) |
| `leverage_default` | 5 | Базовое кредитное плечо |

### Take Profit уровни

```json
{
  "step_tp_levels": [0.005, 0.01, 0.015],
  "step_tp_sizes": [0.5, 0.3, 0.2]
}
```

- **Уровень 1**: 0.5% прибыли (50% позиции)
- **Уровень 2**: 1.0% прибыли (30% позиции)
- **Уровень 3**: 1.5% прибыли (20% позиции)

### Временные параметры

| Параметр | Значение | Описание |
|----------|----------|----------|
| `max_hold_minutes` | 25 | Максимальное время удержания |
| `soft_exit_minutes` | 12 | Время мягкого выхода |
| `weak_position_minutes` | 35 | Время слабой позиции |

## 📊 Целевые показатели

### Прибыльность

```json
{
  "profit_target_hourly": 2.0,
  "profit_target_daily": 50.0,
  "min_win_rate": 0.65,
  "max_daily_loss": 20.0
}
```

### Управление рисками

```json
{
  "max_drawdown_daily": 30.0,
  "emergency_stop_threshold": -1.8,
  "risky_loss_threshold": -1.2,
  "trailing_stop_drawdown": 0.25
}
```

## 🔧 Конфигурации по уровням риска

### 🟢 Безопасная конфигурация (`safe.json`)

```json
{
  "max_concurrent_positions": 1,
  "base_risk_pct": 0.005,
  "sl_percent": 0.008,
  "profit_target_hourly": 0.5,
  "max_hold_minutes": 15,
  "step_tp_levels": [0.003, 0.006, 0.009]
}
```

**Характеристики:**
- Минимальный риск (0.5% на сделку)
- Целевая прибыль: $0.5/час
- Короткие позиции (15 минут)
- Консервативные TP уровни

### 🟡 Тестовая конфигурация (`test.json`)

```json
{
  "max_concurrent_positions": 1,
  "base_risk_pct": 0.01,
  "sl_percent": 0.01,
  "profit_target_hourly": 1.0,
  "max_hold_minutes": 8,
  "step_tp_levels": [0.004, 0.008, 0.012]
}
```

**Характеристики:**
- Средний риск (1% на сделку)
- Целевая прибыль: $1.0/час
- Быстрые сделки (8 минут)
- Умеренные TP уровни

### 🔴 Агрессивная конфигурация (`aggressive.json`)

```json
{
  "max_concurrent_positions": 5,
  "base_risk_pct": 0.15,
  "sl_percent": 0.012,
  "profit_target_hourly": 2.0,
  "max_hold_minutes": 25,
  "step_tp_levels": [0.005, 0.01, 0.015]
}
```

**Характеристики:**
- Высокий риск (15% на сделку)
- Целевая прибыль: $2.0/час
- Длительные позиции (25 минут)
- Агрессивные TP уровни

## 🤖 Telegram настройки

### Уведомления

```json
{
  "telegram_enabled": true,
  "telegram_error_notifications": true,
  "telegram_trade_notifications": true,
  "telegram_notification_levels": {
    "trades": true,
    "errors": true,
    "warnings": true,
    "info": false,
    "debug": false,
    "tp_sl": true,
    "balance": true,
    "performance": true
  }
}
```

### Администраторы

```json
{
  "telegram_admin_users": [123456789],
  "telegram_chat_id": "ваш_chat_id"
}
```

## 🔄 Автоматический выбор конфигурации

### По целевой прибыли

```python
# Автоматический выбор на основе цели $2/час
config = TradingConfig.load_optimized_for_profit_target(2.0)
```

### По уровню риска

```python
# Выбор конфигурации по уровню риска
def select_config_by_risk(risk_level):
    configs = {
        "low": "data/runtime_config_safe.json",
        "medium": "data/runtime_config_test.json",
        "high": "data/runtime_config_aggressive.json"
    }
    return configs.get(risk_level, "data/runtime_config_safe.json")
```

## 📈 Динамическая оптимизация

### Leverage Map

```json
{
  "default_leverage": 5,
  "symbols": {
    "BTCUSDC": {"leverage": 10, "risk_level": "medium"},
    "ETHUSDC": {"leverage": 8, "risk_level": "medium"},
    "ADAUSDC": {"leverage": 5, "risk_level": "low"}
  }
}
```

### Symbol Selection

```json
{
  "max_symbols_to_trade": 15,
  "min_volume_24h_usdc": 5000000.0,
  "min_atr_percent": 0.4,
  "symbol_score_weights": {
    "volume": 30,
    "volatility": 25,
    "trend": 20,
    "win_rate": 15,
    "avg_pnl": 10
  }
}
```

## 🔍 Валидация конфигурации

### Проверка параметров

```python
# Валидация конфигурации
errors = config.validate()
if errors:
    print("❌ Ошибки конфигурации:")
    for error in errors:
        print(f"  - {error}")
```

### Проверка API ключей

```python
# Проверка API ключей для текущего режима
api_errors = config.validate_api_credentials()
if api_errors:
    print("❌ Ошибки API ключей:")
    for error in api_errors:
        print(f"  - {error}")
```

## 🛠️ Изменение конфигурации

### Через код

```python
# Изменение параметров во время выполнения
config.base_risk_pct = 0.08
config.max_concurrent_positions = 5
config.profit_target_hourly = 3.0
```

### Через файл

```bash
# Копирование конфигурации
cp data/runtime_config_aggressive.json data/runtime_config.json

# Редактирование
nano data/runtime_config.json
```

### Через Telegram

```
/config show          # Показать текущую конфигурацию
/config risk 0.08     # Изменить риск
/config positions 5   # Изменить количество позиций
/config save          # Сохранить изменения
```

## 📊 Мониторинг конфигурации

### Статистика

```python
# Получение информации о конфигурации
summary = config.get_summary()
print(f"Режим: {summary['exchange_mode']}")
print(f"Макс. позиций: {summary['max_positions']}")
print(f"Базовый риск: {summary['base_risk_pct']*100:.2f}%")
```

### Целевые показатели

```python
# Информация о целях прибыльности
profit_info = config.get_profit_target_info()
print(f"Целевая прибыль в час: ${profit_info['profit_target_hourly']}")
print(f"Уровень риска: {profit_info['risk_level']}")
```

---

**💡 Совет**: Начните с безопасной конфигурации и постепенно увеличивайте риск по мере накопления опыта.
