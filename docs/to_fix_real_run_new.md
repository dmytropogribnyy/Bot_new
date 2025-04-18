Revised Plan to Include All Fixes
To ensure all issues are covered, I’ll revise the plan to incorporate the MAX_OPEN_ORDERS fix within Step 1 (since it’s related to MAX_POSITIONS). The plan remains focused on REAL_RUN safe mode (DRY_RUN = False, RISK_PERCENT = 0.005, MAX_POSITIONS = 3, SYMBOLS_ACTIVE = ["BTC/USDC", "ETH/USDC"]), with bot-driven position opening (no manual orders). Each step includes:

Issue and fix.
Files to update (artifact IDs from previous responses).
How to apply and test in REAL_RUN.
Error checking.
Short description.
Safe Mode Settings:

python

Copy

# config.py

DRY_RUN = False
RISK_PERCENT = 0.005
MAX_POSITIONS = 3
SYMBOLS_ACTIVE = ["BTC/USDC", "ETH/USDC"]
LOG_LEVEL = "DEBUG"
MAX_OPEN_ORDERS = 10 # New setting for Issue 6
Backup:

Save codebase and tp_performance.csv to data/backups.
Testing Notes:

Run bot for 15-30 minutes per step.
Use ~120 USDC balance.
Bot opens positions automatically.
Close positions with /stop or /panic YES.
Check telegram_log.txt and tp_performance.csv.
Stop bot after each test (Ctrl+C or /stop).
Use /panic YES to clear positions before each step.
Revised Step-by-Step Plan
Step 1: Fix MAX_POSITIONS Limit, tp_performance.csv Not Updating, and MAX_OPEN_ORDERS
Description: Bot opens >10 positions due to outdated cache, trades aren’t logged, and too many TP/SL orders are placed. Fix cache updates, add startup cleanup, ensure logging, and limit open orders.

Files:

main.py (ID: 0a91d5da)
trade_engine.py (ID: ae8326f4, modified for MAX_OPEN_ORDERS)
tp_logger.py (ID: 0547d40d)
config.py (ID: 02e32de4, modified for MAX_OPEN_ORDERS)
symbol_processor.py (ID: fe2828c8)
Apply:

Replace main.py, tp_logger.py, and symbol_processor.py with artifacts.
Update config.py (add MAX_OPEN_ORDERS):
python

Copy

# config.py (partial)

MAX_OPEN_ORDERS = 10 # Add after MAX_POSITIONS
Update trade_engine.py (add MAX_OPEN_ORDERS check in enter_trade):
python

Copy
174 hidden lines
Test:

Use /panic YES to close all positions.
Start bot: cd c:/Bots/BinanceBot && python main.py.
Wait for bot to open up to 3 positions (check Binance).
Check telegram_log.txt for:
[Startup] Found X positions ... Closing excess positions (if any).
[Skipping {symbol} — max open positions (3) reached] for 4th position attempt.
[TP/SL] Skipping TP/SL for {symbol} — max open orders (10) reached] if applicable.
[REAL_RUN] Logged TP result for {symbol}.
Close positions with /stop.
Verify tp_performance.csv has new records.
Check Binance: ≤3 positions, ≤10 open orders per symbol.
Check Errors:

MAX_POSITIONS Fixed: ≤3 positions open; 4th attempt logs [Skipping ... max open positions (3)].
MAX_OPEN_ORDERS Fixed: ≤10 open orders per symbol; excess logs [Skipping TP/SL ... max open orders].
Logging Fixed: tp_performance.csv has trade records.
Not Fixed: >3 positions, >10 orders, or no CSV records (check logs for [TP Logger] Failed).
Artifacts:

config.py
python
Show inline
trade_engine.py
python
Show inline
Step 2: Fix Margin Insufficient Error
Description: TP1 orders fail due to insufficient margin (e.g., 343.16 USDC notional vs. 120 USDC balance). Margin check in symbol_processor.py ensures trades fit available margin.

File:

symbol_processor.py (ID: fe2828c8)
Apply:

Replace symbol_processor.py with artifact.
Confirm config.py: RISK_PERCENT = 0.005, MAX_POSITIONS = 3.
Test:

Use /panic YES to close positions.
Start bot.
Wait for bot to attempt opening positions.
Check telegram_log.txt for [Skipping {symbol} — insufficient margin (required: X, available: Y)].
Verify on Binance: no trades exceed ~120 USDC margin.
Close positions with /stop, check tp_performance.csv.
Check Error:

Fixed: No [ERROR] create_limit_order TP1 ... Margin is insufficient.
Not Fixed: Margin errors or oversized trades.
Step 3: Fix /stop and /panic YES Commands
Description: Commands fail to close positions due to outdated cache. Fetch positions directly and log closures.

File:

telegram_commands.py (ID: 2cd11885)
Apply:

Replace telegram_commands.py with artifact.
Test:

Use /panic YES to close positions.
Start bot.
Wait for bot to open 1-2 positions.
Send /stop or /panic YES.
Check telegram_log.txt for [Stop] Closing position or [Panic] Closing position.
Verify on Binance: all positions closed.
Confirm tp_performance.csv logs closures.
Check Error:

Fixed: Positions close, logs show ✅ All trades closed.
Not Fixed: Positions remain, or [Stop] Failed errors.
Step 4: Fix Trailing Stop Error: Index Out of Bounds
Description: Trailing stop fails if <14 candles, causing index errors. Validate candle count.

File:

trade_engine.py (ID: ae8326f4, updated in Step 1)
Apply:

Use trade_engine.py from Step 1.
Test:

Use /panic YES to close positions.
Start bot with ENABLE_TRAILING = True.
Wait for bot to open a position.
Check telegram_log.txt for [ERROR] Insufficient data for trailing stop (fallback used).
Verify no [ERROR] Trailing init fallback: index 14 is out of bounds.
Close position with /stop, check tp_performance.csv.
Check Error:

Fixed: No index errors, fallback used or closure logged.
Not Fixed: Index errors in logs.
Step 5: Fix Break-Even Error: decimal.ConversionSyntax
Description: Break-even fails due to type mismatch in stop_price. Use float.

File:

trade_engine.py (ID: ae8326f4, updated in Step 1)
Apply:

Use trade_engine.py from Step 1.
Test:

Use /panic YES to close positions.
Start bot with ENABLE_BREAKEVEN = True.
Wait for bot to open a position and trigger break-even.
Check telegram_log.txt for [DEBUG] Creating break-even and no [ERROR] create_break_even ... decimal.ConversionSyntax.
Verify on Binance: break-even stop order set.
Close position with /stop, check tp_performance.csv.
Check Error:

Fixed: Break-even orders set, no type errors.
Not Fixed: [ERROR] create_break_even ... decimal.ConversionSyntax.
Step 6: Fix SmartSwitch Error: 'ResultType'
Description: SmartSwitch fails due to wrong column. Already fixed in engine_controller.py.

File:

None
Apply:

Confirm engine_controller.py uses df[df["Result"] == "smart_switch"].
Test:

Use /panic YES to close positions.
Start bot.
Wait for bot to open a position and trigger SmartSwitch.
Check telegram_log.txt for [SmartSwitch] Closed without [SmartSwitch] Failed ... 'ResultType'.
Verify closure in tp_performance.csv.
Check Error:

Fixed: No ResultType errors, closures logged.
Not Fixed: ResultType errors (unlikely).
Implementation Workflow
Prep:
Backup codebase and tp_performance.csv.
Update config.py with safe settings.
Use /panic YES to clear positions.
Apply Fixes:
Replace files with artifacts per step.
Run bot: cd c:/Bots/BinanceBot && python main.py.
Test as described, checking telegram_log.txt and tp_performance.csv.
Stop bot after each test (Ctrl+C or /stop).
Monitor:
Share telegram_log.txt if errors persist.
Proceed to next step after fixing current error.
Final Check:
Run bot for 1 hour after all fixes.
Verify tp_performance.csv logs all trades, no errors in logs.
Confirmation
The revised plan includes all fixes from to_fix_real_run.md, including the MAX_OPEN_ORDERS addition. Each issue is addressed in a specific step, with artifacts covering all necessary changes. The plan prioritizes MAX_POSITIONS and tp_performance.csv in Step 1, ensuring critical issues are fixed first while maintaining safe testing.

Next Steps
Start Step 1:
Apply main.py, trade_engine.py, tp_logger.py, config.py, symbol_processor.py.
Test in REAL_RUN, check MAX_POSITIONS (≤3), MAX_OPEN_ORDERS (≤10), and tp_performance.csv.
Share telegram_log.txt or results.
Continue:
Move to Step 2 after Step 1 is fixed.
Follow Steps 3-6, testing each.
Report Issues:
Share logs if errors occur.
I’ll provide targeted fixes.
Ready to start Step 1? Let me know if you need help applying artifacts or have questions! 😊
