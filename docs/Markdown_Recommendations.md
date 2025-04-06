# MarkdownV2 Recommendations for Binance USDC Futures Smart Bot

**Last Updated**: April 2025

This document summarizes Telegram MarkdownV2 parsing errors encountered during the development of the Binance USDC Futures Smart Bot (v1.2 STABLE), their causes, fixes applied, and best practices to avoid recurrence. It’s a guide for ensuring reliable Telegram integration.

---

## Overview

The bot uses Telegram for notifications and commands (e.g., `/help`, `/summary`), leveraging MarkdownV2 for styled messages (bold, italic, emojis). Telegram’s strict parsing rules require escaping special characters (e.g., `_`, `-`, `*`) with a backslash (`\`). Unescaped characters caused recurring API errors, now resolved.

---

## Errors Encountered

### 1. Unclosed Italic Marker

- **Error**: `Telegram response 400: can't parse entities: Can't find end of Italic entity at byte offset 43`
- **Where**: `main.py` (`start_trading_loop`)
- **Cause**: Unescaped `_` in `DRY_RUN`, interpreted as start of italic.

### 2. Reserved Character Parsing

- **Error**: `Telegram response 400: Character '-' is reserved and must be escaped with '\'`
- **Where**: `telegram_commands.py` (`/summary`)
- **Cause**: Unescaped `-` in messages (e.g., "waiting for signals - nothing yet")

### 3. Preemptive Fixes

- Issues anticipated and avoided in `/help`, `/status`, etc. by escaping `-`, `(`, `)`.

---

## Root Causes

- **Unescaped Characters**: MarkdownV2 reserves `_`, `*`, `-`, `(`, `)` — they must be escaped.
- **Inconsistent Escaping**: Only dynamic content escaped; static text like "DRY_RUN:" was not.
- **Double Escaping**: Messages escaped twice (e.g., in generator and sender), breaking formatting.
- **Python Warnings**: Invalid escapes like `\,` triggered syntax warnings.

---

## Fixes Applied

### 1. Escape Entire Messages

Instead of escaping fragments:

```python
message = (
    f"Bot started in {mode} mode\n"
    f"Mode: {'SAFE' if not is_aggressive else 'AGGRESSIVE'}\n"
    f"DRY_RUN: {str(DRY_RUN)}, VERBOSE: {str(VERBOSE)}"
)
send_telegram_message(escape_markdown_v2(message), force=True)
```

### 2. Remove Manual Escapes

Let `escape_markdown_v2` handle all characters:

```python
message = (
    "🤖 *Available Commands:*\n\n"
    "📖 /help - Show this message\n"
    "📊 /summary - Show summary\n"
)
send_telegram_message(escape_markdown_v2(message), force=True)
```

### 3. Centralize Escaping in Generators

Escape directly inside functions like `generate_summary()`:

```python
def generate_summary():
    today = now().strftime("%d.%m.%Y")
    summary = build_performance_report("Current Bot Summary", today)
    last_trade = str(get_human_summary_line())
    summary += f"\n\nLast trade summary:\n{last_trade}"
    return escape_markdown_v2(summary)
```

### 4. Avoid Double Escaping

Call `send_telegram_message(summary)` directly if already escaped.

### 5. Fix Python Syntax

Remove `\,` and similar invalid sequences:

```python
# Before:
message = f"DRY\_RUN: {escape_markdown_v2(str(DRY_RUN))}\\, VERBOSE: ..."

# After:
message = f"DRY_RUN: {str(DRY_RUN)}, VERBOSE: ..."
message = escape_markdown_v2(message)
```

### 6. Simplify Message Structure

Avoid `-` and lists unless necessary. Prefer newlines or emojis.

```python
report = (
    f"📊 *{title}*\n"
    f"Trades: {total} (W: {wins} / L: {losses})\n"
    f"PnL: {'+' if pnl >= 0 else ''}{pnl} USDC\n"
)
```

---

## Best Practices

- **Escape Entire Messages**: Always apply `escape_markdown_v2` after message construction.
- **Test with Special Characters**: Use a private Telegram chat to test before deploying.
- **Centralize Escaping**: Do escaping inside generators to ensure consistency.
- **Avoid Reserved Characters**: Use emojis or alternative symbols when possible.
- **Handle Dynamic Data**: Always convert to string with `str()` before escaping.
- **Monitor Responses**: Log success/failure of each Telegram message (already in `utils.py`).

---

## Impact of Fixes

- ✅ Eliminated Telegram API 400 errors
- ✅ Reliable MarkdownV2 formatting in all commands
- ✅ Easier maintenance and scaling

---
