BinanceBot — Master Plan for Small Deposit Optimization (May 2025)
📋 Project Structure & Architecture
BINANCEBOT/
BINANCEBOT/
├── .pycache/ # Python bytecode cache
├── .ruff*cache/ # Ruff linter cache
├── .vscode/ # VSCode editor configuration
├── backup_before_refactor/ # Backup files before code refactoring
├── common/ # Shared configuration
│ ├── \_pycache*/ # Python bytecode cache
│ └── config*loader.py # Centralized configuration management
├── core/ # Main trading engine
│ ├── aggressiveness_controller.py # Trading aggressiveness management
│ ├── balance_watcher.py # Account balance monitoring
│ ├── binance_api.py # Binance API integration
│ ├── engine_controller.py # Trading cycle orchestration
│ ├── exchange_init.py # Exchange connection setup
│ ├── entry_logger.py # Trade entry logging
│ ├── notifier.py # Notification system
│ ├── order_utils.py # Order size calculations
│ ├── risk_utils.py # Risk management functions
│ ├── score_evaluator.py # Signal evaluation
│ ├── score_logger.py # Signal score logging
│ ├── strategy.py # Trading signal generation
│ ├── symbol_processor.py # Symbol validation & processing
│ ├── tp_utils.py # TP/SL calculation
│ ├── trade_engine.py # Order execution logic
│ └── volatility_controller.py # Volatility analysis
├── data/ # Data storage
│ ├── bot_state.json # Bot state information
│ ├── dry_entries.csv # Simulated trade entries
│ ├── dynamic_symbols.json # Selected trading pairs
│ ├── entry_log.csv # Trade entry history
│ ├── filter_adaptation.json # Volatility filter settings
│ ├── last_ip.txt # Last detected external IP
│ ├── last_update.txt # Last update timestamp
│ ├── score_history.csv # Signal score history
│ ├── tp_performance.csv # Trade performance history
│ └── trade_statistics.json # Aggregated trading metrics
├── docs/ # Documentation
│ ├── File_Guide.md # System architecture reference
│ ├── Master_Plan.md # Project roadmap
│ ├── Mini_Hints.md # Daily operations checklist
│ ├── PracticalGuideStrategyAndCode.md # Strategy reference
│ └── Syntax & Markdown Guide.md # Telegram formatting guide
├── logs/ # Log files
│ └── main.log # Main application log
├── telegram/ # Telegram integration
│ ├── \_pycache*/ # Python bytecode cache
│ ├── telegram_commands.py # Bot command handlers
│ ├── telegram_handler.py # Message processing
│ ├── telegram_ip_commands.py # IP-related commands
│ └── telegram_utils.py # Messaging utilities
├── test-output/ # Test results
├── venv/ # Virtual environment
├── .env # Environment variables
├── .env.example # Example environment config
├── .gitignore # Git exclude patterns
├── check_config_imports.py # Import validation tool
├── clean_cache.py # Cache cleaning utility
├── config.py # Legacy configuration
├── debug_log.txt # Debug logging
├── htf_optimizer.py # High timeframe optimization
├── ip_monitor.py # IP change detection
├── main.py # Application entry point
├── pair_selector.py # Trading pair selection
├── push_log.txt # Push operation log
├── push_to_github.bat # GitHub push script
├── pyproject.toml # Project configuration
├── README.md # Project overview
├── refactor_imports.py # Import refactoring tool
├── requirements.txt # Dependencies
├── restore_backup.py # Backup restoration
├── router_reboot_dry.run.md # DRY_RUN IP change guide
├── router_reboot_real.run.md # REAL_RUN IP change guide
├── safe_compile.py # Safe compilation check
├── score_heatmap.py # Score visualization
├── start_bot.bat # Bot startup script
├── stats.py # Performance analytics
├── test_api.py # API testing
├── test_graphviz.py # Structure visualization
├── tp_logger.py # Trade performance logging
├── tp_optimizer_ml.py # ML-based TP optimization
├── tp_optimizer.py # TP/SL optimization
├── update_from_github.bat # GitHub update script
├── utils_core.py # Core utilities
└── utils_logging.py # Logging utilities

# BinanceBot — Master Plan for Small Deposit Optimization (May 2025)

## 👉 Проект: Оптимизация BinanceBot для малых депозитов

### Цель

Оптимизировать торгового бота для работы с депозитами 100–120 USDC с целью безопасного роста капитала до 700+ USDC.

---

## 👉 Архитектура проекта (кратко)

-   **common/** — Конфигурации и параметры
-   **core/** — Основные механизмы торговли, расчёты ордеров, риск-менеджмент
-   **telegram/** — Интеграция с Telegram-ботом
-   **data/** — Логи сделок, динамические пары, статистика
-   **logs/** — Основной лог работы бота
-   **tp_optimizer_ml.py** — Модуль оптимизации TP/SL через машинное обучение
-   **pair_selector.py** — Выбор и ротация торговых пар
-   **main.py** — Запуск всех компонентов, планировщик задач

---

# Master Plan for BinanceBot (Updated)

## 📊 Overview

Smart, adaptive trading bot for Binance USDC Futures.

Core Goals:

-   Safe growth of small deposits (starting 40-100 USDC)
-   Smart trade management (micro-trades, dynamic exits)
-   Full control via Telegram
-   Auto-optimization (TP/SL, HTF analysis)
-   Intelligent symbol rotation and opportunity tracking

---

## 📅 Project Structure (Modules)

-   **main.py**: Core trading loop, Telegram commands, scheduler.
-   **pair_selector.py**: Dynamic symbol selection and missed opportunities tracking.
-   **engine_controller.py**: Trade decision engine, smart switching logic.
-   **trade_engine.py**: Enter/exit trades, monitors (trailing, breakeven, micro-trades).
-   **tp_utils.py**: Dynamic TP/SL management for micro-profits.
-   **config_loader.py**: Centralized configuration, including micro-trade settings.
-   **utils_core.py**: Cache, state management, market volatility calculation.
-   **htf_optimizer.py / tp_optimizer.py**: Auto-optimizations.
-   **telegram_handler.py / telegram_commands.py**: Full Telegram control.

---

## 📈 Status of Key Systems

| Feature                            | Status                                 |
| :--------------------------------- | :------------------------------------- |
| Adaptive Symbol Rotation           | ✅ Completed (Dynamic with volatility) |
| Micro-Trade Timeout and Management | ✅ Completed                           |
| Missed Opportunities Tracker       | ✅ Completed                           |
| Smart Switching Between Positions  | ✅ Completed                           |
| Full Telegram Bot Control          | ✅ Completed                           |
| Trailing Stop & Breakeven          | ✅ Completed                           |
| HTF Confirmation Analyzer          | ✅ Completed                           |
| Dynamic TP/SL Optimizer            | ✅ Completed                           |
| Auto Aggressiveness Bias           | ✅ Completed                           |

---

## 🏆 Successfully Implemented

-   Dynamic rotation of trading pairs based on balance, volatility, trading hours.
-   Micro-trade optimization: timeouts, dynamic exit thresholds.
-   Smart Switching: replace weak trades with better opportunities.
-   Safe Close: all exits through safe_close_trade() to avoid stuck orders.
-   Missed opportunities tracking for long-term strategy learning.
-   Telegram-based bot management: start, stop, panic, summaries.
-   Multi-layered scheduled reports: daily, weekly, monthly, quarterly, yearly.
-   Independent monitoring threads: IP monitor, symbol rotation, optimization loops.

---

## 📆 Completion Roadmap

### Phase 1: Critical Enhancements (Completed)

-   Refine Risk/Reward settings for small balances.
-   Adjust indicator weights in Score System.
-   Light optimization of TP/SL calculations.

### Phase 2: Extended Adaptation (In Progress)

-   Further improve adaptation for priority pairs.
-   Check all edge-cases for API/margin errors.

### Phase 3: Real Launch (Upcoming)

-   Final test Real Run with low risk.
-   Progressively increase risk with growing balance.

---

## 🔢 Monitoring Metrics

| Metric                    | Target      |
| :------------------------ | :---------- |
| Win Rate                  | > 60%       |
| Profit Factor             | > 1.5       |
| Average Profit per Trade  | > 0.7%      |
| Fee Ratio to Gross Profit | < 25%       |
| API/Margin Errors         | 0–1 per day |

---

## 🔔 Final Summary

🔹 BinanceBot v1.6.5-dev is ready for stable Real Run with small deposits.

-   Bot autonomously adapts to market conditions.
-   All major risks are under control.
-   Key automation features are implemented.
-   Remaining enhancements are minor and can be added in parallel with trading.

# 🚀 Ready for Real Run!

# 📜 История улучшений проекта (2025)

Этот документ отражает этапы развития торгового бота Binance USDC Futures в 2025 году. Всё реализованное описано ниже, для понимания логики, эволюции и целей изменений.

Основные этапы:
⚙️ Базовая архитектура
Модульная структура (trade_engine.py, strategy.py, risk_utils.py, telegram_handler.py и др.)

Поддержка USDC-фьючерсов, работа с лимитными ордерами и стопами.

Первичная фильтрация сделок через индикаторы ATR, ADX, BB.

📈 Развитие стратегий
Внедрение системы адаптивных фильтров ATR/ADX/BB.

Добавление динамической оценки score для сигналов.

Введение мультистадийных Take-Profit (TP1/TP2) с логированием.

🛡️ Безопасность и стабильность
Поддержка DRY_RUN режима.

Защита от сбоев при закрытии сделок и рестарте.

Контроль внешнего IP-адреса для автоматической остановки бота при смене.

✨ Интеллектуальные улучшения
Smart Switching между сделками при более сильных сигналах.

HTF Optimizer: оптимизация фильтрации по старшим таймфреймам.

TP Optimizer ML: машинное обучение для адаптации TP1/TP2.

📊 Telegram-интеграция
Команды управления /stop, /panic, /status, /summary.

Автоматические уведомления о сделках, отчёты за день, неделю, месяц.

Умная обработка Markdown для Telegram.

🚀 Новейшие улучшения (май 2025)
Адаптивный риск на сделку от 2% до 5% в зависимости от качества пары.

Мгновенное удаление слабых пар по ATR% и объёму без задержки.

Динамическое обновление Priority-листа лучших активных символов.

Фиксация ошибок трейлинга после остановки бота.

Полная ревизия всех файлов проекта и обновление документации.

📂 Состояние на май 2025:
Проект полностью стабилен, поддерживает:

Реальные сделки с защитой капитала.

Автоматическую адаптацию стратегий.

Гибкое управление риском.

Полную Telegram-поддержку.

Проект готов к дальнейшему развитию:

WebSocket-подключения.

Расширение под другие биржи.

Углублённый AI-анализ сигналов.
