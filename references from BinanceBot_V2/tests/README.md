# 🧪 Тесты BinanceBot_V2

## 📁 Структура тестов

```
tests/
├── README.md                           # Этот файл
├── config/                             # Тесты конфигурации
│   ├── test_config_selection.py       # Выбор конфигурации
│   └── test_api_keys_verification.py  # Проверка API ключей
├── integration/                        # Интеграционные тесты
│   ├── final_comprehensive_test.py    # Полный интеграционный тест
│   ├── integration_test.py            # Основной интеграционный тест
│   └── strategy_integration_test.py   # Тест стратегий
├── api/                               # Тесты API
│   └── test_binance_connection.py     # Подключение к Binance
├── telegram/                          # Тесты Telegram
│   ├── test_telegram_simple.py        # Простой тест Telegram
│   ├── test_telegram_message.py       # Тест сообщений
│   ├── test_telegram_notifications.py # Тест уведомлений
│   └── telegram_commands_test.py      # Тест команд
├── system/                            # Системные тесты
│   ├── test_system_startup.py         # Тест запуска системы
│   ├── test_full_system.py            # Полный тест системы
│   ├── test_fee_calculation_system.py # Тест расчета комиссий
│   ├── test_emergency_shutdown_recovery.py # Тест экстренного выключения
│   ├── test_synchronization_system.py # Тест синхронизации
│   ├── test_timeout_system.py         # Тест таймаутов
│   ├── test_order_management_system.py # Тест управления ордерами
│   ├── test_stop_shutdown_commands.py # Тест команд остановки
│   ├── quick_stop_test.py             # Быстрый тест остановки
│   ├── simple_stop_test.py            # Простой тест остановки
│   └── final_audit_test.py            # Финальный аудит
└── utils/                             # Утилитарные тесты
    ├── test_logging_and_real_run.py   # Тест логирования
    ├── simple_test.py                  # Простой тест
    └── final_real_test.py             # Финальный реальный тест
```

## 🚀 Запуск тестов

### Все тесты
```bash
# Запуск всех тестов
python -m pytest tests/ -v

# Запуск с подробным выводом
python -m pytest tests/ -v -s
```

### По категориям
```bash
# Тесты конфигурации
python tests/config/test_config_selection.py
python tests/config/test_api_keys_verification.py

# Интеграционные тесты
python tests/integration/final_comprehensive_test.py
python tests/integration/integration_test.py

# Тесты API
python tests/api/test_binance_connection.py

# Тесты Telegram
python tests/telegram/test_telegram_simple.py
python tests/telegram/telegram_commands_test.py

# Системные тесты
python tests/system/test_system_startup.py
python tests/system/test_full_system.py
```

## 📋 Описание тестов

### 🔧 Конфигурация (`config/`)
- **`test_config_selection.py`**: Тестирует автоматический выбор конфигурации для разных целей прибыли ($0.5, $1.0, $2.0/час)
- **`test_api_keys_verification.py`**: Проверяет валидность API ключей для testnet и production

### 🔗 Интеграция (`integration/`)
- **`final_comprehensive_test.py`**: Полный интеграционный тест всех компонентов системы
- **`integration_test.py`**: Основной интеграционный тест
- **`strategy_integration_test.py`**: Тестирует интеграцию торговых стратегий

### 🌐 API (`api/`)
- **`test_binance_connection.py`**: Тестирует подключение к Binance API, проверяет баланс и статус аккаунта

### 📱 Telegram (`telegram/`)
- **`test_telegram_simple.py`**: Простой тест Telegram бота
- **`test_telegram_message.py`**: Тестирует отправку сообщений
- **`test_telegram_notifications.py`**: Тестирует систему уведомлений
- **`telegram_commands_test.py`**: Тестирует все Telegram команды

### ⚙️ Система (`system/`)
- **`test_system_startup.py`**: Тестирует запуск системы
- **`test_full_system.py`**: Полный тест системы
- **`test_fee_calculation_system.py`**: Тестирует расчет комиссий
- **`test_emergency_shutdown_recovery.py`**: Тестирует экстренное выключение
- **`test_synchronization_system.py`**: Тестирует синхронизацию данных
- **`test_timeout_system.py`**: Тестирует систему таймаутов
- **`test_order_management_system.py`**: Тестирует управление ордерами
- **`test_stop_shutdown_commands.py`**: Тестирует команды остановки
- **`quick_stop_test.py`**: Быстрый тест остановки
- **`simple_stop_test.py`**: Простой тест остановки
- **`final_audit_test.py`**: Финальный аудит системы

### 🛠️ Утилиты (`utils/`)
- **`test_logging_and_real_run.py`**: Тестирует логирование в реальном времени
- **`simple_test.py`**: Простой тест
- **`final_real_test.py`**: Финальный реальный тест

## 🎯 Ключевые тесты для $2/час

### Приоритетные тесты:
1. **`test_config_selection.py`** - проверяет выбор конфигурации для $2/час
2. **`test_binance_connection.py`** - проверяет подключение к API
3. **`final_comprehensive_test.py`** - полный интеграционный тест
4. **`test_telegram_simple.py`** - проверяет Telegram интеграцию

### Запуск ключевых тестов:
```bash
# Тест конфигурации для $2/час
python tests/config/test_config_selection.py

# Тест подключения к Binance
python tests/api/test_binance_connection.py

# Полный интеграционный тест
python tests/integration/final_comprehensive_test.py

# Тест Telegram
python tests/telegram/test_telegram_simple.py
```

## 📊 Результаты тестов

### ✅ Успешные тесты
- Конфигурация для $2/час выбрана корректно
- Подключение к Binance API работает
- Telegram интеграция функционирует
- Система запускается без ошибок

### ⚠️ Тесты требующие внимания
- Некоторые тесты могут требовать настройки API ключей
- Отдельные тесты могут зависеть от состояния сети

## 🔧 Настройка для тестов

### Переменные окружения
```bash
# API ключи для тестов
export BINANCE_TESTNET_API_KEY="your_testnet_key"
export BINANCE_TESTNET_API_SECRET="your_testnet_secret"
export BINANCE_PRODUCTION_API_KEY="your_production_key"
export BINANCE_PRODUCTION_API_SECRET="your_production_secret"

# Telegram для тестов
export TELEGRAM_BOT_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="your_chat_id"
```

### Конфигурация
```bash
# Копирование тестовой конфигурации
cp data/runtime_config_test.json data/runtime_config.json
```

---

**📅 Дата создания**: 3 августа 2024
**✅ Статус**: Тесты организованы и готовы к использованию
