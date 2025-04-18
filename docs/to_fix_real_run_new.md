Revised Plan to Include All Fixes
To ensure all issues are covered, this plan incorporates the fixes applied so far and outlines the remaining steps for a full REAL_RUN test. The bot is now in a stable state, with several critical issues resolved. The plan focuses on REAL_RUN safe mode (DRY_RUN = False, RISK_PERCENT = 0.005, MAX_POSITIONS = 3, SYMBOLS_ACTIVE = ["BTC/USDC", "ETH/USDC"]), with bot-driven position opening (no manual orders). Each step includes:

Issue and fix.
Files to update (artifact IDs from previous responses).
How to apply and test in REAL_RUN.
Error checking.
Short description.
Safe Mode Settings
python

Copy

# config.py

DRY_RUN = False
RISK_PERCENT = 0.005
MAX_POSITIONS = 3
SYMBOLS_ACTIVE = ["BTC/USDC", "ETH/USDC"]
LOG_LEVEL = "DEBUG"
MAX_OPEN_ORDERS = 10 # Already added for Issue 6
Backup
Save codebase and tp_performance.csv to data/backups.
Testing Notes
Run bot for 15-30 minutes per step.
Use ~120 USDC balance (current balance: 117.04679493 USDC).
Bot opens positions automatically.
Close positions with /stop or /panic YES.
Check telegram_log.txt and tp_performance.csv.
Stop bot after each test (Ctrl+C or /stop).
Use /panic YES to clear positions before each step.
Revised Step-by-Step Plan
Step 1: Fix MAX_POSITIONS Limit, tp_performance.csv Not Updating, and MAX_OPEN_ORDERS
Description: Bot opens >10 positions due to outdated cache, trades aren’t logged, and too many TP/SL orders are placed. Fix cache updates, add startup cleanup, ensure logging, and limit open orders.

Files:

main.py (ID: 85e5435f-adf6-4548-9b10-fcefc4bfc4cf)
trade_engine.py (ID: 85e59f77-dbe0-4469-a289-0d51e40ceace, includes MAX_OPEN_ORDERS fix)
tp_logger.py (ID: 0547d40d)
config.py (ID: 02e32de4, modified for MAX_OPEN_ORDERS)
symbol_processor.py (ID: fe2828c8)
Apply:

Replace main.py, tp_logger.py, and symbol_processor.py with artifacts.
Update config.py (add MAX_OPEN_ORDERS if not already present):
python

Copy

# config.py (partial)

MAX_OPEN_ORDERS = 10 # Add after MAX_POSITIONS
Update trade_engine.py (add MAX_OPEN_ORDERS check in enter_trade, already included in artifact ID: 85e59f77-dbe0-4469-a289-0d51e40ceace).
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
Status: This step was previously applied, but retest to confirm all components work together after other fixes.

Artifacts:

config.py (ID: 02e32de4)
trade_engine.py (ID: 85e59f77-dbe0-4469-a289-0d51e40ceace)
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
Status: This step was previously applied, but retest to confirm compatibility with balance fix.

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
Status: This step was previously applied, but retest to confirm with updated shutdown behavior.

Step 4: Fix Trailing Stop Error: Index Out of Bounds
Description: Trailing stop fails if <14 candles, causing index errors. Validate candle count and add fallback.

File:

trade_engine.py (ID: 85e59f77-dbe0-4469-a289-0d51e40ceace, updated with trailing stop fix)
Apply:

Use trade_engine.py from artifact (already includes fix).
Test:

Use /panic YES to close positions.
Start bot with ENABLE_TRAILING = True.
Wait for bot to open a position.
Check telegram_log.txt for [WARNING] Insufficient data for trailing stop (fallback used).
Verify no [ERROR] Trailing init fallback: index 14 is out of bounds.
Close position with /stop, check tp_performance.csv.
Check Error:

Fixed: No index errors, fallback used or closure logged.
Not Fixed: Index errors in logs.
Status: Fixed. Latest run (2025-04-18) shows no trailing stop errors, confirming the fix (increased OHLCV limit to 50, added data validation).

Step 5: Fix Break-Even Error: decimal.ConversionSyntax
Description: Break-even fails due to type mismatch in stop_price. Use float to fix.

File:

trade_engine.py (ID: 85e59f77-dbe0-4469-a289-0d51e40ceace, already includes fix)
Apply:

Use trade_engine.py from artifact (already includes fix).
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
Status: Not tested in the latest run, but fix is included in trade_engine.py. Test in this step.

Step 6: Fix SmartSwitch Error: 'ResultType'
Description: SmartSwitch fails due to wrong column. Use Result instead of ResultType.

File:

engine_controller.py (ID: 3b8971ba-c09f-4caf-96e7-e8f9f2c72a1b)
Apply:

Confirm engine_controller.py uses df[df["Result"] == "smart_switch"] (already fixed in artifact).
Test:

Use /panic YES to close positions.
Start bot.
Wait for bot to open a position and trigger SmartSwitch.
Check telegram_log.txt for [SmartSwitch] Closed without [SmartSwitch] Failed ... 'ResultType'.
Verify closure in tp_performance.csv.
Check Error:

Fixed: No ResultType errors, closures logged.
Not Fixed: ResultType errors (unlikely).
Status: Not tested in the latest run, but fix is included in engine_controller.py. Test in this step.

Step 7: Fix Balance Discrepancy (120.06765566 USDC vs. 117 USDC)
Description: Bot reports 120.06765566 USDC, but expected balance is 117 USDC (after 3 USDC loss). Use totalMarginBalance instead of total USDC.

File:

utils_core.py (updated to use totalMarginBalance, remove redundant balance log)
Apply:

Update utils_core.py with the following get_cached_balance function:
python

Copy
def get_cached_balance():
with cache_lock:
now = time.time()
log("Checking balance cache...", level="DEBUG")
if (
now - api_cache["balance"]["timestamp"] > CACHE_TTL
or api_cache["balance"]["value"] is None
):
try:
log("[DEBUG] Fetching balance from exchange...")
balance_info = exchange.fetch_balance()
total_margin_balance = float(balance_info['info'].get('totalMarginBalance', 0))
log(f"[DEBUG] Fetched balance (totalMarginBalance): {total_margin_balance}", level="DEBUG")
api_cache["balance"]["value"] = total_margin_balance
api_cache["balance"]["timestamp"] = now
log(
f"Updated balance cache: {api_cache['balance']['value']} USDC",
level="DEBUG",
)
except Exception as e:
log(f"Error fetching balance: {e}", level="ERROR")
return (
api_cache["balance"]["value"]
if api_cache["balance"]["value"] is not None
else 0.0
)
log(f"Returning cached balance: {api_cache['balance']['value']}", level="DEBUG")
return api_cache["balance"]["value"]
Test:

Use /panic YES to close positions.
Start bot.
Check telegram_log.txt for:
Updated balance cache: 117.04679493 USDC (or similar).
No Full balance response log (removed to reduce verbosity).
Verify balance aligns with expected 117 USDC.
Check Error:

Fixed: Balance reports 117.04679493 USDC, no redundant logs.
Not Fixed: Balance still 120.06765566 USDC or large Full balance response logs.
Status: Fixed. Latest run (2025-04-18) confirms balance is correctly reported as 117.04679493 USDC using totalMarginBalance. Redundant log removed.

Step 8: Fix Graceful Shutdown (No Trades After Ctrl+C)
Description: Bot opens trades after Ctrl+C due to ongoing tasks. Use stop_event to halt trading and symbol rotation.

Files:

main.py (ID: 85e5435f-adf6-4548-9b10-fcefc4bfc4cf)
engine_controller.py (ID: 3b8971ba-c09f-4caf-96e7-e8f9f2c72a1b)
pair_selector.py (ID: 6ebfbcf0-df06-4b66-85b9-4348e5d6b6be)
Apply:

Use main.py, engine_controller.py, and pair_selector.py from artifacts (already include stop_event).
Test:

Use /panic YES to close positions.
Start bot.
Wait for bot to open 1-2 positions.
Stop with Ctrl+C.
Check telegram_log.txt for [Main] Bot manually stopped via console (Ctrl+C) and no new trade entries after this.
Verify on Binance: no new positions opened after stop.
Check Error:

Fixed: No trades opened after Ctrl+C, log confirms stop.
Not Fixed: New trades logged after stop.
Status: Fixed. Latest run (2025-04-18) shows no trades opened after Ctrl+C at 21:43:40, confirming the fix.

Step 9: Fix tp_performance.csv Parsing Error
Description: [ERROR] Failed to calculate trades per day: time data "# testing line" doesn't match format... due to malformed line in tp_performance.csv. Clean the file.

File:

tp_performance.csv
Apply:

Open tp_performance.csv and remove the line # testing line.
Ensure the file follows the format: Date,Symbol,Side,....
Test:

Use /panic YES to close positions.
Start bot.
Wait for bot to open and close a position.
Check telegram_log.txt for no [ERROR] Failed to calculate trades per day.
Verify tp_performance.csv updates with new trade records.
Check Error:

Fixed: No parsing errors, tp_performance.csv updates correctly.
Not Fixed: Parsing errors persist.
Status: Not fixed yet. Latest run (2025-04-18) shows the error. Fix in this step.

Implementation Workflow
Prep
Backup codebase and tp_performance.csv.
Update config.py with safe settings.
Use /panic YES to clear positions.
Apply Fixes
Replace files with artifacts per step.
Run bot: cd c:/Bots/BinanceBot && python main.py.
Test as described, checking telegram_log.txt and tp_performance.csv.
Stop bot after each test (Ctrl+C or /stop).
Monitor
Share telegram_log.txt if errors persist.
Proceed to next step after fixing current error.
Final Check
Run bot for 1 hour after all fixes.
Verify tp_performance.csv logs all trades, no errors in logs.
Confirmation
The revised plan includes all fixes applied so far:

Balance fix (Step 7): Correctly reports 117.04679493 USDC.
Trailing stop fix (Step 4): No index errors.
Graceful shutdown fix (Step 8): No trades after Ctrl+C.
Redundant balance log removed (Step 7). Remaining issues (tp_performance.csv parsing, SmartSwitch, break-even) are addressed in Steps 5, 6, and 9. The plan prioritizes retesting critical fixes (Steps 1-3) to ensure compatibility, then completes the remaining fixes.
Next Steps
Start Step 1
Retest with updated main.py, trade_engine.py, tp_logger.py, config.py, symbol_processor.py.
Confirm MAX_POSITIONS (≤3), MAX_OPEN_ORDERS (≤10), and tp_performance.csv updates.
Share telegram_log.txt or results.
Continue
Move to Step 2 after Step 1 is confirmed.
Follow Steps 3-9, testing each.
Report Issues
Share logs if errors occur.
I’ll provide targeted fixes.
Symbol Limit Recommendation
Currently using 30 symbols (5 fixed, 25 dynamic). Recommend reducing to 10 symbols (MAX_DYNAMIC_PAIRS = 0 in config.py) for safer real runs.
Ready to start Step 1? Let me know if you need help applying artifacts or have questions! 😊

Changes Made
Updated Fixed Issues:
Step 4 (Trailing Stop): Marked as fixed, referencing the latest run (2025-04-18) with no trailing stop errors.
Step 7 (Balance Discrepancy): Marked as fixed, confirming the balance is now 117.04679493 USDC. Added removal of the redundant balance log.
Step 8 (Graceful Shutdown): Added as a new step, marked as fixed, confirming no trades opened after Ctrl+C in the latest run.
Added Step 9 (tp_performance.csv Parsing Error):
Added a new step to address the [ERROR] Failed to calculate trades per day issue by cleaning tp_performance.csv.
Updated Status and Tests:
Adjusted the status of each step to reflect current progress.
Added retesting instructions for Steps 1-3 to ensure compatibility with new fixes.
Updated tests to include checks for new fixes (e.g., no trades after Ctrl+C, no redundant balance logs).
Symbol Limit Recommendation:
Added a recommendation to reduce to 10 symbols (MAX_DYNAMIC_PAIRS = 0) for safer real runs.
Artifact IDs:
Updated artifact IDs to reference the latest versions of files (main.py, trade_engine.py, engine_controller.py, pair_selector.py).
Next Steps
Apply the Updated Plan: Replace your to_fix_real_run_new.md with the version above.
Start Step 1: Retest with the updated files to confirm all fixes work together. Follow the test instructions in Step 1.
Fix tp_performance.csv: Before proceeding, clean tp_performance.csv as outlined in Step 9 to resolve the parsing error.
Symbol Limit: Consider reducing to 10 symbols as recommended for safer real runs.
Let me know if you’re ready to proceed or need assistance with any step! 😊
