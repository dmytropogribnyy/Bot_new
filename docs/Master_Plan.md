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

BinanceBot Master Plan — Small Deposit Optimization 2.0 (May 2025)
Executive Summary
This document outlines the strategy and implementation status for BinanceBot's small deposit optimization initiative. The goal is to optimize the bot for trading with deposits of 100-120 USDC while establishing a growth path to 700+ USDC. The plan addresses key components including risk management, scoring algorithms, entry/exit strategies, and specific adaptations for small balances.
Implementation Status Overview
AreaStatusPriorityAdaptive Risk Management✅ 90% CompleteMEDIUMSignal Scoring System⚠️ 50% CompleteHIGHATR-based TP/SL✅ 80% CompleteMEDIUMPriority Pairs Selection✅ 100% CompleteLOWRisk/Reward Requirements⚠️ 40% CompleteCRITICALCommission Awareness✅ 90% CompleteLOWBreak-even & Soft Exit✅ 100% CompleteLOWError Handling & Validation⚠️ 60% CompleteHIGH
Core Strategy Components
Account Size Adaptation
Balance (USDC)Risk %Max PositionsMin ProfitFocus Pairs< 1002.0%20.15 USDCXRP, DOGE only100-1502.5%30.20 USDCXRP, DOGE, ADA, SOL150-3003.0%40.30 USDCAll priority pairs> 3004.0%50.50 USDCAll available pairs
Priority Pairs Definition
pythonPRIORITY_SMALL_BALANCE_PAIRS = [
"XRP/USDC", # Low price, high liquidity
"DOGE/USDC", # Low price, good volatility
"ADA/USDC", # Low price, steady volatility
"SOL/USDC", # Medium price, good volume
"MATIC/USDC", # Added: Low price, high liquidity
"DOT/USDC", # Added: Good volatility profile
]
Optimized Leverage Settings
pythonLEVERAGE_MAP = {
"BTCUSDT": 5,
"ETHUSDT": 5,
"BTCUSDC": 5,
"ETHUSDC": 5,
"DOGEUSDC": 12, # Increased from 10 for better capital efficiency
"XRPUSDC": 12, # Increased from 10
"ADAUSDC": 10, # Unchanged
"SOLUSDC": 6, # Increased from 5
"BNBUSDC": 5, # Unchanged
"LINKUSDC": 8, # Increased from 5
"ARBUSDC": 6, # Increased from 5
"SUIUSDC": 6, # Increased from 5
"MATICUSDC": 10, # Added new pair
"DOTUSDC": 8, # Added new pair
}
Critical Pending Optimizations

1.  Risk/Reward Ratio Adjustment ⚠️ CRITICAL
    Current Implementation (needs update):
    pythondef get_required_risk_reward_ratio(score, symbol=None, balance=None): # Base R:R by score
    if score < 3.0:
    base_rr = 1.8 # Too high for small deposits
    elif score < 3.5:
    base_rr = 1.5
    elif score < 4.0:
    base_rr = 1.3
    else:
    base_rr = 1.2

        # Priority pair adjustment for small accounts
        if balance and balance < 150 and symbol in PRIORITY_SMALL_BALANCE_PAIRS:
            base_rr *= 0.9  # Only 10% lower R:R requirement - insufficient

        return base_rr

    Required Changes:
    pythondef get_required_risk_reward_ratio(score, symbol=None, balance=None): # Significantly reduce base requirements
    if score < 3.0:
    base_rr = 1.0 # Reduced from 1.8
    elif score < 3.5:
    base_rr = 0.8 # Reduced from 1.5
    elif score < 4.0:
    base_rr = 0.7 # Reduced from 1.3
    else:
    base_rr = 0.6 # Reduced from 1.2

        # Increase discount for priority pairs
        if balance and balance < 150 and symbol in PRIORITY_SMALL_BALANCE_PAIRS:
            base_rr *= 0.6  # 40% discount instead of 10%

        # Additional discount for very small deposits
        if balance and balance < 100:
            base_rr *= 0.8  # Another 20% discount for deposits <100 USDC

        return base_rr

2.  Scoring Weights Enhancement ⚠️ HIGH
    Current Implementation (needs update):
    pythonSCORE_WEIGHTS = {
    "RSI": 1.5,
    "MACD_RSI": 2.0,
    "MACD_EMA": 2.0,
    "HTF": 0.5,
    "VOLUME": 1.5,
    "EMA_CROSS": 2.0,
    "VOL_SPIKE": 1.5,
    "PRICE_ACTION": 1.5,
    }
    Required Changes:
    pythonSCORE_WEIGHTS = {
    "RSI": 2.0, # Increased from 1.5
    "MACD_RSI": 2.5, # Increased from 2.0
    "MACD_EMA": 2.5, # Increased from 2.0
    "HTF": 0.5, # Unchanged (less important for short-term)
    "VOLUME": 2.0, # Increased from 1.5
    "EMA_CROSS": 3.0, # Increased from 2.0 - emphasis on short-term momentum
    "VOL_SPIKE": 2.5, # Increased from 1.5 - emphasis on volume
    "PRICE_ACTION": 2.5, # Increased from 1.5 - emphasis on recent price actions
    }
3.  TP/SL Calculation Optimization ⚠️ HIGH
    Current Implementation (needs update):
    python# Current values in tp_utils.py

# ATR-based calculations with potentially suboptimal multipliers

Required Changes (Option 1 - ATR Multipliers):
python# Optimize ATR multipliers in tp*utils.py
tp1_mult = 1.2 # Increased from 0.8
tp2_mult = 2.4 # Increased from 1.6
sl_mult = 0.8 # Decreased from 1.2
Required Changes (Option 2 - Base Percentages):
python# In config_loader.py
TP1_PERCENT = 0.009 # Increased from 0.006 (0.9% instead of 0.6%)
TP2_PERCENT = 0.016 # Increased from 0.013 (1.6% instead of 1.3%)
SL_PERCENT = 0.007 # Decreased from 0.009 (0.7% instead of 0.9%) 4. Priority Pair Adaptation ⚠️ MEDIUM
Current Implementation (needs update):
python# In strategy.py
if SHORT_TERM_MODE and is_optimal_trading_hour():
min_required *= 0.9 # Only 10% reduction - insufficient
Required Changes:
python# Enhanced adaptation during optimal trading hours
if SHORT*TERM_MODE and is_optimal_trading_hour():
min_required *= 0.7 # 30% reduction instead of 10%

# Additional confidence boost for priority pairs

if balance < 150 and symbol in PRIORITY_SMALL_BALANCE_PAIRS:
direction_confidence += 0.2 # Additional +20% confidence
Successful Implementations
Adaptive Risk Management ✅
pythondef get_adaptive_risk_percent(balance, win_streak=0): # Base risk based on account size
if balance < 100:
base_risk = 0.018 # 1.8% for ultra-small accounts
elif balance < 150:
base_risk = 0.022 # 2.2% for small accounts
elif balance < 300:
base_risk = 0.028 # 2.8% for medium accounts
else:
base_risk = 0.038 # 3.8% for larger accounts

    # Adjust based on recent performance
    win_streak_boost = min(win_streak * 0.002, 0.01)  # Up to +1% for win streaks

    # Cap final risk percentage
    return min(base_risk + win_streak_boost, 0.05)  # Cap at 5%

Break-Even & Soft Exit Optimization ✅
python# Early break-even
BREAKEVEN_TRIGGER = 0.4 # Changed from 0.5 to 0.4 for earlier breakeven

# Early profit taking

SOFT_EXIT_THRESHOLD = 0.7 # Changed from 0.8 to 0.7 for earlier profit taking
Trading Hours Optimization ✅
python# Trading hours filter
TRADING_HOURS_FILTER = True
HIGH_ACTIVITY_HOURS = [8, 9, 10, 11, 12, 13, 14, 15, 16, 20, 21, 22] # UTC hours

def is_optimal_trading_hour():
current_time = datetime.now(pytz.UTC)
hour_utc = current_time.hour
return hour_utc in HIGH_ACTIVITY_HOURS
Short-Term Indicators ✅
pythondef detect_ema_crossover(df):
"""
Detect recent EMA crossover for short-term momentum signals.
"""
if "fast_ema" not in df.columns or "slow_ema" not in df.columns:
return False, 0

    # Check if we have a recent crossover (within last 3 candles)
    fast_ema = df["fast_ema"].iloc[-3:].values
    slow_ema = df["slow_ema"].iloc[-3:].values

    # Check for bullish crossover (fast crosses above slow)
    if fast_ema[-1] > slow_ema[-1] and fast_ema[-3] <= slow_ema[-3]:
        return True, 1  # Bullish

    # Check for bearish crossover (fast crosses below slow)
    if fast_ema[-1] < slow_ema[-1] and fast_ema[-3] >= slow_ema[-3]:
        return True, -1  # Bearish

    return False, 0

Implementation Timeline
Phase 1: Critical Fixes (Days 1-3)

Day 1: Update Risk/Reward Requirements

Modify get_required_risk_reward_ratio in score_evaluator.py
Test with various score and balance combinations

Day 2: Enhance Scoring Weights

Update SCORE_WEIGHTS in config_loader.py
Test signal generation on historical data

Day 3: Optimize TP/SL Calculations

Implement either ATR multiplier or base percentage adjustments
Verify R ratios achieve target values

Phase 2: Advanced Optimizations (Days 4-7)

Day 4: Enhance Priority Pair Processing

Update trading hour adaptations in strategy.py
Add confidence boosting for priority pairs

Day 5: Error Validation Improvements

Add comprehensive NoneType checks in key functions
Implement margin safety buffer at 90%

Day 6-7: DRY_RUN Testing

Execute 24-hour test with updated parameters
Analyze trade frequency, entry points, and profitability

Phase 3: Production Deployment (Days 8-14)

Days 8-10: Controlled Real Trading

Start with conservative risk (1.5%) on priority pairs
Limited to maximum 2 positions
Monitor and analyze trade performance

Days 11-14: Scale and Optimize

Progressively increase risk (2.0-2.5%) based on performance
Expand to all priority pairs if profitable
Fine-tune parameters based on real results

Risk Management Framework
Position Sizing

Adaptive Risk Percentage: 1-5% based on account size
Position Limit: 1-5 positions based on account size
Maximum Margin: 90% of available margin to prevent errors
Minimum Notional: 20 USDC per order

Entry Criteria

Signal Quality: Score threshold adjusted for account size
Risk/Reward: Lower requirements for small accounts
Profit Filter: Skip trades with < 0.15-0.5 USDC expected profit (account size dependent)
Priority Pairs: Lower thresholds for designated pairs

Exit Strategy

TP1: 70% of position at ATR-based target (min 0.7%)
TP2: 30% of position at ATR-based target (min 1.3%)
SL: ATR-based with minimum 0.7-1.0%
Break-Even: Move SL to entry after 40% of distance to TP1
Soft Exit: Close 50% at 70% of distance to TP1

Monitoring & Analysis
Key Performance Indicators

Win Rate: Target > 60%
Profit Factor: Target > 1.5
Average Profit: Target > 0.7% per trade
Commission Impact: < 25% of gross profit

Daily Review Process

Monitor TP/SL hit rate
Track commission impact
Analyze trade duration
Review error logs for NoneType or margin issues

Long-Term Development Roadmap
Near-Term (1-2 Months)

Implement ML-based parameter optimization
Add slippage analysis and adjustments
Develop enhanced pair rotation algorithm

Medium-Term (3-6 Months)

Implement hedging strategy for correlated pairs
Develop divergence detection for MACD/RSI
Add sentiment analysis integration

Long-Term (6+ Months)

Multi-exchange support
Portfolio balancing across assets
Advanced ML price prediction

Conclusion
This Master Plan reflects the current implementation status and priorities for optimizing BinanceBot for small deposit trading. While significant progress has been made in adaptive risk management, market analysis, and trade execution, critical adjustments are still required in risk/reward requirements, signal scoring, and TP/SL calculations to achieve optimal performance with small accounts.
The implementation timeline provides a clear roadmap for completing these optimizations and moving into controlled production deployment. By systematically addressing each component, the bot will achieve its goal of effectively trading with deposits as small as 100-120 USDC while providing a growth path to larger account sizes.

## The additional files confirm my earlier analysis:

Pair Selector (pair_selector.py): ✅ 100% Complete

Comprehensive strategy for small accounts (<150 USDC)
Prioritizes low-price assets with good momentum
Restricts to 3-5 pairs for very small accounts (<120 USDC)
Adaptive rotation frequency (faster for small accounts)

Risk Management (risk_utils.py): ✅ 100% Complete

Implements adaptive risk percentages (2-4%)
Scales position limits based on account size (2-5 positions)

Aggressiveness Controller (aggressiveness_controller.py): ✅ 100% Complete

Caps maximum aggressiveness for small accounts
Implements slower adaptation for more stability

Volatility Filtering (volatility_controller.py): ✅ 100% Complete

More permissive filters for priority pairs on small accounts
Stricter filters for non-priority pairs on small accounts

The critical pending optimizations remain as identified in the Master Plan:

Risk/Reward Requirements: ⚠️ CRITICAL

Current requirements in score_evaluator.py (1.8 for low scores) are still too high
The 10% discount for priority pairs is insufficient

Scoring Weights: ⚠️ HIGH

Current weights produce scores too low to trigger trades
Needs increased weights for short-term indicators

TP/SL Calculation: ⚠️ HIGH

Current implementation needs optimization for better risk ratio

Priority Pair Adaptation: ⚠️ MEDIUM

Current 10% threshold reduction in strategy.py is insufficient
Needs more aggressive adaptation during optimal trading hours

The Master Plan document correctly captures these implementation details and identifies the remaining work needed to fully optimize the bot for small deposit trading. No major updates to that document are needed - it remains an accurate roadmap for completing the optimization process.
