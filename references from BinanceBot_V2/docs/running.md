# 🚀 Запуск BinanceBot_V2

## 📋 Предварительные требования

Перед запуском убедитесь, что:
- ✅ Установлены все зависимости
- ✅ Настроены API ключи
- ✅ Создан Telegram бот
- ✅ Выбрана конфигурация

## 🎯 Способы запуска

### 1. Базовый запуск

```bash
# Активируйте виртуальное окружение
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows

# Запуск бота
python main.py
```

### 2. Запуск с параметрами

```bash
# Запуск с автоматическим выбором конфигурации
python main.py --profit-target 2.0

# Запуск в тестовом режиме
python main.py --testnet

# Запуск с подробным логированием
python main.py --verbose

# Запуск с отладкой
python main.py --debug
```

### 3. Запуск через скрипт

```bash
# Использование скрипта запуска
./start_bot.py

# Запуск с мониторингом
./start_bot.py --monitor
```

## 🔧 Параметры командной строки

| Параметр | Описание | Пример |
|----------|----------|--------|
| `--profit-target VALUE` | Целевая прибыль в час | `--profit-target 2.0` |
| `--testnet` | Тестовый режим | `--testnet` |
| `--verbose` | Подробное логирование | `--verbose` |
| `--debug` | Режим отладки | `--debug` |
| `--config FILE` | Файл конфигурации | `--config data/runtime_config_safe.json` |
| `--dry-run` | Тестовый режим без торговли | `--dry-run` |

## 📱 Запуск через Telegram

После запуска бота используйте команды в Telegram:

```
/start          # Запуск бота
/status         # Проверка статуса
/balance        # Проверка баланса
/positions      # Активные позиции
```

## 🖥️ VPS запуск

### Через tmux (рекомендуется)

```bash
# Создание новой сессии
tmux new-session -d -s bot 'python main.py'

# Подключение к сессии
tmux attach-session -t bot

# Отключение от сессии (Ctrl+B, затем D)
# Сессия продолжит работать в фоне
```

### Через systemd

```bash
# Копирование сервиса
sudo cp deployment/systemd/binance-bot.service /etc/systemd/system/

# Перезагрузка systemd
sudo systemctl daemon-reload

# Включение автозапуска
sudo systemctl enable binance-bot

# Запуск сервиса
sudo systemctl start binance-bot

# Проверка статуса
sudo systemctl status binance-bot
```

### Через screen

```bash
# Создание новой сессии
screen -S bot

# Запуск бота
python main.py

# Отключение (Ctrl+A, затем D)
# Подключение обратно: screen -r bot
```

## 🔍 Мониторинг запуска

### Проверка логов

```bash
# Просмотр логов в реальном времени
tail -f logs/bot.log

# Просмотр последних 100 строк
tail -n 100 logs/bot.log

# Поиск ошибок
grep "ERROR" logs/bot.log
```

### Проверка процессов

```bash
# Поиск процесса бота
ps aux | grep python

# Проверка использования ресурсов
htop
```

### Проверка подключений

```bash
# Проверка подключения к Binance
curl -I https://fapi.binance.com

# Проверка Telegram бота
curl https://api.telegram.org/bot<YOUR_TOKEN>/getMe
```

## 🛠️ Устранение проблем

### Проблемы с запуском

#### 1. Ошибка импорта модулей

```bash
# Проверка установки зависимостей
pip list | grep ccxt

# Переустановка зависимостей
pip install -r requirements.txt --force-reinstall
```

#### 2. Ошибки конфигурации

```bash
# Проверка конфигурации
python -c "from core.config import TradingConfig; config = TradingConfig(); print('✅ Конфигурация загружена')"

# Валидация конфигурации
python test_config_selection.py
```

#### 3. Проблемы с API ключами

```bash
# Тест API ключей
python test_api_keys_verification.py

# Проверка подключения к Binance
python test_binance_connection.py
```

### Проблемы с Telegram

```bash
# Тест Telegram бота
python test_telegram_simple.py

# Проверка токена
curl https://api.telegram.org/bot<YOUR_TOKEN>/getMe
```

### Проблемы с производительностью

```bash
# Проверка системных ресурсов
python utils/performance.py

# Очистка кэша
python scripts/clean_cache.py
```

## 🔄 Перезапуск

### Graceful перезапуск

```bash
# Остановка через Telegram
/stop

# Или через сигнал
kill -TERM <PID>

# Запуск заново
python main.py
```

### Принудительный перезапуск

```bash
# Остановка процесса
pkill -f "python main.py"

# Очистка портов
lsof -ti:8080 | xargs kill -9

# Запуск заново
python main.py
```

## 📊 Автоматизация

### Скрипт автозапуска

Создайте файл `auto_start.sh`:

```bash
#!/bin/bash
cd /path/to/BinanceBot_V2
source venv/bin/activate
python main.py >> logs/auto_start.log 2>&1
```

### Cron задача

```bash
# Добавление в crontab
crontab -e

# Добавьте строку для автозапуска при перезагрузке
@reboot /path/to/BinanceBot_V2/auto_start.sh
```

## 🔒 Безопасность

### Рекомендации по запуску

1. **Используйте VPS** для стабильной работы
2. **Настройте firewall** для защиты
3. **Используйте отдельный аккаунт** для бота
4. **Регулярно обновляйте** систему
5. **Мониторьте логи** на предмет ошибок

### Переменные окружения

```bash
# Установка переменных окружения
export BINANCE_API_KEY="ваш_ключ"
export BINANCE_API_SECRET="ваш_секрет"
export TELEGRAM_BOT_TOKEN="ваш_токен"

# Запуск с переменными
python main.py
```

## 📈 Оптимизация

### Настройка производительности

```bash
# Увеличение лимитов файлов
ulimit -n 65536

# Оптимизация Python
export PYTHONOPTIMIZE=1

# Запуск с оптимизацией
python -O main.py
```

### Мониторинг ресурсов

```bash
# Установка мониторинга
pip install psutil

# Запуск с мониторингом
python main.py --monitor-resources
```

---

**✅ Готово!** Бот запущен и готов к работе. Используйте Telegram команды для управления и мониторинга.
