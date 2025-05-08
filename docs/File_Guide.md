### BinanceBot File Guide

Introduction
This document provides a comprehensive overview of the BinanceBot project files, explaining the purpose and role of each component in the system. The architecture is designed with scalability in mind, starting with small deposit optimization (100-120 USDC) while supporting growth to larger account sizes.

# 📚 File Guide — Актуальная структура проекта BinanceBot (Май 2025)

Этот документ описывает назначение всех файлов проекта.

| 📄 **Файл**                    | 🛠 **Основное назначение**                        | 📘 **Краткое содержание функций**               |
| ------------------------------ | ------------------------------------------------ | ----------------------------------------------- |
| `main.py`                      | Старт и управление ботом                         | запуск бота, ротация символов, мониторинг IP    |
| `trade_engine.py`              | Основная торговая логика                         | сделки, трейлинг, обработка сигналов            |
| `pair_selector.py`             | Выбор активных торговых пар                      | динамическая фильтрация, ротация, приоритизация |
| `strategy.py`                  | Проверка сигналов стратегий                      | ATR/ADX/BB фильтры, условия входа               |
| `tp_logger.py`                 | Логирование тейк-профитов и стопов               | запись TP/SL событий в CSV                      |
| `tp_optimizer.py`              | Анализ эффективности TP1/TP2                     | расчёт winrate, настройка TP                    |
| `tp_optimizer_ml.py`           | ML-адаптация параметров TP                       | машинное обучение на данных сделок              |
| `score_evaluator.py`           | Оценка силы сигнала (score)                      | финальный расчёт балла сделки                   |
| `score_logger.py`              | Логирование расчётов score                       | запись анализа сигналов в файл                  |
| `score_heatmap.py`             | Построение карты активности сигналов             | визуализация эффективности символов             |
| `risk_utils.py`                | Расчёт риска и размера позиций                   | адаптивный риск-менеджмент                      |
| `engine_controller.py`         | Управление состоянием работы бота                | глобальные флаги запуска/остановки              |
| `utils_core.py`                | Базовые утилиты                                  | кэширование данных, защита файлов               |
| `utils_logging.py`             | Система логирования                              | вывод логов в консоль/Telegram                  |
| `binance_api.py`               | Работа с API Binance                             | обёртки над запросами, ордера                   |
| `exchange_init.py`             | Инициализация подключения                        | создание клиента API                            |
| `aggressiveness_controller.py` | Контроль уровня агрессии торговли                | динамическое сглаживание агрессии               |
| `balance_watcher.py`           | Мониторинг баланса                               | защита рисков по балансу                        |
| `order_utils.py`               | Утилиты для работы с ордерами                    | расчёт цен TP/SL                                |
| `symbol_processor.py`          | Утилиты для обработки символов                   | стандартизация имён, фильтрация                 |
| `telegram_handler.py`          | Telegram-бот: подключение                        | прием команд, отправка сообщений                |
| `telegram_commands.py`         | Реализация Telegram-команд                       | команды `/stop`, `/status`, `/log` и др.        |
| `telegram_ip_commands.py`      | IP-команды Telegram (перезагрузка роутера и др.) | `/ipstatus`, `/router_reboot`, `/forceipcheck`  |
| `telegram_utils.py`            | Утилиты для работы с Telegram                    | экранирование сообщений, безопасная отправка    |
| `notifier.py`                  | Отправка ключевых уведомлений                    | уведомления о закрытии сделок, ошибках          |
| `htf_optimizer.py`             | Анализ фильтра по старшему таймфрейму (HTF)      | автоподключение/отключение HTF-фильтра          |
| `volatility_controller.py`     | Контроль волатильности рынка                     | динамическое изменение числа активных пар       |
| `stats.py`                     | Сбор статистики PnL и сделок                     | генерация отчётов для Telegram                  |
| `ip_monitor.py`                | Мониторинг смены внешнего IP                     | защита бота при смене IP-адреса                 |
| `config.py`                    | Основные настройки проекта                       | параметры стратегий, риск-лимиты, фильтры       |
| `config_loader.py`             | Загрузка и проверка конфигураций                 | чтение config.py и валидация                    |

---

# 📊 Важно:

-   Все модули логически связаны и обмениваются данными через централизованные структуры (`state`, `config`, `scheduler`, и пр.).
-   Все логи выводятся через единую систему `utils_logging.py`, поддерживающую Telegram.
-   Все расчёты сделок учитывают динамический риск через `risk_utils.py` и качество сигналов через `score_evaluator.py`.

---

# ⚡️📂 Проект Binance USDC Futures SmartBot – Карта файлов и связей

🧠 Логика стратегий
Модуль Назначение Зависимости
strategy.py Расчёт торговых сигналов (фильтры, ATR, score) utils_core, utils_logging
score_evaluator.py Оценка сделок по скору strategy, utils_logging
score_logger.py Логирование score при каждом анализе utils_logging
htf_optimizer.py Анализ старшего таймфрейма для фильтрации сделок utils_logging
score_heatmap.py Статистика скоринга по всем сделкам stats.py

⚙️ Торговый движок
Модуль Назначение Зависимости
trade_engine.py Основной процесс открытия/ведения сделок binance_api, order_utils, tp_utils, entry_logger, risk_utils, utils_logging
symbol_processor.py Управление обработкой пар pair_selector, trade_engine, volatility_controller
pair_selector.py Выбор лучших пар по волатильности и объёму utils_core, utils_logging
volatility_controller.py Контроль минимального числа активных пар utils_logging

💰 Финансы и риск
Модуль Назначение Зависимости
risk_utils.py Расчёт адаптивного риска на сделку -
tp_utils.py Работа с тейк-профитами (TP1, TP2) tp_logger, tp_optimizer, tp_optimizer_ml, utils_logging
tp_logger.py Логирование всех TP/SL событий utils_logging
tp_optimizer.py Оптимизация TP1/TP2 на основе статистики stats.py
tp_optimizer_ml.py ML-анализ TP-статистики и автоадаптация порогов stats.py
entry_logger.py Логирование всех входов в сделки utils_logging
balance_watcher.py Мониторинг баланса и прибыли utils_logging

🌐 Интеграция с биржей
Модуль Назначение Зависимости
binance_api.py Обёртка для работы с API Binance USDC Futures utils_logging
exchange_init.py Инициализация клиента биржи binance_api, config_loader

📡 Telegram-интеграция
Модуль Назначение Зависимости
telegram_handler.py Подключение Telegram-бота telegram_commands, telegram_ip_commands, telegram_utils, utils_logging
telegram_commands.py Стандартные команды управления ботом engine_controller, trade_engine, stats.py
telegram_ip_commands.py Команды управления мониторингом IP ip_monitor, utils_logging
telegram_utils.py Утилиты для Telegram (markdown, экранирование) -
notifier.py Отправка уведомлений о сделках в Telegram utils_logging

🛠 Вспомогательные модули
Модуль Назначение Зависимости
engine_controller.py Управление запуском/остановкой движка торговли trade_engine, symbol_processor
ip_monitor.py Мониторинг изменения внешнего IP-адреса utils_logging
stats.py Общая статистика сделок, PnL и отчёты entry_logger, tp_logger
utils_core.py Базовые утилиты (например, safe_call, async tools) -
utils_logging.py Базовое логирование в консоль и файлы -

📂 Конфигурация и управление настройками
Модуль Назначение
config.py Старый файл конфигурации - для примера.
config_loader.py Актуальный файл конфигурации: Основные параметры стратегии и торговли, Загрузка и валидация конфигураций
main.py Главный запуск бота (инициализация всех модулей)

📍 Как читается эта карта
Торговый цикл: main.py ➔ engine_controller ➔ symbol_processor ➔ trade_engine ➔ binance_api.

Стратегии: strategy.py, score_evaluator.py, htf_optimizer.py.

Риски и TP: risk_utils, tp_utils, tp_logger, tp_optimizer, tp_optimizer_ml.

Telegram: через telegram_handler и связанные команды.

Логи и утилиты: через utils_logging, utils_core.

## 🗂 Приоритеты файлов проекта Binance USDC Futures SmartBot

Уровень Файлы Назначение
🔥 Критические (основа торговли) main.py, engine_controller.py, symbol_processor.py, trade_engine.py, strategy.py, binance_api.py, pair_selector.py Без них торговля невозможна

📈 Стратегия и адаптация score_evaluator.py, htf_optimizer.py, tp_utils.py, risk_utils.py, tp_optimizer.py, tp_optimizer_ml.py, volatility_controller.py Обработка сигналов, адаптация TP, риск-менеджмент

📡 Коммуникация и Telegram telegram_handler.py, telegram_commands.py, telegram_ip_commands.py, telegram_utils.py, notifier.py Telegram-бот, команды, уведомления

📋 Логи, учёт сделок и статистика entry_logger.py, tp_logger.py, stats.py, score_logger.py, score_heatmap.py Ведение истории сделок, анализ прибыли, графики

🛠 Вспомогательные утилиты utils_core.py, utils_logging.py, order_utils.py, exchange_init.py, aggressiveness_controller.py Технические операции, API-запросы, логирование

⚙️ Конфигурация и настройки config_loader.py Все параметры торговли, фильтры, режимы работы
🛡️ Безопасность и стабильность ip_monitor.py Контроль смены IP, защита сессии

📍 Как использовать эту таблицу
Если нужно менять логику торговли → смотреть 🔥 Критические.

Если нужно оптимизировать стратегию или риски → идти в 📈 Стратегию и адаптацию.

Если проблема в Telegram или уведомлениях → смотреть 📡 Коммуникацию.

Для логов, отчётов, графиков → проверять 📋 Логи и статистику.

Вспомогательные скрипты и общие утилиты — 🛠 Вспомогательные.

Все глобальные настройки и пороги — ⚙️ Конфигурация.
