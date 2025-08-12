# 📢 Telegram Syntax & Markdown Guide — BinanceBot v1.6.3

Этот справочник описывает, как корректно обрабатывать все сообщения Telegram в системе BinanceBot. Он гарантирует единообразное поведение для DRY_RUN, REAL_RUN, логов, уведомлений и отчетов.

---

## ✅ Правила форматирования сообщений

| Контекст                 | `parse_mode`    | Использовать `escape_markdown_v2()`? | Примечания                                                                                         |
| ------------------------ | --------------- | ------------------------------------ | -------------------------------------------------------------------------------------------------- |
| DRY_RUN, логи, status    | `""` или `None` | ❌ Нет                               | Отправка сообщений как plain text без экранирования                                                |
| Alerts / Errors          | `""`            | ❌ Нет                               | Эмодзи допустимы; избегайте символов `*`, `_`, `[`, `]`, `(`, `)` и т.д.                           |
| Отчёты (/summary)        | `"MarkdownV2"`  | ✅ Да                                | Используйте, если требуется Markdown-разметка; функция send_telegram_message сама экранирует текст |
| Сложные отчёты (/status) | `"HTML"`        | ❌ Нет                               | Используйте HTML-теги для точного контроля форматирования                                          |

_Используйте `escape_markdown_v2(text)` **только** при отправке сообщений с `parse_mode="MarkdownV2"`, если функция send_telegram_message не проводит экранирование автоматически._

---

## ✅ Рекомендуемые примеры использования

### Пример для plain text (DRY_RUN, логи, алерты)

```python
# Пример для /help или DRY_RUN-сообщения:
msg = "🤖 Available Commands:\n\n📖 /help - Show this message\n📊 /summary - Show performance summary"
send_telegram_message(msg, force=True, parse_mode="")

```

# Пример для команды /pause, /resume, /stop и т.п.:

send_telegram_message("Trading paused.", force=True, parse_mode="")

# Получаем отчет в формате, пригодном для MarkdownV2

summary = generate_summary_text() # Функция возвращает текст с нужной разметкой
send_telegram_message(summary, force=True, parse_mode="MarkdownV2")

# Используем HTML для обеспечения корректного форматирования сложных сообщений

msg = (
"<b>Bot Status</b>\n"
f"- Balance: {round(balance, 2)} USDC\n"
f"- Mode: {mode}\n"
f"- API Errors: {trade_stats.get('api_errors', 0)}\n"
f"- Last Signal: {idle}\n"
f"- Status: {paused} {stopping}\n"
f"- Open: {', '.join(open_syms) if open_syms else 'None'}"
)
send_telegram_message(msg, force=True, parse_mode="HTML")

❌ Распространенные ошибки
Неверное экранирование для plain text

# WRONG – лишнее экранирование для plain text-сообщений

send_telegram_message(escape_markdown_v2("Trading paused."), force=True, parse_mode="")

# RIGHT

send_telegram_message("Trading paused.", force=True, parse_mode="")

Двойное экранирование в MarkdownV2

# WRONG – двойное экранирование вызывает ошибки парсинга

send*telegram_message(escape_markdown_v2("\_Started*"), force=True, parse_mode="MarkdownV2")

# RIGHT

send*telegram_message("\_Started*", force=True, parse_mode="MarkdownV2")

📌 Итоговая сводная таблица
Тип сообщения parse_mode Использовать escape_markdown_v2()? Примечание
DRY_RUN / логи "" или None ❌ Нет Plain text – без экранирования
Alerts / Errors "" ❌ Нет Используйте plain text
Отчёты "MarkdownV2" ✅ Да Текст перед отправкой экранируется функцией
HTML-отчёты "HTML" ❌ Нет Используйте HTML для точного контроля форматирования

💡 Дополнительные советы
Избегайте экранирования пробела.
В функции escape_markdown_v2 исключите пробел из списка символов:

# Было:

escape*chars = r"*\*[]()~`>#+-=|{}.! "

# Стало:

escape*chars = r"*\*[]()~`>#+-=|{}.!"

Работа с динамическим содержимым:
Если вам нужно экранировать динамические данные, экранируйте только переменные:

from telegram.telegram_utils import escape_markdown_v2
symbol = escape_markdown_v2("BTC/USDC")
msg = f"Current price for {symbol} is 50000 USDC"
send_telegram_message(msg, force=True, parse_mode="MarkdownV2")

Проверяйте сообщения в DRY_RUN режиме.
Запустите сообщения сначала в DRY_RUN, чтобы убедиться, что форматирование корректно и отсутствуют ошибки вида “Bad Request: can't parse entities…”.
