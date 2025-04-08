# ✅ Telegram Messaging Guide for BinanceBot v1.6.1-final

This is the final and unified guide for how to correctly handle all Telegram messages in the BinanceBot system. It reflects all recent fixes, best practices, and escaping rules to ensure zero MarkdownV2 errors and clean message output.

---

## ✅ Message Formatting Rules

| Context                 | parse_mode     | Use escape_markdown_v2? | Notes                                        |
| ----------------------- | -------------- | ----------------------- | -------------------------------------------- |
| DRY_RUN, logs, status   | `""` or `None` | ❌ No                   | Plain text only — no formatting or escaping  |
| Alerts, errors          | `""`           | ❌ No                   | Emojis OK, no special symbols like `*`, `_`  |
| Reports (e.g. /summary) | `"MarkdownV2"` | ✅ Yes                  | Use `escape_markdown_v2()` for full messages |

---

## 🔧 When to escape

Only apply `escape_markdown_v2(text)` if you're using `parse_mode="MarkdownV2"` **and** you expect formatting like bold, italic, links, etc.

For everything else — especially DRY_RUN — never escape manually.

---

## ✅ Recommended Examples

### DRY_RUN (strategy.py):

```python
msg = f"🧪-DRY-RUN-{symbol}-{direction}-Score-{round(score, 2)}-of-5"
send_telegram_message(msg, force=True, parse_mode="")
```

### Start message (main.py):

```python
message = (
    f"Bot started in {mode} mode\n"
    f"Mode: {mode_text}\n"
    f"DRY_RUN: {str(DRY_RUN)}, VERBOSE: {str(VERBOSE)}"
)
send_telegram_message(message, force=True, parse_mode="")
```

### Shutdown message:

```python
send_telegram_message("🛑 Bot manually stopped via console (Ctrl+C)", force=True, parse_mode="")
```

### Symbol rotation result (pair_selector.py):

```python
msg = f"🔄 Symbol rotation completed:\nTotal: {total}\nFixed: {fixed}, Dynamic: {dynamic}"
send_telegram_message(msg, force=True, parse_mode="")
```

---

## ❌ What NOT to do

### Don't escape when parse_mode is off:

```python
# ❌ Incorrect
send_telegram_message(escape_markdown_v2(msg), parse_mode="")

# ✅ Correct
send_telegram_message(msg, parse_mode="")
```

### Don't mix formatting modes:

```python
# ❌ Incorrect: MarkdownV2 used without escaping
send_telegram_message("*Started* (mode: DRY_RUN)", parse_mode="MarkdownV2")

# ✅ Correct:
send_telegram_message(escape_markdown_v2("*Started* (mode: DRY_RUN)"), parse_mode="MarkdownV2")
```

---

## 🔁 Summary

- DRY_RUN and logs → always plain text (`parse_mode=""`)
- Reports like `/summary`, `/status` → use MarkdownV2 with proper escaping
- Don't use `escape_markdown_v2()` unless you're using Markdown formatting
- No more `\`, no more Telegram 400 errors — clean, readable, and consistent 💯
