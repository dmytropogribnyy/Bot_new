Вот финальный ✅ гайд по Telegram-сообщениям в BinanceBot, чтобы ты больше не мучился с \\, ошибками Markdown и непонятным экранированием:

✅ Базовые правила использования send_telegram_message(...)
Ситуация Что использовать Пример
Обычные сообщения (лог, DRY_RUN) parse_mode="" send_telegram_message(msg, parse_mode="")
Ошибки, алерты, статусы parse_mode="" или Markdown (если хочешь формат) send_telegram_message("❌ Error!", parse_mode="")
Форматированные отчёты (summary) parse_mode="MarkdownV2" + escape_markdown_v2(msg) send_telegram_message(escape_markdown_v2(summary), parse_mode="MarkdownV2")
🧼 Примеры — как правильно и как не надо:
❌ Плохо (будет \\, Telegram 400, экранирование неуместно):
python
Copy
Edit
send_telegram_message(escape_markdown_v2(msg), parse_mode="")
✅ Хорошо:
python
Copy
Edit
send_telegram_message(msg, parse_mode="") # plain text
📎 Пример из main.py — запуск:
python
Copy
Edit
message = (
f"Bot started in {mode} mode\n"
f"Mode: {mode_text}\n"
f"DRY_RUN: {str(DRY_RUN)}, VERBOSE: {str(VERBOSE)}"
)
send_telegram_message(message, force=True, parse_mode="")
🧪 Пример из strategy.py — DRY_RUN-сигнал:
python
Copy
Edit
msg = f"🧪 DRY RUN {symbol} → {direction} | Score: {round(score, 2)}/5"
send_telegram_message(msg, force=True, parse_mode="")
📊 Пример для отчёта (MarkdownV2 допустим):
python
Copy
Edit
from telegram.telegram_utils import escape_markdown_v2

msg = escape_markdown_v2(generate_summary_text())
send_telegram_message(msg, parse_mode="MarkdownV2")
✅ Итог:
Тип сообщения parse_mode escape_markdown_v2()?
DRY_RUN, лог, статус "" или None ❌ НЕТ
Отчёты с форматированием "MarkdownV2" ✅ ДА
Алерты / ошибки "" ❌ НЕ нужно
