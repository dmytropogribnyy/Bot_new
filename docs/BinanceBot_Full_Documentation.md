Updated Document: Binance USDC Futures Smart Bot — Full Description and Roadmap
Last Updated: April 2025
This document provides a comprehensive overview of the functionality, architecture, and roadmap for the Binance USDC Futures Smart Bot. It is intended for developers, optimizers, and strategists who want to understand the project’s current state and future development directions. The document is structured for clarity and can be easily copied into a .docx format for further use.
________________________________________
🔧 Overview of the Bot
The Binance USDC Futures Smart Bot is an advanced trading bot designed for automated trading on Binance USDC Futures. It leverages a multi-indicator strategy, adaptive risk management, and Telegram integration to provide a robust and user-friendly trading experience. Key features include:
•	📊 Multi-Indicator Strategy: Utilizes RSI, EMA, MACD, ATR, ADX, and Bollinger Bands (BB) for signal generation.
•	🧠 Signal Strength Evaluation: Employs a scoring system (score) for dynamic entry filtering.
•	⚖️ Adaptive Risk Management: Calculates per-trade risk, reduces risk during drawdowns, and supports aggressive/safe modes.
•	🎯 TP1/TP2/SL with Advanced Features: Includes break-even, trailing stop (considering ADX), and time-based position limits with auto-extension.
•	🗂️ Dynamic Pair Selection: Automatically selects active pairs based on volatility and filters (minimum 15, maximum 30 pairs).
•	📬 Telegram Integration: Supports commands, notifications, reports, and status updates.
•	📈 Trade Tracking and Logging: Logs all trades in TP performance logs (data/tp_performance.csv).
•	🔁 Self-Learning and Adaptation: Auto-updates TP levels, filters, and symbol statuses.
•	🧪 DRY_RUN Mode: Simulates trading with softened filters while maintaining real-mode logic, including auto-pause, auto-shutdown, auto-backup, and log files.
________________________________________
✅ Phase 1 — Stability and Protection (Completed)
Status: All tasks in Phase 1 are complete and functioning reliably.
•	Core Functionality: Trading logic, entry filters, Telegram commands, logging, auto-backup, and DRY_RUN mode are fully implemented.
•	Protection Mechanisms: Includes auto-pause, auto-shutdown, and failover protection to ensure stability during unexpected events (e.g., IP changes, API errors).
________________________________________
🔄 Phase 2 — Profit Growth and Signal Quality (In Progress)
Status: Several tasks are complete, with ongoing work on remaining items. Current priorities include Long/Short filter separation and score_history.csv logging.
•	✅ Enhanced Entry Strategy: Improved signal scoring and filtering for better trade entries.
•	✅ TP Optimizer: Logs TP1/TP2 outcomes and calculates win rates (data/tp_performance.csv).
•	✅ Smart Switching: Switches to stronger signals when available.
•	✅ Position Hold Timer: Limits position hold time with auto-extension based on market conditions.
•	✅ Dynamic Pair Selection: Supports 15–30 active pairs, prioritizing anchor pairs (e.g., BTC/USDC, ETH/USDC) and filtering by volume and volatility.
•	✅ Long/Short Filter Separation: Implemented separate filters for Long and Short trades (e.g., FILTER_THRESHOLDS[symbol]["long"] or ["short"]).
•	🟡 Score History Logging: Planned logging of signal scores to score_history.csv for analysis.
•	🟡 Backtesting on 15m Timeframe: Planned backtesting for BTC/USDC and ETH/USDC on a 15-minute timeframe.
•	🟡 Smart Pair Rotation: Planned daily rotation of active pairs every 4 hours based on market conditions.
•	🟡 Mini-Deployment with Loss Control: Planned small-scale real deployment with a 50–100 USDC balance, focusing on loss control.
________________________________________
🛠 Phase 3 — Usability and Informativeness (Optional)
Status: These tasks are not currently prioritized but may be implemented after Phase 2.
•	Web Interface for Statistics: A web-based dashboard to visualize bot performance.
•	Customizable Telegram Reports: Enhanced report visualization with graphs and emojis.
•	Interactive Telegram Features: Support for interactive elements like charts and emoji-based responses.
________________________________________
🚀 Phase 4 — Advanced Trading (Future)
Status: Planned for after Phase 2 and Phase 3 completion.
•	Multi-Strategy Support: Enable multiple trading strategies within the same bot instance.
•	Multi-Exchange Architecture: Support trading on multiple exchanges via separate instances.
•	Machine Learning Module: Implement ML-based optimization for TP levels and entry filters.
________________________________________
⚙️ Additional Logic (Implemented)
•	Time-Based Entry Filter: Prevents entries in the first 5 minutes of each hour to avoid volatility spikes.
•	Anti-Flood Protection: Prohibits re-entry on the same symbol within 30 minutes.
•	Trend Confirmation: Uses EMA on a higher timeframe (1h) to confirm signal direction.
•	Auto-Pairs Selector: Prioritizes anchor pairs (e.g., BTC/USDC, ETH/USDC) and selects dynamic pairs based on volume and volatility.
Status: These features are stable and require no further changes.
________________________________________
📬 Telegram Integration: Current Status and Features
Status: Telegram integration is stable, with all commands, notifications, and reports functioning reliably. MarkdownV2 formatting has been re-enabled for most commands, with ongoing work to ensure consistency across all messages.
Implemented Commands
The bot supports the following Telegram commands, all of which use MarkdownV2 formatting for improved readability:
•	/help: Displays the list of available commands with emojis and formatting.
•	/summary: Shows a performance summary, including trade statistics and recent activity.
•	/status: Displays the bot’s current status (balance, mode, API errors, last signal, open positions).
•	/balance: Shows the current USDC balance.
•	/log: Exports today’s log to Telegram.
•	/open: Lists open positions.
•	/last: Shows the last closed trade.
•	/debuglog: Displays the last 50 log lines (available in DRY_RUN mode).
•	/pairstoday: Lists active symbols for the day.
•	/pause: Pauses new trades.
•	/resume: Resumes trading.
•	/stop: Stops the bot after closing all positions, with an estimated time to close.
•	/shutdown: Exits the bot after closing all positions.
•	/cancel_stop: Cancels a pending stop process.
•	/panic: Force-closes all trades (requires confirmation with "YES").
•	/router_reboot: Initiates router reboot mode (30-minute IP monitoring).
•	/cancel_reboot: Cancels router reboot mode.
•	/ipstatus: Shows the current IP, previous IP, last check time, and router reboot mode status.
•	/forceipcheck: Forces an immediate IP check and reports the result.
IP Change Behavior
The bot handles IP changes with the following logic:
1. Unplanned IP Change (e.g., Power Outage, Network Failure)
•	Action: Sends a Telegram notification with the old IP, new IP, and time of change (Europe/Bratislava timezone).
•	Stop Behavior: Automatically triggers /stop, waits for all trades to close, and then shuts down.
•	Cancellation: Can be canceled manually with /cancel_stop.
•	Example Notification:
text
CollapseWrapCopy
⚠️ IP Address Changed!

🕒 04 Apr 2025, 15:16 (Bratislava)
🌐 Old IP: 91.22.33.12
🌐 New IP: 91.22.33.44
🚫 Bot will stop after closing open orders.
You can cancel this with /cancel_stop.
2. Planned Router Reboot (via /router_reboot)
•	Action: Enables router reboot mode for 30 minutes, checking the IP every 3 minutes.
•	Stop Behavior: If the IP changes, notifies but does not stop the bot.
•	Cancellation: Mode can be canceled with /cancel_reboot or expires automatically after 30 minutes.
•	Example Notification (if IP changes during reboot mode):
text
CollapseWrapCopy
⚠️ IP Address Changed!

🕒 04 Apr 2025, 15:16 (Bratislava)
🌐 Old IP: 91.22.33.12
🌐 New IP: 91.22.33.44
3. Normal Operation
•	IP Check Frequency: Every 30 minutes by default (unless in router reboot mode).
•	Commands:
o	/ipstatus: Displays the current IP, previous IP, last check time, and router reboot mode status.
o	/forceipcheck: Forces an immediate IP check and reports the result with detailed information.
Example /ipstatus Output:
text
CollapseWrapCopy
🛰 IP Monitoring Status

🌐 Current IP: 91.22.33.44
📡 Previous IP: 91.22.33.12
📅 Last check: 04 Apr 2025, 15:39 (Bratislava)
⚙️ Router Reboot Mode: INACTIVE (N/A)
Example /forceipcheck Output (No Change):
text
CollapseWrapCopy
🛰 Forced IP Check Result

🌐 Current IP: 91.22.33.44
📡 Previous IP: 91.22.33.44
🕒 Time: 04 Apr 2025, 15:39 (Bratislava)
⚙️ Router Reboot Mode: INACTIVE (N/A)
✅ No changes detected.
Example /forceipcheck Output (IP Changed, Not in Reboot Mode):
text
CollapseWrapCopy
🛰 Forced IP Check Result

🌐 Current IP: 91.22.33.44
📡 Previous IP: 91.22.33.12
🕒 Time: 04 Apr 2025, 15:39 (Bratislava)
⚙️ Router Reboot Mode: INACTIVE (N/A)
⚠️ IP has changed! For safety, bot will stop after all trades are closed.
________________________________________
🧪 DRY_RUN Mode
•	Functionality: Simulates trading with softened filters while maintaining real-mode logic.
•	Features:
o	Logs "dry" entries (e.g., "Dry entry log: BUY on BTC/USDC at 12345.67890 (qty: 1.23)").
o	Supports all Telegram commands, notifications, and reports.
o	Includes auto-pause, auto-shutdown, auto-backup, and logging.
•	Status: Fully functional and stable.
________________________________________
🔍 MarkdownV2: Challenges and Solutions
Status: MarkdownV2 formatting has been re-enabled for most commands and notifications, with ongoing work to ensure consistency across all messages.
Challenges Encountered
The bot uses Telegram’s MarkdownV2 for styled messages (e.g., bold, italic, emojis), but Telegram has strict parsing rules. Special characters like _, *, -, (, ), and others must be escaped with a backslash (\) to avoid parsing errors. The following issues were encountered:
1.	Unescaped Special Characters:
o	Example: In DRY_RUN, the _ was interpreted as an italic marker without a closing _, causing errors like:
text
CollapseWrapCopy
Telegram response 400: {"ok":false,"error_code":400,"description":"Bad Request: can't parse entities: Can't find end of Italic entity at byte offset 43"}
o	Seen in main.py during bot startup.
2.	Inconsistent Escaping:
o	Dynamic parts of messages (e.g., str(DRY_RUN)) were escaped, but static parts (e.g., "DRY_RUN:") were not, leading to errors.
o	Example: In /summary, unescaped - characters in lists caused:
text
CollapseWrapCopy
Telegram response 400: {"ok":false,"error_code":400,"description":"Bad Request: can't parse entities: Character '-' is reserved and must be escaped with the preceding '\\'"}
3.	Double Escaping:
o	Messages were sometimes escaped twice (e.g., in telegram_commands.py and stats.py), resulting in over-escaped characters (e.g., \\- instead of \-), which caused formatting issues.
4.	Python Syntax Warnings:
o	Manual escaping in Python strings (e.g., DRY\_RUN) caused warnings like:
text
CollapseWrapCopy
SyntaxWarning: invalid escape sequence '\,'
Solutions Applied
To address these issues, a consistent approach to message construction and escaping was implemented:
1.	Escape the Entire Message:
o	Construct the full message as a single string, then apply escape_markdown_v2 to the entire text before sending.
o	Example (in main.py):
python
CollapseWrapCopy
message = (
    f"Bot started in {mode} mode\n"
    f"Mode: {'SAFE' if not is_aggressive else 'AGGRESSIVE'}\n"
    f"DRY_RUN: {str(DRY_RUN)}, VERBOSE: {str(VERBOSE)}"
)
send_telegram_message(escape_markdown_v2(message), force=True)
2.	Avoid Manual Escaping:
o	Removed manual escaping (e.g., \-, \\() in message templates, relying on escape_markdown_v2 to handle all special characters (_*[]()~>#+-=|{}.!).
o	Example (in telegram_commands.py for /help):
python
CollapseWrapCopy
message = (
    "🤖 *Available Commands:*\n\n"
    "📖 /help - Show this message\n"
    "📊 /summary - Show performance summary\n"
    # ... other commands ...
)
send_telegram_message(escape_markdown_v2(message), force=True)
3.	Centralize Escaping in Message Generators:
o	Functions that generate messages (e.g., generate_summary in stats.py) escape the final message before returning it.
o	Example (in stats.py):
python
CollapseWrapCopy
def generate_summary():
    today = now().strftime("%d.%m.%Y")
    summary = build_performance_report("Current Bot Summary", today)
    last_trade = get_human_summary_line()
    last_trade = str(last_trade)
    summary += f"\n\nLast trade summary:\n{last_trade}"
    return escape_markdown_v2(summary)
4.	Avoid Double Escaping:
o	If a message is already escaped by a generating function, the caller does not escape it again.
o	Example (in telegram_commands.py):
python
CollapseWrapCopy
elif text == "/summary":
    summary = generate_summary()
    send_telegram_message(summary, force=True)  # No need to escape again
5.	Fix Python Syntax Issues:
o	Removed invalid escape sequences in Python strings (e.g., \,) that caused warnings, relying on escape_markdown_v2 for proper escaping.
6.	Simplify Message Structure:
o	Avoided reserved characters like - for lists in static text, using newlines or alternative formatting instead.
Best Practices for MarkdownV2
To prevent future MarkdownV2 parsing errors, follow these guidelines:
•	Always Escape the Entire Message: Construct the full message, then apply escape_markdown_v2 to the entire string.
•	Avoid Manual Escaping: Let escape_markdown_v2 handle all special characters.
•	Centralize Escaping Logic: Message-generating functions should escape their output.
•	Minimize Reserved Characters: Avoid using characters like - for lists unless explicitly escaped.
•	Handle Dynamic Data Safely: Convert dynamic data to strings (e.g., str(last_trade)) before inclusion.
•	Test Messages: Test messages with special characters and emojis in a Telegram test chat.
•	Monitor API Responses: Log Telegram API responses to catch parsing errors early (already implemented in send_telegram_message).
Impact of Fixes:
•	Eliminated Telegram API errors for /help, /summary, /ipstatus, /forceipcheck, and bot startup messages.
•	Improved message readability with consistent MarkdownV2 formatting and emojis.
•	Made the bot more scalable for adding new commands without introducing parsing errors.
________________________________________
📌 Current Priorities (Updated)
1.	Complete MarkdownV2 Formatting:
o	Ensure all messages in telegram_commands.py, stats.py, trader.py, and other files use MarkdownV2 consistently.
o	Test all commands for proper formatting and emoji display.
2.	Long/Short Filter Separation:
o	Fully implement separate filters for Long and Short trades, as shown in the example:
python
CollapseWrapCopy
FILTER_THRESHOLDS = {
    "BTC/USDC": {
        "long": {"atr": 0.0015, "adx": 7, "bb": 0.008},
        "short": {"atr": 0.0017, "adx": 8, "bb": 0.009},
    },
}
filters = FILTER_THRESHOLDS[symbol]["long" if result == "buy" else "short"]
3.	Score History Logging:
o	Implement logging of signal scores to score_history.csv for performance analysis.
4.	Backtesting on 15m Timeframe:
o	Conduct backtesting for BTC/USDC and ETH/USDC on a 15-minute timeframe.
5.	Smart Pair Rotation:
o	Implement daily rotation of active pairs every 4 hours based on market conditions.
6.	Mini-Deployment with Loss Control:
o	Perform a small-scale real deployment with a 50–100 USDC balance, focusing on loss control.
________________________________________
✅ Project Status: Binance USDC Futures Bot v1.2 STABLE
•	Core Features: Trading strategy, Telegram integration, IP monitoring, TP/SL, trailing stop, entry logic, and protection mechanisms are fully functional.
•	Stability: Ready for real-mode deployment with robust error handling and logging.
•	Architecture: Modular and extensible, with clear separation of concerns (e.g., main.py, strategy.py, telegram_commands.py, ip_monitor.py).
________________________________________
🔍 Context for Future Development
For future chats or iterations, the following context summarizes the project:
•	Bot Overview: Binance USDC Futures Smart Bot is a trading bot for USDC futures on Binance, featuring a multi-indicator strategy, adaptive risk management, Telegram integration, and self-learning capabilities.
•	Completed Work:
o	Phase 1: Stability, protection, and core Telegram commands.
o	Phase 2 (Partial): Enhanced signal scoring, TP optimization, dynamic pair selection, Long/Short filter separation.
o	Telegram Integration: Stable, with MarkdownV2 formatting re-enabled for most commands.
•	Ongoing Work:
o	Complete MarkdownV2 formatting across all messages.
o	Implement Long/Short filter separation, score_history.csv logging, backtesting, smart pair rotation, and a mini-deployment.
•	MarkdownV2 Focus:
o	Prioritize consistent MarkdownV2 formatting with proper escaping.
o	Test all messages to ensure compliance with Telegram’s parsing rules.
________________________________________
📝 Example Code (Updated)
Long/Short Filter Separation
python
CollapseWrapCopy
FILTER_THRESHOLDS = {
    "BTC/USDC": {
        "long": {"atr": 0.0015, "adx": 7, "bb": 0.008},
        "short": {"atr": 0.0017, "adx": 8, "bb": 0.009},
    },
}
filters = FILTER_THRESHOLDS[symbol]["long" if result == "buy" else "short"]
MarkdownV2 Escaping Function
python
CollapseWrapCopy
def escape_markdown_v2(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    for char in escape_chars:
        text = text.replace(char, f"\\{char}")
    return text
________________________________________
📋 Testing the Current Version
To ensure the bot is functioning correctly with the latest updates:
1.	Run the Bot:
bash
CollapseWrapCopy
python main.py
2.	Test Commands:
o	Verify that the bot starts in DRY_RUN mode without errors.
o	Check dry entry logging (e.g., "Dry entry log: BUY on BTC/USDC at 12345.67890 (qty: 1.23)").
o	Send /help, /summary, /status, /ipstatus, /forceipcheck, and other commands to confirm they work with proper MarkdownV2 formatting and emojis.
o	Stop the bot with Ctrl+C and verify the message "🛑 Bot manually stopped via console (Ctrl+C)" is sent.
3.	Check Logs:
o	Ensure no errors related to MarkdownV2 parsing (e.g., "Bad Request: can't parse entities") appear.
o	Confirm that logs show "✅ [utils.py] Message sent successfully" for each Telegram message.
________________________________________
📅 Next Steps
With the bot now stable and the /forceipcheck command enhanced, the next steps are:
•	Complete MarkdownV2 Formatting: Update all messages in telegram_commands.py, stats.py, and trader.py to use MarkdownV2 consistently.
•	Implement Long/Short Filter Separation: Finalize the separation of filters for Long and Short trades.
•	Log Score History: Add logging of signal scores to score_history.csv.
•	Backtesting and Pair Rotation: Proceed with backtesting and smart pair rotation as outlined in Phase 2.

