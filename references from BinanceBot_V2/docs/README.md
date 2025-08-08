# 🚀 BinanceBot_V2 (OptiFlow HFT)

**Высокопроизводительный торговый бот для Binance USDC Futures с архитектурой OptiFlow HFT**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen.svg)]()

## 📋 Содержание

- [Обзор](#-обзор)
- [Основные особенности](#-основные-особенности)
- [Архитектура](#-архитектура)
- [Установка](#-установка)
- [Конфигурация](#-конфигурация)
- [Запуск](#-запуск)
- [Telegram команды](#-telegram-команды)
- [Тестирование](#-тестирование)
- [Мониторинг и метрики](#-мониторинг-и-метрики)
- [VPS развертывание](#-vps-развертывание)
- [Signal API интеграция](#-signal-api-интеграция)
- [Валидация и отчеты](#-валидация-и-отчеты)
- [Troubleshooting](#-troubleshooting)
- [Лицензия](#-лицензия)

## 🎯 Обзор

BinanceBot_V2 - это профессиональный торговый бот для Binance USDC Futures, построенный на архитектуре **OptiFlow HFT** (High-Frequency Trading). Бот предназначен для автоматической торговли с минимальным депозитом $250-350 USDC и целевой прибылью от $2/час.

### Ключевые преимущества:
- ⚡ **Высокая скорость исполнения** (WebSocket + REST API)
- 🧠 **Адаптивные стратегии** (Scalping, Grid, Microstructure)
- 📊 **Автоматическая оптимизация** (TP Optimizer, Leverage Manager)
- 📱 **Telegram управление** (полный набор команд)
- 🎯 **Управление рисками** (централизованная система)
- 📈 **Мониторинг производительности** (реальное время)

## ⭐ Основные особенности

### 🤖 Торговые стратегии
- **Scalping V1**: Быстрые сделки с высоким win rate
- **TP Optimizer**: Автоматическая подстройка Take Profit уровней
- **Grid Trading**: Сеточная торговля в боковых рынках
- **Microstructure**: Анализ Order Book Imbalance (OBI)

### 🔧 Системные компоненты
- **Leverage Manager**: Динамическое управление плечом
- **Performance Monitor**: Мониторинг системы и торговли
- **Risk Manager**: Централизованное управление рисками
- **Symbol Selector**: Умный выбор торговых пар
- **Rate Limiter**: Оптимизация API запросов

### 📱 Telegram интеграция
- Полное управление через Telegram бота
- Уведомления о сделках и событиях
- Команды для мониторинга и контроля
- Отчеты о производительности

## 🏗️ Архитектура

```
BinanceBot_V2/
├── core/                    # Основные компоненты
│   ├── config.py           # Конфигурация
│   ├── exchange_client.py  # API клиент
│   ├── trading_engine.py   # Торговый движок
│   ├── risk_manager.py     # Управление рисками
│   └── monitoring.py       # Мониторинг
├── strategies/             # Торговые стратегии
│   ├── base_strategy.py    # Базовая стратегия
│   ├── scalping_v1.py      # Скальпинг
│   └── tp_optimizer.py     # TP оптимизатор
├── telegram/               # Telegram бот
├── utils/                  # Утилиты
└── deployment/             # VPS развертывание
```

## 🚀 Установка

### Предварительные требования
- Python 3.10+
- Git
- Binance аккаунт с API ключами
- Telegram бот токен

### 1. Клонирование репозитория
```bash
git clone https://github.com/your-username/BinanceBot_V2.git
cd BinanceBot_V2
```

### 2. Создание виртуального окружения
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows
```

### 3. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 4. Настройка конфигурации
```bash
# Скопируйте пример конфигурации
cp data/runtime_config.example.json data/runtime_config.json

# Отредактируйте конфигурацию
nano data/runtime_config.json
```

## ⚙️ Конфигурация

### Основные параметры (data/runtime_config.json)

```json
{
  "binance_api_key": "YOUR_API_KEY",
  "binance_secret_key": "YOUR_SECRET_KEY",
  "telegram_token": "YOUR_BOT_TOKEN",
  "telegram_chat_id": "YOUR_CHAT_ID",

  "trading_params": {
    "max_concurrent_positions": 5,
    "base_risk_pct": 0.12,
    "sl_percent": 0.006,
    "step_tp_levels": [0.004, 0.008, 0.012]
  },

  "performance_targets": {
    "min_hourly_profit": 2.0,
    "target_win_rate": 0.55,
    "max_drawdown": 0.15
  }
}
```

### Leverage Map (data/leverage_map.json)
```json
{
  "default_leverage": 5,
  "symbols": {
    "BTCUSDC": {"leverage": 10, "risk_level": "medium"},
    "ETHUSDC": {"leverage": 8, "risk_level": "medium"}
  }
}
```

## ▶️ Запуск

### Локальный запуск
```bash
# Активируйте виртуальное окружение
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows

# Запустите бота
python main.py
```

### VPS запуск (рекомендуется)
```bash
# Используйте tmux для фонового запуска
./deployment/tmux_start.sh

# Или systemd сервис
sudo systemctl start binance-bot
sudo systemctl enable binance-bot
```

## 📱 Telegram команды

### Основные команды
| Команда | Описание |
|---------|----------|
| `/start` | Запуск бота |
| `/status` | Статус бота и позиции |
| `/positions` | Активные позиции |
| `/balance` | Баланс аккаунта |
| `/performance` | Отчет о производительности |

### Управление торговлей
| Команда | Описание |
|---------|----------|
| `/pause` | Приостановить торговлю |
| `/resume` | Возобновить торговлю |
| `/close_position SYMBOL` | Закрыть позицию |
| `/config` | Показать конфигурацию |

### Leverage управление
| Команда | Описание |
|---------|----------|
| `/leverage_report` | Отчет по плечу |
| `/approve_leverage SYMBOL LEVERAGE` | Изменить плечо |
| `/refresh_symbols` | Обновить символы |

### Дополнительные команды
| Команда | Описание |
|---------|----------|
| `/help` | Справка по командам |
| `/restart` | Перезапуск бота |
| `/shutdown` | Остановка бота |

## 🧪 Тестирование

### Запуск всех тестов
```bash
# Загрузите алиасы для удобства
source scripts/ruff_commands.sh

# Запустите все тесты
python -m pytest tests/ -v

# Или отдельные тесты
python integration_test.py
python strategy_integration_test.py
python telegram_commands_test.py
```

### Проверка кода
```bash
# Проверка с Ruff
ruff_check

# Исправление проблем
ruff_fix

# Форматирование
ruff_format

# Полная проверка
ruff_full
```

### VS Code задачи
- `Ctrl+Shift+P` → `Tasks: Run Task`
- Выберите нужную задачу:
  - `Ruff: Check` - Проверка кода
  - `Run Tests` - Запуск тестов
  - `Integration Test` - Интеграционные тесты

## 📊 Мониторинг и метрики

### Системные метрики
- CPU и Memory usage
- Network latency до Binance
- API rate limit статус

### Торговые метрики
- PnL (прибыль/убыток)
- Win Rate (% успешных сделок)
- Количество сделок в час
- Средняя прибыль на сделку

### Доступ к метрикам
```bash
# Через Telegram
/performance 1    # За день
/performance 7    # За неделю
/performance 30   # За месяц

# Через API (для внешних платформ)
curl http://localhost:8080/metrics
```

## 🌐 VPS развертывание

### Автоматическая установка
```bash
# Скачайте скрипт установки
wget https://raw.githubusercontent.com/your-username/BinanceBot_V2/main/deployment/vps_setup.sh
chmod +x vps_setup.sh
./vps_setup.sh
```

### Ручная установка
```bash
# 1. Обновите систему
sudo apt update && sudo apt upgrade -y

# 2. Установите зависимости
sudo apt install -y python3 python3-pip git tmux

# 3. Клонируйте репозиторий
git clone https://github.com/your-username/BinanceBot_V2.git
cd BinanceBot_V2

# 4. Создайте виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# 5. Установите зависимости
pip install -r requirements.txt

# 6. Настройте конфигурацию
cp data/runtime_config.example.json data/runtime_config.json
nano data/runtime_config.json

# 7. Запустите через tmux
tmux new-session -d -s bot 'python main.py'

# 8. Или через systemd
sudo cp deployment/systemd/binance-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable binance-bot
sudo systemctl start binance-bot
```

### Управление на VPS
```bash
# Проверить статус
sudo systemctl status binance-bot

# Посмотреть логи
sudo journalctl -u binance-bot -f

# Перезапустить
sudo systemctl restart binance-bot

# Остановить
sudo systemctl stop binance-bot
```

## 🔌 Signal API интеграция

### Для копитрейдинга
```python
# Пример интеграции с внешними сигналами
from core.signal_processor import SignalProcessor

signal_processor = SignalProcessor(config, exchange, logger)

# Обработка внешнего сигнала
signal = {
    "symbol": "BTCUSDC",
    "side": "BUY",
    "entry_price": 50000,
    "sl_price": 49500,
    "tp_price": 51000,
    "confidence": 0.8
}

await signal_processor.process_external_signal(signal)
```

### Для подписок на сигналы
```python
# Настройка webhook для получения сигналов
@app.route('/webhook/signal', methods=['POST'])
async def handle_signal():
    signal_data = request.json
    await signal_processor.process_signal(signal_data)
    return {"status": "processed"}
```

## 📈 Валидация и отчеты

### Метрики для инвесторов
- **Sharpe Ratio**: Мера риск-скорректированной доходности
- **Maximum Drawdown**: Максимальная просадка
- **Win Rate**: Процент успешных сделок
- **Profit Factor**: Отношение прибыли к убыткам
- **Average Trade Duration**: Средняя продолжительность сделки

### Генерация отчетов
```bash
# Генерация отчета о производительности
python utils/generate_report.py --days 30 --format pdf

# Экспорт данных для анализа
python utils/export_data.py --start-date 2024-01-01 --end-date 2024-01-31
```

### API для внешних платформ
```python
# REST API для получения метрик
from fastapi import FastAPI
from core.api_server import APIServer

app = FastAPI()
api_server = APIServer(config, logger)

@app.get("/metrics/performance")
async def get_performance():
    return await api_server.get_performance_metrics()

@app.get("/metrics/positions")
async def get_positions():
    return await api_server.get_active_positions()
```

### Валидация на платформах
- **Copy Trading Platforms**: Интеграция через API
- **Signal Marketplaces**: Экспорт сигналов
- **Portfolio Trackers**: Отправка метрик
- **Social Trading**: Публикация результатов

## 🔧 Troubleshooting

### Частые проблемы

#### 1. Ошибки подключения к Binance
```bash
# Проверьте API ключи
python test_api.py

# Проверьте сетевую связность
ping fapi.binance.com
```

#### 2. Проблемы с Telegram
```bash
# Проверьте токен бота
curl https://api.telegram.org/bot<YOUR_TOKEN>/getMe

# Проверьте chat_id
curl https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
```

#### 3. Ошибки в логах
```bash
# Просмотр логов
tail -f logs/bot.log

# Очистка кэша
python scripts/clean_cache.py
```

#### 4. Проблемы с производительностью
```bash
# Проверка системных ресурсов
python utils/performance_check.py

# Оптимизация настроек
python utils/optimize_config.py
```

### Полезные команды
```bash
# Проверка статуса всех компонентов
python final_comprehensive_test.py

# Тест Telegram бота
python test_telegram_message.py

# Проверка конфигурации
python utils/validators.py
```

## 📄 Лицензия

Этот проект распространяется под лицензией MIT. См. файл [LICENSE](LICENSE) для подробностей.

## 🤝 Поддержка

### Контакты
- **Email**: support@binancebot.com
- **Telegram**: @BinanceBotSupport
- **GitHub Issues**: [Создать issue](https://github.com/your-username/BinanceBot_V2/issues)

### Документация
- [Полная документация](docs/)
- [Быстрый старт](docs/installation.md)
- [Telegram команды](docs/telegram-commands.md)
- [Конфигурация](docs/configuration.md)

---

**⚠️ Дисклеймер**: Торговля криптовалютами связана с высокими рисками. Используйте этот бот на свой страх и риск. Авторы не несут ответственности за возможные финансовые потери.

**📊 Статус проекта**:
- ✅ **Production Ready**: Да
- 🚀 **Последнее обновление**: 3 августа 2024
- 🎯 **Целевая прибыль**: $2/час
- 🛡️ **Уровень риска**: 0.06% на сделку
