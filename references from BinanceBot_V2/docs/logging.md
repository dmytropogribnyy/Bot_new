# 📝 Система логирования BinanceBot_V2

## 🎯 Обзор

Система логирования обеспечивает централизованное отслеживание всех событий бота с цветным выводом, категоризацией и автоматической ротацией файлов.

## 🏗️ Архитектура

### UnifiedLogger

Основной компонент логирования, который:
- ✅ Поддерживает цветной вывод в консоль
- ✅ Записывает логи в файлы
- ✅ Сохраняет данные в SQLite базу
- ✅ Автоматически ротирует файлы
- ✅ Категоризирует события

### Структура логов

```
logs/
├── bot.log              # Основной лог
├── performance.log      # Лог производительности
├── trades.log          # Лог сделок
├── errors.log          # Лог ошибок
└── archive/            # Архив старых логов
    ├── bot_20240801.log
    └── bot_20240802.log
```

## 📊 Уровни логирования

### Основные уровни

| Уровень | Цвет | Описание | Пример |
|---------|------|----------|--------|
| `DEBUG` | 🔵 | Отладочная информация | `[DEBUG] Подключение к API` |
| `INFO` | ℹ️ | Информационные сообщения | `[INFO] Баланс: 100 USDC` |
| `WARNING` | ⚠️ | Предупреждения | `[WARNING] Высокий риск` |
| `ERROR` | ❌ | Ошибки | `[ERROR] Ошибка API` |
| `CRITICAL` | 🚨 | Критические ошибки | `[CRITICAL] Потеря соединения` |

### Специальные уровни

| Уровень | Цвет | Описание |
|---------|------|----------|
| `SUCCESS` | ✅ | Успешные операции |
| `TRADE` | 💰 | Торговые операции |
| `BALANCE` | 💰 | Операции с балансом |
| `EXCHANGE` | 🏦 | Операции с биржей |

## 🔧 Настройка логирования

### Конфигурация в config.py

```python
# Параметры логирования
db_path: str = "data/trading_log.db"
max_log_size_mb: int = 100
log_retention_days: int = 30
verbose_logging: bool = False
```

### Инициализация логгера

```python
from core.unified_logger import UnifiedLogger

# Создание логгера
logger = UnifiedLogger(
    config=config,
    db_path="data/trading_log.db",
    max_size_mb=100,
    retention_days=30
)
```

## 📝 Примеры использования

### Базовое логирование

```python
# Информационные сообщения
logger.log_event("MAIN", "INFO", "Бот запущен")

# Ошибки
logger.log_event("API", "ERROR", "Ошибка подключения к Binance")

# Успешные операции
logger.log_event("TRADE", "SUCCESS", "Сделка закрыта с прибылью $2.50")

# Торговые операции
logger.log_event("TRADE", "TRADE", "Открыта позиция BTCUSDC LONG")
```

### Логирование с контекстом

```python
# Логирование с дополнительными данными
logger.log_event(
    "TRADE",
    "TRADE",
    "Открыта позиция",
    extra={
        "symbol": "BTCUSDC",
        "side": "LONG",
        "size": 0.001,
        "price": 50000
    }
)
```

### Логирование производительности

```python
# Метрики производительности
logger.log_performance(
    "hourly_profit",
    2.5,
    {"trades": 5, "win_rate": 0.8}
)
```

## 📊 Категории событий

### Основные категории

| Категория | Описание | Примеры |
|-----------|----------|---------|
| `MAIN` | Основные события | Запуск, остановка, конфигурация |
| `API` | API операции | Подключения, запросы, ошибки |
| `TRADE` | Торговые операции | Открытие/закрытие позиций |
| `BALANCE` | Операции с балансом | Изменения баланса, переводы |
| `TELEGRAM` | Telegram события | Команды, уведомления |
| `SYSTEM` | Системные события | Мониторинг, оптимизация |
| `RISK` | Управление рисками | Stop Loss, Risk Manager |
| `PERFORMANCE` | Метрики производительности | PnL, статистика |

### Специальные категории

| Категория | Описание |
|-----------|----------|
| `WEBSOCKET` | WebSocket соединения |
| `ORDER` | Управление ордерами |
| `LEVERAGE` | Операции с плечом |
| `SYMBOL` | Выбор символов |
| `STRATEGY` | Торговые стратегии |

## 🗄️ База данных

### Структура таблиц

```sql
-- Таблица событий
CREATE TABLE events (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME,
    category TEXT,
    level TEXT,
    message TEXT,
    extra_data TEXT
);

-- Таблица производительности
CREATE TABLE performance (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME,
    metric_name TEXT,
    value REAL,
    metadata TEXT
);

-- Таблица сделок
CREATE TABLE trades (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME,
    symbol TEXT,
    side TEXT,
    size REAL,
    price REAL,
    pnl REAL
);
```

### Запросы к базе данных

```python
# Получение событий за последний час
events = logger.get_events(hours=1)

# Получение статистики сделок
trades = logger.get_trade_stats(days=7)

# Получение метрик производительности
performance = logger.get_performance_metrics(days=30)
```

## 🔍 Просмотр логов

### Консольный вывод

```bash
# Просмотр в реальном времени
tail -f logs/bot.log

# Поиск ошибок
grep "ERROR" logs/bot.log

# Поиск торговых операций
grep "TRADE" logs/bot.log

# Поиск по категории
grep "\[API\]" logs/bot.log
```

### Фильтрация логов

```bash
# Только ошибки
grep "\[ERROR\]" logs/bot.log

# Только успешные сделки
grep "\[SUCCESS\]" logs/bot.log

# Только баланс
grep "\[BALANCE\]" logs/bot.log
```

### Анализ логов

```bash
# Подсчет ошибок
grep -c "\[ERROR\]" logs/bot.log

# Статистика по категориям
grep -o "\[[A-Z]*\]" logs/bot.log | sort | uniq -c

# Поиск медленных операций
grep "slow" logs/bot.log
```

## 🔄 Ротация логов

### Автоматическая ротация

```python
# Настройки ротации
max_log_size_mb: int = 100      # Максимальный размер файла
log_retention_days: int = 30    # Время хранения логов
```

### Ручная ротация

```bash
# Архивирование текущего лога
mv logs/bot.log logs/archive/bot_$(date +%Y%m%d).log

# Создание нового лога
touch logs/bot.log

# Очистка старых логов
find logs/archive -name "*.log" -mtime +30 -delete
```

## 📈 Метрики и аналитика

### Встроенные метрики

```python
# Логирование метрик
logger.log_performance("hourly_profit", 2.5)
logger.log_performance("win_rate", 0.75)
logger.log_performance("trades_count", 15)
logger.log_performance("max_drawdown", -0.05)
```

### Кастомные метрики

```python
# Создание кастомных метрик
logger.log_performance(
    "custom_metric",
    value=0.85,
    metadata={
        "description": "Пользовательская метрика",
        "unit": "percentage"
    }
)
```

### Экспорт данных

```python
# Экспорт логов в JSON
logger.export_events(
    output_file="exports/events.json",
    days=7
)

# Экспорт метрик в CSV
logger.export_performance(
    output_file="exports/performance.csv",
    days=30
)
```

## 🛠️ Отладка

### Включение отладочного режима

```python
# В конфигурации
debug_mode: bool = True
verbose_logging: bool = True

# Или при запуске
python main.py --debug --verbose
```

### Отладочные команды

```bash
# Просмотр всех логов
cat logs/bot.log

# Поиск конкретной ошибки
grep "ConnectionError" logs/bot.log

# Анализ производительности
python utils/analyze_logs.py
```

## 🔒 Безопасность

### Маскирование чувствительных данных

```python
# API ключи автоматически маскируются
logger.log_event("API", "INFO", "Подключение к Binance")
# Вывод: [API] INFO Подключение к Binance (API_KEY: ***)

# Балансы округляются
logger.log_event("BALANCE", "INFO", f"Баланс: {balance:.2f} USDC")
```

### Очистка логов

```bash
# Удаление логов с чувствительными данными
python scripts/clean_logs.py

# Шифрование архивных логов
gpg -e logs/archive/bot_20240801.log
```

---

**💡 Совет**: Регулярно проверяйте логи для мониторинга работы бота и выявления проблем на ранней стадии.
