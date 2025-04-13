# 📢 Telegram Syntax & Markdown Guide — BinanceBot v1.6.3

This unified guide shows how to correctly handle all Telegram messages in the BinanceBot system. It ensures consistent behavior across DRY_RUN, REAL_RUN, logs, alerts, and reports.

---

## ✅ Message Formatting Rules

| Context               | `parse_mode`   | `escape_markdown_v2()`? | Notes                                 |
| --------------------- | -------------- | ----------------------- | ------------------------------------- |
| DRY_RUN, logs, status | `""` or `None` | ❌ No                   | Plain text only — no escaping         |
| Alerts, errors        | `""`           | ❌ No                   | Emojis OK, avoid `*`, `_`, `[`        |
| Reports (/summary)    | `"MarkdownV2"` | ✅ Yes                  | Must escape Markdown symbols manually |

Use `escape_markdown_v2(text)` **only** when using `parse_mode="MarkdownV2"` and formatting.

---

## ✅ Recommended Usage Examples

### 🧪 DRY_RUN (strategy.py)

```python
msg = f"🧪-DRY-RUN-{symbol}-{direction}-Score-{round(score, 2)}-of-5"
send_telegram_message(msg, force=True, parse_mode="")
```

### 📦 Start Message (main.py)

```python
message = (
    f"Bot started in {mode} mode\n"
    f"Mode: {mode_text}\n"
    f"DRY_RUN: {str(DRY_RUN)}, VERBOSE: {str(VERBOSE)}"
)
send_telegram_message(message, force=True, parse_mode="")
```

### 🛑 Shutdown Notification

```python
send_telegram_message("🛑 Bot manually stopped via console (Ctrl+C)", force=True, parse_mode="")
```

### 🔄 Symbol Rotation

```python
msg = f"🔄 Symbol rotation completed:\nTotal: {total}\nFixed: {fixed}, Dynamic: {dynamic}"
send_telegram_message(msg, force=True, parse_mode="")
```

### 📊 Formatted Report (MarkdownV2)

```python
from telegram.telegram_utils import escape_markdown_v2

summary = generate_summary_text()
msg = escape_markdown_v2(summary)
send_telegram_message(msg, parse_mode="MarkdownV2")
```

---

## ❌ Common Mistakes to Avoid

### ❌ Escaping when not using MarkdownV2:

```python
# WRONG
send_telegram_message(escape_markdown_v2(msg), parse_mode="")

# RIGHT
send_telegram_message(msg, parse_mode="")
```

### ❌ Unescaped MarkdownV2:

```python
# WRONG
send_telegram_message("*Started*", parse_mode="MarkdownV2")

# RIGHT
send_telegram_message(escape_markdown_v2("*Started*"), parse_mode="MarkdownV2")
```

---

## 📌 Summary Table

| Type              | `parse_mode`   | `escape_markdown_v2()`? |
| ----------------- | -------------- | ----------------------- |
| DRY_RUN / logs    | `""` or `None` | ❌ No                   |
| Alerts / Errors   | `""`           | ❌ No                   |
| Formatted Reports | `"MarkdownV2"` | ✅ Yes                  |

---

## 💡 Tips

- Avoid special characters `* _ [ ] ( ) ~` unless escaped in MarkdownV2.
- Telegram has a 4096-char limit — truncate if needed.
- Test your messages in DRY_RUN first if unsure.

---

🔍 Telegram Utility Functions Reference

1. escape*markdown_v2(text: str) -> str
   Purpose:
   Эта функция экранирует специальные символы для безопасного использования с Telegram MarkdownV2 (например, символы \*, *, [, ], (, ), ~ и т.д.).

Usage:

Используйте эту функцию только при отправке сообщений с parse_mode="MarkdownV2".

Для plain text сообщений (например, в DRY_RUN, логах, командах как /help) функция не применяется, чтобы избежать двойного экранирования.
from telegram.telegram_utils import escape_markdown_v2

formatted*text = escape_markdown_v2("\_Important* message: Please check the log.")
send_telegram_message(formatted_text, force=True, parse_mode="MarkdownV2")

2. send_telegram_message(text: str, force=False, parse_mode="MarkdownV2") -> None
   Purpose:
   Отправляет сообщение в Telegram с учетом выбранного режима форматирования.

Если установлен parse_mode="MarkdownV2", сообщение автоматически передается через функцию escape_markdown_v2(text) для экранирования специальных символов.

Если используется parse_mode="" (или None), сообщение отправляется как plain text без изменений.

Usage:

Для сообщений, где важна разметка (отчеты, статусные сообщения с форматированием) – используйте parse_mode="MarkdownV2" и предварительно экранируйте текст с помощью escape_markdown_v2().

Для команд типа /help, логов, DRY_RUN-сообщений и алертов – указывайте parse_mode="", чтобы избежать ошибок форматирования.

Examples:

Plain Text (без Markdown):

# Сообщение для /help, отправляется как обычный текст без форматирования.

send_telegram_message("🤖 Available Commands:\n\n📖 /help - Show this message\n📊 /summary - Show performance summary", force=True, parse_mode="")

С Markdown форматированием:

from telegram.telegram_utils import escape_markdown_v2

message = "🤖 _Available Commands:_\n\n📖 /help - Show this message\n📊 /summary - Show performance summary"
formatted_message = escape_markdown_v2(message)
send_telegram_message(formatted_message, force=True, parse_mode="MarkdownV2")

Общие рекомендации:
Не использовать escape_markdown_v2() при отправке plain text сообщений (например, команды /help в режиме DRY_RUN), чтобы избежать двойного экранирования.

Проверяйте конечное отображение сообщений в Telegram и логи консоли, чтобы убедиться, что форматирование соответствует ожиданиям.

Используйте данный справочник для единообразия при работе с Telegram сообщениями в вашем проекте.

> This guide ensures clean, safe, and professional message output for all BinanceBot environments (v1.6.3).
