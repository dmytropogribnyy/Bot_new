# 📱 Telegram команды BinanceBot_V2

## 🎯 Обзор

Telegram бот предоставляет полное управление торговым ботом через удобный интерфейс. Все команды поддерживают как обычных пользователей, так и администраторов.

## 🚀 Основные команды

### Статус и информация

| Команда | Описание | Пример |
|---------|----------|--------|
| `/start` | Запуск бота и приветствие | `/start` |
| `/status` | Статус бота и системы | `/status` |
| `/help` | Справка по командам | `/help` |
| `/version` | Версия бота | `/version` |

### Баланс и финансы

| Команда | Описание | Пример |
|---------|----------|--------|
| `/balance` | Баланс аккаунта | `/balance` |
| `/balance_detailed` | Подробный баланс | `/balance_detailed` |
| `/pnl` | Прибыль/убыток | `/pnl` |
| `/pnl_daily` | Дневная прибыль | `/pnl_daily` |

### Позиции и торговля

| Команда | Описание | Пример |
|---------|----------|--------|
| `/positions` | Активные позиции | `/positions` |
| `/positions_detailed` | Подробные позиции | `/positions_detailed` |
| `/close_position SYMBOL` | Закрыть позицию | `/close_position BTCUSDC` |
| `/close_all` | Закрыть все позиции | `/close_all` |

## 🔧 Управление торговлей

### Контроль торговли

| Команда | Описание | Пример |
|---------|----------|--------|
| `/pause` | Приостановить торговлю | `/pause` |
| `/resume` | Возобновить торговлю | `/resume` |
| `/stop` | Остановить бота | `/stop` |
| `/restart` | Перезапустить бота | `/restart` |

### Конфигурация

| Команда | Описание | Пример |
|---------|----------|--------|
| `/config` | Показать конфигурацию | `/config` |
| `/config_show` | Подробная конфигурация | `/config_show` |
| `/config_risk VALUE` | Изменить риск | `/config_risk 0.08` |
| `/config_positions VALUE` | Изменить позиции | `/config_positions 5` |
| `/config_save` | Сохранить изменения | `/config_save` |

## 📊 Отчеты и аналитика

### Производительность

| Команда | Описание | Пример |
|---------|----------|--------|
| `/performance` | Отчет о производительности | `/performance` |
| `/performance 1` | За день | `/performance 1` |
| `/performance 7` | За неделю | `/performance 7` |
| `/performance 30` | За месяц | `/performance 30` |

### Статистика

| Команда | Описание | Пример |
|---------|----------|--------|
| `/stats` | Общая статистика | `/stats` |
| `/stats_trades` | Статистика сделок | `/stats_trades` |
| `/stats_symbols` | Статистика символов | `/stats_symbols` |
| `/stats_hourly` | Почасовая статистика | `/stats_hourly` |

## 🎛️ Leverage управление

### Отчеты по плечу

| Команда | Описание | Пример |
|---------|----------|--------|
| `/leverage_report` | Отчет по плечу | `/leverage_report` |
| `/leverage_symbols` | Плечо по символам | `/leverage_symbols` |
| `/leverage_optimization` | Оптимизация плеча | `/leverage_optimization` |

### Изменение плеча

| Команда | Описание | Пример |
|---------|----------|--------|
| `/approve_leverage SYMBOL LEVERAGE` | Изменить плечо | `/approve_leverage BTCUSDC 10` |
| `/leverage_all VALUE` | Плечо для всех | `/leverage_all 5` |
| `/leverage_reset` | Сбросить плечо | `/leverage_reset` |

## 🔍 Мониторинг и диагностика

### Система

| Команда | Описание | Пример |
|---------|----------|--------|
| `/system_status` | Статус системы | `/system_status` |
| `/system_health` | Здоровье системы | `/system_health` |
| `/system_logs` | Последние логи | `/system_logs` |
| `/system_restart` | Перезапуск системы | `/system_restart` |

### Символы

| Команда | Описание | Пример |
|---------|----------|--------|
| `/symbols` | Список символов | `/symbols` |
| `/symbols_active` | Активные символы | `/symbols_active` |
| `/refresh_symbols` | Обновить символы | `/refresh_symbols` |
| `/symbol_info SYMBOL` | Информация о символе | `/symbol_info BTCUSDC` |

## 🛡️ Безопасность

### IP мониторинг

| Команда | Описание | Пример |
|---------|----------|--------|
| `/ip_status` | Статус IP | `/ip_status` |
| `/ip_change` | Изменения IP | `/ip_change` |
| `/ip_whitelist` | Белый список IP | `/ip_whitelist` |

### Экстренные команды

| Команда | Описание | Пример |
|---------|----------|--------|
| `/emergency_stop` | Экстренная остановка | `/emergency_stop` |
| `/emergency_close` | Экстренное закрытие | `/emergency_close` |
| `/shutdown` | Полная остановка | `/shutdown` |

## 📈 Административные команды

### Только для администраторов

| Команда | Описание | Пример |
|---------|----------|--------|
| `/admin_status` | Статус админа | `/admin_status` |
| `/admin_users` | Список админов | `/admin_users` |
| `/admin_add USER_ID` | Добавить админа | `/admin_add 123456789` |
| `/admin_remove USER_ID` | Удалить админа | `/admin_remove 123456789` |

### Настройки уведомлений

| Команда | Описание | Пример |
|---------|----------|--------|
| `/notifications` | Статус уведомлений | `/notifications` |
| `/notifications_trades ON/OFF` | Уведомления о сделках | `/notifications_trades ON` |
| `/notifications_errors ON/OFF` | Уведомления об ошибках | `/notifications_errors ON` |
| `/notifications_balance ON/OFF` | Уведомления о балансе | `/notifications_balance ON` |

## 🔧 Утилиты

### Тестирование

| Команда | Описание | Пример |
|---------|----------|--------|
| `/test_connection` | Тест подключения | `/test_connection` |
| `/test_telegram` | Тест Telegram | `/test_telegram` |
| `/test_api` | Тест API | `/test_api` |
| `/test_full` | Полный тест | `/test_full` |

### Экспорт данных

| Команда | Описание | Пример |
|---------|----------|--------|
| `/export_trades` | Экспорт сделок | `/export_trades` |
| `/export_performance` | Экспорт производительности | `/export_performance` |
| `/export_config` | Экспорт конфигурации | `/export_config` |

## 📱 Примеры использования

### Базовый мониторинг

```
/start
/status
/balance
/positions
/performance
```

### Управление торговлей

```
/pause
/resume
/close_all
/emergency_stop
```

### Настройка конфигурации

```
/config_show
/config_risk 0.08
/config_positions 5
/config_save
```

### Аналитика

```
/performance 7
/stats_trades
/leverage_report
/system_health
```

## ⚠️ Важные замечания

### Безопасность

1. **Административные команды** доступны только администраторам
2. **Экстренные команды** требуют подтверждения
3. **API ключи** никогда не отправляются в Telegram
4. **Чувствительные данные** маскируются в сообщениях

### Ограничения

1. **Rate Limiting** - не более 10 команд в минуту
2. **Размер сообщений** - ограничен Telegram API
3. **Время ответа** - зависит от скорости системы
4. **Доступность** - только при работающем боте

### Рекомендации

1. **Регулярно проверяйте** `/status` и `/system_health`
2. **Используйте** `/performance` для мониторинга прибыли
3. **Настройте уведомления** для важных событий
4. **Сохраняйте логи** для анализа проблем

---

**💡 Совет**: Начните с базовых команд `/start`, `/status`, `/balance` для знакомства с системой.
