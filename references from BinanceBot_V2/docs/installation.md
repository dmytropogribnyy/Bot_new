# 🚀 Установка и настройка BinanceBot_V2

## 📋 Требования

### Системные требования
- **Python**: 3.10+
- **ОС**: Windows 10+, Linux, macOS
- **RAM**: Минимум 2GB
- **Интернет**: Стабильное соединение

### Торговые требования
- **Binance аккаунт** с API ключами
- **Telegram бот** токен
- **Минимальный депозит**: $250-350 USDC
- **Доступ к USDC-M Futures**

## 🛠️ Установка

### 1. Клонирование репозитория

```bash
git clone https://github.com/your-username/BinanceBot_V2.git
cd BinanceBot_V2
```

### 2. Создание виртуального окружения

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Проверка установки

```bash
python -c "import ccxt; print('✅ Зависимости установлены')"
```

## ⚙️ Настройка

### 1. Создание конфигурационного файла

```bash
cp data/runtime_config.example.json data/runtime_config.json
```

### 2. Настройка API ключей

Отредактируйте файл `data/runtime_config.json`:

```json
{
  "api_key": "ваш_binance_api_key",
  "api_secret": "ваш_binance_api_secret",
  "telegram_token": "ваш_telegram_bot_token",
  "telegram_chat_id": "ваш_chat_id",

  "trading_params": {
    "max_concurrent_positions": 3,
    "base_risk_pct": 0.06,
    "sl_percent": 0.01,
    "step_tp_levels": [0.005, 0.01, 0.015]
  }
}
```

### 3. Получение API ключей Binance

1. Войдите в аккаунт Binance
2. Перейдите в **API Management**
3. Создайте новый API ключ
4. Включите **Futures Trading**
5. Скопируйте **API Key** и **Secret Key**

### 4. Создание Telegram бота

1. Найдите @BotFather в Telegram
2. Отправьте команду `/newbot`
3. Следуйте инструкциям
4. Скопируйте токен бота

### 5. Получение Chat ID

1. Добавьте бота в чат
2. Отправьте сообщение боту
3. Перейдите по ссылке: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
4. Найдите `chat_id` в ответе

## 🔧 Конфигурации

### Доступные конфигурации

| Конфигурация | Риск | Целевая прибыль | Описание |
|--------------|------|-----------------|----------|
| `safe.json` | 0.5% | $0.5/час | Безопасная торговля |
| `test.json` | 1.0% | $1.0/час | Тестовая торговля |
| `aggressive.json` | 2.0% | $2.0/час | Активная торговля |

### Выбор конфигурации

```bash
# Автоматический выбор на основе цели
python main.py --profit-target 2.0

# Ручной выбор конфигурации
cp data/runtime_config_aggressive.json data/runtime_config.json
```

## 🧪 Тестирование

### 1. Проверка подключения

```bash
python test_binance_connection.py
```

### 2. Тест Telegram бота

```bash
python test_telegram_message.py
```

### 3. Полный тест системы

```bash
python final_comprehensive_test.py
```

## 🚀 Первый запуск

### 1. Запуск в тестовом режиме

```bash
python main.py --testnet
```

### 2. Запуск в продакшене

```bash
python main.py
```

### 3. Запуск с мониторингом

```bash
python main.py --verbose
```

## 📱 Telegram команды

После запуска используйте команды в Telegram:

- `/start` - Запуск бота
- `/status` - Статус системы
- `/balance` - Баланс аккаунта
- `/positions` - Активные позиции
- `/help` - Справка по командам

## 🔍 Устранение неполадок

### Проблемы с API ключами

```bash
# Проверка API ключей
python test_api_keys_verification.py
```

### Проблемы с Telegram

```bash
# Тест Telegram бота
python test_telegram_simple.py
```

### Проблемы с подключением

```bash
# Проверка сети
ping fapi.binance.com
```

## 📊 Мониторинг

### Логи

```bash
# Просмотр логов
tail -f logs/bot.log
```

### Метрики

```bash
# Проверка производительности
python utils/performance.py
```

## 🔒 Безопасность

### Рекомендации

1. **Используйте отдельный аккаунт** для бота
2. **Ограничьте права API** только на Futures Trading
3. **Не делитесь API ключами**
4. **Регулярно обновляйте ключи**
5. **Используйте VPS** для стабильной работы

### Переменные окружения

```bash
# Установка переменных окружения
export BINANCE_API_KEY="ваш_ключ"
export BINANCE_API_SECRET="ваш_секрет"
export TELEGRAM_BOT_TOKEN="ваш_токен"
```

---

**✅ Готово!** Бот настроен и готов к работе. Следуйте инструкциям в [документации по запуску](running.md) для начала торговли.
