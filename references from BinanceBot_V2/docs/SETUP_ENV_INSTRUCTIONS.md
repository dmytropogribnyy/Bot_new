# Инструкция по настройке .env файла

## 🔐 Безопасное хранение API ключей

### Шаг 1: Создание .env файла

```bash
# Скопируйте пример файла
cp data/env.example .env

# Отредактируйте .env файл
nano .env
```

### Шаг 2: Добавьте ваши реальные API ключи

```bash
# Binance API Configuration
BINANCE_API_KEY=w2LwaYZq0x1t50ARb3IP69y9XQLssukr78dSnFcQF9XfbngkELA8hprvtTPAhX5S
BINANCE_API_SECRET=hmG7FVUeyQ8wK09596iDJE8ipQqWvpdlRZ8obwAnCwOa8qlZyHyO9fTvr6oQvMFD

# Telegram Configuration
TELEGRAM_TOKEN=7681205697:AAFB1FogqFMgoTgcu2vkDOmdcd-FYW4YdbU
TELEGRAM_CHAT_ID=383821734

# Logging Configuration
LOG_LEVEL=CLEAN
LOG_VERBOSITY=CLEAN
```

### Шаг 3: Настройка .gitignore

Добавьте в файл `.gitignore`:

```
# Environment variables
.env

# Runtime configuration with sensitive data
data/runtime_config.json

# Logs
logs/

# Database files
*.db
*.sqlite

# Cache files
__pycache__/
*.pyc
```

## 🎯 Настройки для разных сценариев

### Для продакшена (рекомендуется):
```bash
LOG_LEVEL=CLEAN
LOG_VERBOSITY=CLEAN
```

### Для разработки:
```bash
LOG_LEVEL=VERBOSE
LOG_VERBOSITY=VERBOSE
```

### Для отладки:
```bash
LOG_LEVEL=DEBUG
LOG_VERBOSITY=DEBUG
```

## 🔧 Проверка настройки

### Тест загрузки переменных окружения:

```python
import os
from dotenv import load_dotenv

# Загружаем .env файл
load_dotenv()

# Проверяем переменные
print(f"BINANCE_API_KEY: {'✅' if os.environ.get('BINANCE_API_KEY') else '❌'}")
print(f"BINANCE_API_SECRET: {'✅' if os.environ.get('BINANCE_API_SECRET') else '❌'}")
print(f"TELEGRAM_TOKEN: {'✅' if os.environ.get('TELEGRAM_TOKEN') else '❌'}")
print(f"TELEGRAM_CHAT_ID: {'✅' if os.environ.get('TELEGRAM_CHAT_ID') else '❌'}")
print(f"LOG_LEVEL: {os.environ.get('LOG_LEVEL', 'NOT_SET')}")
```

### Запуск теста конфигурации:

```bash
python -c "
from core.config import TradingConfig
config = TradingConfig()
errors = config.validate()
if errors:
    print('❌ Ошибки конфигурации:')
    for error in errors:
        print(f'  - {error}')
else:
    print('✅ Конфигурация корректна')
"
```

## 🚨 Важные предупреждения

### ⚠️ Безопасность:
1. **НИКОГДА не коммитьте .env файл в git**
2. **Храните .env файл в безопасном месте**
3. **Регулярно обновляйте API ключи**
4. **Используйте разные ключи для тестирования и продакшена**

### 🔒 Права доступа:
```bash
# Установите правильные права доступа
chmod 600 .env
```

### 📁 Структура файлов:
```
BinanceBot_V2/
├── .env                    # Ваши API ключи (НЕ в git)
├── data/
│   ├── env.example        # Пример файла
│   ├── runtime_config.json # Конфигурация без ключей
│   └── ...
└── ...
```

## 🧪 Тестирование

### 1. Тест подключения к Binance:
```bash
python test_api_connection.py
```

### 2. Тест Telegram бота:
```bash
python test_telegram_integration.py
```

### 3. Тест полной системы:
```bash
python test_full_startup.py
```

## 🔄 Обновление ключей

### Если нужно обновить API ключи:

1. **Создайте новые ключи в Binance**
2. **Обновите .env файл**
3. **Перезапустите бота**

```bash
# Остановите бота
pkill -f main.py

# Обновите .env файл
nano .env

# Запустите бота заново
python main.py
```

## 📊 Мониторинг

### Проверка статуса:
```bash
# Проверьте, что переменные загружены
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
print('Environment variables:')
for key in ['BINANCE_API_KEY', 'TELEGRAM_TOKEN', 'LOG_LEVEL']:
    value = os.environ.get(key, 'NOT_SET')
    status = '✅' if value != 'NOT_SET' else '❌'
    print(f'{key}: {status}')
"
```

## 🎯 Готово!

После выполнения всех шагов ваша система будет:
- ✅ Безопасно хранить API ключи
- ✅ Правильно загружать конфигурацию
- ✅ Готова к продакшену
- ✅ Иметь настраиваемое логирование

### Следующие шаги:
1. Запустите бота: `python main.py`
2. Проверьте логи: `tail -f logs/main.log`
3. Настройте мониторинг через Telegram
4. Начните торговлю с безопасной конфигурации
