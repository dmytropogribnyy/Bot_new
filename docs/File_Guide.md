BinanceBot File Guide
Introduction
This document provides a comprehensive overview of the BinanceBot project files, explaining the purpose and role of each component in the system. The architecture is designed with scalability in mind, starting with small deposit optimization (100-120 USDC) while supporting growth to larger account sizes.
Configuration Management
common/config_loader.py
Central configuration hub with adaptive parameters for different account sizes. Manages risk percentages, position limits, trading thresholds, and commission rates. Contains priority pair definitions for small accounts and leverage mappings.
config.py (Legacy)
Being phased out in favor of config_loader.py. Contains older static configuration values that are being migrated to the centralized system.
Core Trading Engine
core/main.py
Application entry point that initializes all components, manages threading, and coordinates the main trading loop. Handles graceful shutdown and implements adaptive position management based on account size.
core/engine_controller.py
Orchestrates trading cycles with symbol group processing. Implements position limit enforcement, smart switching between signals, and adaptive cycle timing. Contains emergency stop handling for risk management.
core/trade_engine.py
Executes entry and exit orders with commission-aware profit calculation. Implements TP/SL management, trailing stops, and break-even functionality. Includes specialized order sizing for small deposits and margin safety checks.
core/exchange_init.py
Establishes connection to Binance API and configures leverage settings. Handles both regular and testnet environments with appropriate error reporting.
core/binance_api.py
Provides safe, standardized access to all Binance API endpoints with retry logic. Includes commission calculation, order validation, and enhanced error handling for small accounts.
Position & Risk Management
core/risk_utils.py
Implements adaptive risk percentage calculation based on account size, with progressive scaling from 2% for small accounts to 4% for larger accounts. Provides position limit determination and minimum profit requirements.
core/order_utils.py
Calculates optimal order quantities based on risk parameters and price levels. Implements position sizing with account-aware risk scaling.
core/symbol_processor.py
Processes trading symbols with comprehensive validation for small deposits. Implements margin buffer, priority pair filtering, and minimum notional checks with specific optimizations for accounts under 150 USDC.
core/balance_watcher.py
Monitors account balance changes with milestone tracking for growth. Detects deposits, withdrawals, and sends notifications for significant account balance milestones (150, 200, 300, 500, 1000 USDC).
Signal Generation
core/strategy.py
Implements multi-timeframe signal generation with enhanced filtering for small accounts. Contains entry condition logic with account-aware profit threshold calculation and dynamic position sizing.
core/score_evaluator.py
Evaluates and scores trading signals with adaptive thresholds based on account size. Implements different score requirements for different account categories to balance opportunity and risk.
core/volatility_controller.py
Controls volatility filtering with adaptations for small accounts. Provides more permissive filters for priority pairs on small accounts while maintaining stricter standards for non-priority pairs.
core/aggressiveness_controller.py
Manages trading aggressiveness levels with account size adaptations. Implements more conservative approach for small accounts with slower adaptation to performance changes.
Data Processing & Analysis
core/pair_selector.py
Selects optimal trading pairs based on volatility, volume, and price with account-specific strategies. Prioritizes XRP/USDC, DOGE/USDC, ADA/USDC for accounts under 150 USDC and implements different selection algorithms based on account size.
core/tp_logger.py
Logs trade performance with enhanced metrics for small deposits. Tracks absolute profit in USDC, calculates commission impact, and maintains statistics for optimization decisions.
core/entry_logger.py
Records trade entries with detailed context for small accounts. Captures account balance, commission, and expected profit metrics for each entry.
core/score_logger.py
Logs signal score history for performance analysis. Used by visualization and optimization components to refine strategy parameters.
Communication & Notification
telegram/telegram_handler.py
Processes incoming Telegram commands and coordinates responses. Provides the communication backbone for the bot's control interface.
telegram/telegram_commands.py
Implements Telegram command processing with comprehensive status reporting. Provides enhanced position formatting for small accounts and account-specific risk reporting.
telegram/telegram_utils.py
Handles message formatting and delivery with fallback mechanisms. Ensures critical notifications are delivered properly, especially for small accounts where timely information is essential.
telegram/telegram_ip_commands.py
Manages IP-related commands for maintaining API access. Helps prevent trading interruptions due to IP changes, which is critical for maintaining consistent performance on small accounts.
core/notifier.py
Sends notifications for significant events with specialized alerts for small accounts. Provides milestone notifications, low balance warnings, and performance updates.
Optimization Tools
htf_optimizer.py
Analyzes and optimizes the High Timeframe confirmation strategy based on performance data. Helps improve overall strategy performance regardless of account size.
tp_optimizer.py
Optimizes Take Profit and Stop Loss levels based on historical performance. Provides automated parameter adjustment for maximizing returns, especially important for small accounts where each percentage point matters more.
tp_optimizer_ml.py
Implements machine learning based optimization for symbol-specific parameters. Provides finer control over risk parameters based on actual performance with adaptive thresholds.
score_heatmap.py
Generates visualization of scoring patterns across different symbols. Assists in identifying the most consistently promising trading opportunities, critical for selective trading with limited capital.
Utilities & Support Functions
utils_core.py
Provides core utility functions including API caching, state management, and safe API calls. Implements adaptive risk management functions and minimum profit requirements based on account size.
utils_logging.py
Implements comprehensive logging with level-based filtering and rotation. Provides error notification, configuration backup, and specialized event logging to support trading operations.
ip_monitor.py
Monitors external IP address changes to prevent API access issues. Important for maintaining consistent trading, especially for small accounts where interruptions can have larger relative impact.
Special-Purpose Components
stats.py
Generates performance reports and analyzes trading results. Provides insights for optimization and strategy refinement with metrics relevant to different account sizes.
Integration Structure
The system is designed around a component-based architecture with:

Centralized Configuration: All parameters flow from config_loader.py to ensure consistency
Message-Based Communication: Components interact through well-defined interfaces
Adaptive Behavior: All critical components adapt their behavior based on account size
Progressive Risk Scaling: Risk parameters automatically adjust as the account grows
Priority-Based Trading: Small accounts focus on specific pairs for optimal capital utilization

This architecture supports the growth trajectory from small deposits (100-120 USDC) to larger account sizes by automatically adjusting parameters, priorities, and strategies based on the current balance.
