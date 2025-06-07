## ✅ Финальный статус проекта (v1.6.4-final)

### 🔁 Архитектура отбора и мониторинга пар

-   Формат символов нормализован: `BTC/USDC:USDC`, используется `normalize_symbol()`.
-   `atr_percent = atr / close_price`, `volume_usdc = mean(volume) * price` — стандартизированы.
-   `FILTER_TIERS` реализованы и сравниваются по долям.
-   `score = 0` не фильтруется, влияет только на приоритет.
-   fallback-логика активна (filtered_data / USDC_SYMBOLS / recovery fallback).
-   Автоослабление фильтров при отсутствии пар реализовано.
-   Проверка рыночной волатильности через `get_btc_volatility()`.
-   Telegram-уведомление при 0 отобранных пар добавлено.

### 🔄 Ротация и Live-мониторинг

-   `rotate_symbols()` вызывается через APScheduler каждые 30 мин.
-   `start_symbol_rotation()` работает параллельно.
-   `dynamic_symbols.json` обновляется плавно.
-   Бот не завершает работу при пустом списке.

### 📊 Адаптивные фильтры и оптимизаторы

-   `filter_optimizer.py`, `signal_feedback_loop.py`, `debug_tools.py` активны.
-   Используются `calculate_volatility`, `calculate_atr_volatility` (перенесены в `utils_core.py`).
-   `get_market_volatility_index()` и `get_btc_volatility()` в работе.
-   `runtime_config.json` согласован с логикой, адаптация активна.

### 📁 Автоинициализация данных

-   В `main.py` создаются, если отсутствуют:
    -   `data/missed_opportunities.json`
    -   `data/tp_performance.csv`
-   Исключены ошибки при первом старте.

---

✅ Phase 2.7 — Завершено
Сделано:

Задача Статус Где реализовано
Автоослабление фильтров при 0 пар ✅ pair_selector.py
Telegram alert при отсутствии пар ✅ pair_selector.py
Подключение ATR BTC/USDC ✅ utils_core.py
Автоинициализация файлов ✅ main.py
Фоновая ротация через scheduler ✅ main.py
Fallback recovery (min_pairs, USDC) ✅ pair_selector.py
analyze_signal_blockers() ✅ signal_feedback_loop.py
scheduler: адаптация по blocker'ам ✅ main.py
Telegram-команда /blockers ✅ telegram_commands.py
Лог в parameter_history.json и main.log ✅ signal_feedback_loop.py

🔜 Phase 2.8 — Signal Intelligence & Adaptive Reactions
Текущий статус:

Задача Статус Комментарий
🔄 Re-entry логика 🔸 Частично Повторные сигналы учитываются, входа повторно нет
📈 WebSocket сигналы ⛔ Нет Всё ещё polling
📊 Графики PnL / winrate ⛔ Нет Telegram-графики не реализованы
🧠 Signal Intelligence (auto-ban сигналов) 🔸 Частично Компоненты трекаются, автоисключения нет
📉 Smart fallback → continuous_candidates ⛔ Нет Поддержка USDC_SYMBOLS, но не candidate fallback
🔧 symbol_controller (модуль объединения) ⛔ Нет Всё пока разделено
📉 Автоадаптация min_dynamic_pairs ⛔ Нет min_dyn, max_dyn задаются вручную

🧠 Auto Blocker Analysis (выполнено):
Блок Статус
debug_monitoring_summary.json активен ✅
analyze_signal_blockers() ✅
Runtime адаптация по top_reasons ✅
Запись в parameter_history.json и main.log ✅
Команда /blockers в Telegram ✅
Планировщик (scheduler job) ✅

🟡 Следующие шаги (дополнительно, Phase 2.8+)
Шаг Что делает Статус
/near Показывает пары с score ≈ 2.0–2.4, не открытые 🔜
/audit Автоотчёт: сколько проверено, что мешало 🔜
send_signal_audit_summary() Telegram-раз в 60 мин — отчёт по блокерам 🔜

📁 Ожидаемые файлы:

telegram_commands.py

debug_tools.py

main.py

📌 В TODO / phase_2.8_plan.md добавить:
Приоритет:

/near (отладка сигналов)

send_signal_audit_summary() (периодический отчёт)

После этого:

переход к WebSocket, Re-entry и визуализациям (PNL-графики и др.)

## Added high priority for telegram files:Набор файлов выглядит довольно целостно, всё связанное с Telegram­-логикой в основном разделено по смыслу (общие команды, IP-/роутер-команды, вспомогательные утилиты и т.п.). Ниже кратко, что хорошо и что можно улучшить:

1. registry.py
   Что хорошо: очень лёгкий модуль, просто хранит COMMAND_REGISTRY и не нагружает код.

Что можно улучшить: в текущем виде ок — нет риска круговых импортов, функционал соответствует назначению.

2. telegram_commands.py
   Что хорошо:

Использование декоратора @register_command и @handle_errors даёт понятную структуру: каждая команда оформлена единообразно.

Хорошо вынесены хелпер-функции формата позиций (\_format_pos_real, \_format_pos_dry).

Логика \_initiate_stop и \_monitor_stop_timeout аккуратно разделена для остановки бота.

Наличие ручной обработки legacy-команд в конце (до полной миграции) — разумная временная мера.

Что можно улучшить:

Группировка команд: сейчас часть команд современная (декоратор), часть — в “legacy”-блоке. Для единообразия стоит перенести /open, /summary, /runtime и т.п. тоже через @register_command.

/help: уже хорошо использует COMMAND_REGISTRY, но можно сгруппировать команды (Статистика, Управление, Сигналы и т.д.).

Объём файла: он довольно большой; если станет слишком громоздким, можно вывести IP­-команды или управленческие команды в отдельный модуль (но сейчас это не критично).

3. telegram_handler.py
   Что хорошо:

Реализован лонг-поллинг с сохранением last_update_id, корректная обработка новых апдейтов.

process_telegram_commands вызывает универсальный handler_fn, что упрощает интеграцию.

Проверка chat_id и user_id — базовая безопасность.

Что можно улучшить:

При желании часть логики (проверка “stale” сообщений, фильтр user/chat) можно вынести в хелпер-функции, чтобы упростить чтение.

Если бот разрастётся, может понадобиться асинхронный подход (Aiogram, python-telegram-bot), но для текущих нужд лонг-поллинг норм.

4. telegram_ip_commands.py
   Что хорошо:

Все IP- и router-­команды в одном месте, удобно поддерживать.

Вызов send_telegram_message централизован.

Что можно улучшить:

Можно перенести эти команды под единый декоратор @register_command, но если хочется держать их “легаси” на время — тоже вариант.

Название handle_ip_and_misc_commands уже включает «прочие» команды — если “misc” станет слишком много, лучше разбить.

5. telegram_utils.py
   Что хорошо:

Единая точка для send_telegram_message, send_telegram_file, send_telegram_image, и т.д.

Механизм fallback на plain text, если MarkdownV2 даёт ошибку, очень полезен.

escape_markdown_v2 корректно экранирует спецсимволы.

Что можно улучшить:

Можно удалить/почистить закомментированный старый код отправки сообщений (есть большой блок # def send_telegram_message(...)) — если он не нужен, лучше убрать.

Параметры markdown=False и parse_mode дублируют друг друга — можно оставить что-то одно, чтобы не путать.

Общие рекомендации
Свести все “legacy” команды под @register_command. Так HELP будет показывать все команды, и код станет более единообразным.

Сгруппировать команды в /help:

Управление ботом: /stop, /shutdown, /panic, /restart

Информация/статистика: /status, /summary, /signalstats, /failstats, /open, /near, /blockers_history и т.п.

Настройки/конфиг: /filters, /signalconfig, /runtime и т.д.

Добавить новые команды (как в твоём списке /near, /blockers_history, ...) через @register_command, чтобы была единая система.

Сократить дубли и подчищать комментарии: часть команд типа /signalblocks, /blockers пересекаются по логике анализов — можно объединить или чётко разграничить.

В итоге структура уже вполне логична. Главное — постепенно мигрировать оставшиеся ручные хендлеры в «декораторный» стиль, при этом не ломая текущую логику. Тогда всё будет чётко, единообразно и удобно.

## Plan

Ниже пошаговый план с рефакторингом telegram_commands.py, перенося все «legacy» команды в формат @register_command. В конце — итоговый код файла с комментариями и группировкой в /help.

Шаг 1. Перенести “legacy” команды в декораторы
Пример: перенос /open
Находим в конце telegram_commands.py место, где вызывается handle_open_command(state) при text == "/open".

Копируем логику handle_open_command в новую функцию под декоратором:

python
Copy
@register_command("/open")
@handle_errors
def cmd_open(message, state=None, stop_event=None):
"""
Показать все открытые позиции (DRY или REAL) с расчётом потенциального профита
"""
handle_open_command(state)
Удаляем ветку из раздела elif text == "/open": handle_open_command(state) (т.к. теперь команда обрабатывается декоратором).

Аналогично переносим /summary, /runtime, /mode, /log, /last, /failstats, /heatmap и т.д.

Шаг 2. Улучшить /help с блоками
В коде @register_command("/help") уже есть сбор COMMAND_REGISTRY.items().

Чтобы сделать секции, можно хранить «категорию» команды внутри COMMAND_REGISTRY.
Например, добавить при регистрации:

python
Copy
@register_command("/open", category="activity")
@handle_errors
def cmd_open(...):
...
В /help — сортируем по category и формируем блочное описание.

Пример кода внутри /help:

python
Copy
categories_order = ["Статистика", "Конфигурация", "Активность", "Управление", "Инструменты"]

# Название категории → список команд

grouped = {}

for cmd, entry in COMMAND_REGISTRY.items():
cat = entry.get("category", "Прочее")
grouped.setdefault(cat, []).append((cmd, entry))

# Собираем текст

help*msg = "🤖 \_Available Commands by Category:*\n\n"
for cat in categories*order:
if cat in grouped:
help_msg += f"🔹 *{cat}\_:\n"
for cmd, info in grouped[cat]:
short_desc = info["help"].split("\n")[0].strip()
help_msg += f" {cmd} — {short_desc}\n"
help_msg += "\n"

# Добавим остальные категории, не попавшие в список

for cat, cmds in grouped.items():
if cat not in categories*order:
help_msg += f"🔹 *{cat}\_:\n"
for cmd, info in cmds:
short_desc = info["help"].split("\n")[0].strip()
help_msg += f" {cmd} — {short_desc}\n"
help_msg += "\n"

send_telegram_message(help_msg, parse_mode="MarkdownV2")
Шаг 3. Чистка telegram_utils.py
Удалить закомментированную старую версию send_telegram_message.

Удалить параметр markdown=False (дублируется parse_mode).

Оставить один универсальный механизм отправки с fallback.

Итоговый пример telegram_commands.py (укороченная версия)
Ниже итоговый файл, где:

Все «legacy» команды перенесены в @register_command.

/help распределяет по категориям.

Старые elif text == "/cmd" — убраны.

Сохранена логика \_initiate_stop, \_monitor_stop_timeout и вспомогательных функций.

Обратите внимание: это укороченный пример. В нём я вынес только ключевые команды, а остальное (IP-команды и т.д.) остаётся, как у вас сейчас.

python
Copy

# telegram_commands.py

import json
import os
import threading
import time
from threading import Lock, Thread

import pandas as pd

from common.config_loader import (
DRY_RUN,
EXPORT_PATH,
LEVERAGE_MAP,
RISK_PERCENT,
SL_PERCENT,
TP1_PERCENT,
TP2_PERCENT,
get_adaptive_risk_percent,
get_adaptive_score_threshold,
get_deposit_tier,
get_max_positions,
)
from core.aggressiveness_controller import get_aggressiveness_score
from core.exchange_init import exchange
from core.fail_stats_tracker import reset_failure_count
from core.trade_engine import close_real_trade, trade_manager
from missed_tracker import flush_best_missed_opportunities
from score_heatmap import generate_score_heatmap
from stats import generate_summary
from symbol_activity_tracker import get_most_active_symbols
from telegram.registry import COMMAND_REGISTRY
from telegram.telegram_handler import handle_errors
from telegram.telegram_utils import escape_markdown_v2, register_command, send_telegram_message
from utils_core import get_cached_balance, get_runtime_config, load_state, save_state
from utils_logging import log

command_lock = Lock()

# ------------------------------------------------

# ХЕЛПЕРЫ

# ------------------------------------------------

def \_format_pos_real(p):
...
def \_format_pos_dry(t):
...
def \_monitor_stop_timeout(reason, state, timeout_minutes=30):
...
def \_initiate_stop(reason, stop_event=None):
...

# ------------------------------------------------

# ПРИМЕР: МИГРИРУЕМ /open из "legacy"

# ------------------------------------------------

def handle_open_command(state):
"""
Реальная логика /open, вызывалась раньше вручную.
"""
try:
from core.strategy import calculate_tp_targets
from utils_core import get_cached_balance

        balance = float(get_cached_balance())
        tp1_total, tp2_total = 0.0, 0.0

        if DRY_RUN:
            trades = [t for t in trade_manager._trades.values()
                      if not t.get("tp1_hit") and not t.get("tp2_hit") and not t.get("soft_exit_hit")]
            open_list = []
            for t in trades:
                ...
                # (Логика расчёта profit1/profit2)
                open_list.append(
                    f"{_format_pos_dry(t)}\n→ TP1: +{profit1:.2f} | TP2: +{profit2:.2f} USDC"
                )
            header = "🔍 *Open DRY positions:*"
        else:
            positions = exchange.fetch_positions()
            real_positions = [p for p in positions if float(p.get("contracts", 0)) > 0]
            open_list = []
            for p in real_positions:
                ...
            header = "🔍 *Open positions:*"

        ...
        send_telegram_message(msg, force=True, parse_mode="MarkdownV2")
        log("Sent /open positions with potential PnL.", level="INFO")
    except Exception as e:
        send_telegram_message(f"❌ Failed to fetch open positions: {e}", force=True)
        log(f"Open positions error: {e}", level="ERROR")

@register_command("/open", category="Активность")
@handle_errors
def cmd_open(message, state=None, stop_event=None):
"""Показать все открытые позиции (DRY или REAL) с расчётом потенциального профита"""
handle_open_command(state)

# ------------------------------------------------

# Аналогично переносим /summary, /runtime, /mode...

# ------------------------------------------------

@register_command("/summary", category="Статистика")
@handle_errors
def cmd_summary(message, state=None, stop_event=None):
"""
Сводка: PnL, баланс, активные позиции
"""
try:
summary = generate_summary()
balance = get_cached_balance()
tier = get_deposit_tier()
runtime_config = get_runtime_config()
current_risk = runtime_config.get("risk_percent", get_adaptive_risk_percent(tier))

        if DRY_RUN:
            open_details = [
                ...
            ]
        else:
            ...
        msg = (
            summary
            + f"\n\n*Account Info*:\nBalance: {balance:.2f} USDC\nRisk Tier: {tier}\n"
            f"Active Risk: {current_risk*100:.1f}%\n"
            f"Max Positions: {get_max_positions()}\n"
            f"\n*Open Positions*:\n" + ("\n".join(open_details) if open_details else "None")
        )
        send_telegram_message(msg, force=True, parse_mode="MarkdownV2")
        log("Sent enhanced summary via /summary.", level="INFO")
    except Exception as e:
        send_telegram_message(f"❌ Failed to generate summary: {e}", force=True)
        log(f"Summary error: {e}", level="ERROR")

@register*command("/runtime", category="Конфигурация")
@handle_errors
def cmd_runtime(message, state=None, stop_event=None):
"""Показать текущий runtime_config.json"""
try:
cfg = get_runtime_config()
if not cfg:
send_telegram_message("⚠️ Runtime config is empty or unavailable.", force=True)
return
msg = "⚙️ \_Current Runtime Config:*\n"
for k, v in cfg.items():
msg += f"`{k}`: _{v}_\n"
send_telegram_message(msg, force=True, parse_mode="MarkdownV2")
except Exception as e:
send_telegram_message(f"❌ Error fetching runtime config: {e}", force=True)

@register*command("/mode", category="Конфигурация")
@handle_errors
def cmd_mode(message, state=None, stop_event=None):
"""Показать текущий «strategy bias» и score"""
try:
score = round(get_aggressiveness_score(), 2)
bias = "🔥 HIGH" if score >= 3.5 else "⚡ MODERATE" if score >= 2.5 else "🧊 LOW"
msg = f"🎯 \_Strategy Bias*: {bias}\n📈 _Score_: `{score}`"
send_telegram_message(msg, force=True, parse_mode="MarkdownV2")
log("Sent mode info.", level="INFO")
except Exception as e:
send_telegram_message(f"❌ Failed to fetch mode: {e}", force=True)
log(f"Mode error: {e}", level="ERROR")

@register_command("/log", category="Инструменты")
@handle_errors
def cmd_log(message, state=None, stop_event=None):
"""Отправить daily report (лог за сегодня)"""
from stats import send_daily_report
try:
send_daily_report(parse_mode="")
log("Sent daily report via /log command.", level="INFO")
except Exception as e:
send_telegram_message(f"❌ Failed to send daily report: {e}", force=True)
log(f"/log error: {e}", level="ERROR")

@register_command("/last", category="Статистика")
@handle_errors
def cmd_last(message, state=None, stop_event=None):
"""Показать последнюю сделку"""
try:
df = pd.read_csv(EXPORT_PATH)
if df.empty:
send_telegram_message("No trades logged yet.", force=True)
return
last = df.iloc[-1]
commission_info = ""
if "Commission" in last:
commission_info = f"\nCommission: {round(last['Commission'], 5)} USDC"
msg = (
f"{'[DRY_RUN]\n' if DRY_RUN else ''}Last Trade:\n"
f"{last['Symbol']} - {last['Side']}@{round(last['Entry Price'],4)} -> {round(last['Exit Price'],4)}\n"
f"PnL: {round(last['PnL (%)'],2)}% ({last['Result']}){commission_info}"
)
send_telegram_message(msg, force=True)
log("Sent last trade info.", level="INFO")
except Exception as e:
send_telegram_message(f"❌ Failed to read last trade: {e}", force=True)
log(f"Last trade error: {e}", level="ERROR")

@register*command("/failstats", category="Статистика")
@handle_errors
def cmd_failstats(message, state=None, stop_event=None):
"""Показать статистику отказов (причины и счётчики)"""
from core.fail_stats_tracker import get_signal_failure_stats
try:
failure_stats = get_signal_failure_stats()
if not failure_stats:
send_telegram_message("No failure statistics available. ✅")
return
msg = "📊 \_Signal Failure Statistics:*\n\n"
sorted_symbols = sorted(
failure_stats.items(),
key=lambda x: sum(x[1].values()),
reverse=True
)
for symbol, reasons in sorted_symbols[:10]:
total_failures = sum(reasons.values())
msg += f"• {symbol}: {total_failures} failures\n"
sorted_reasons = sorted(reasons.items(), key=lambda x: x[1], reverse=True)
for reason, count in sorted_reasons[:3]:
msg += f" - {reason}: {count}\n"
msg += "\n"
send_telegram_message(msg, force=True, parse_mode="MarkdownV2")
except Exception as e:
send_telegram_message(f"❌ Error fetching failstats: {e}", force=True)

@register_command("/heatmap", category="Инструменты")
@handle_errors
def cmd_heatmap(message, state=None, stop_event=None):
"""Сгенерировать и отправить heatmap по score (7дн)"""
if DRY_RUN:
send_telegram_message("Heatmap unavailable in DRY_RUN mode.", force=True)
return
try:
generate_score_heatmap(days=7)
log("Generated heatmap.", level="INFO") # При желании можно отправить картинку, если она сохраняется # send_telegram_image("data/score_heatmap.png", "Score Heatmap (7 days)")
except Exception as e:
send_telegram_message(f"❌ Failed to generate heatmap: {e}", force=True)
log(f"Heatmap error: {e}", level="ERROR")

# ------------------------------------------------

# /help — группируем по категориям

# ------------------------------------------------

@register_command("/help", category="Справка")
@handle_errors
def cmd_help(message, state=None, stop_event=None):
"""Показать список команд по категориям. /help [cmd] для детальной инфы"""
command_parts = message.get("text", "").strip().split()
if len(command_parts) > 1: # /help <команда>
specific_cmd = f"/{command_parts[1].lower().lstrip('/')}"
cmd_entry = COMMAND_REGISTRY.get(specific_cmd)
if cmd_entry:
help_text = cmd_entry["help"] or "No description available."
send_telegram_message(f"Help for {specific_cmd}:\n\n{help_text}", force=True)
return
else:
send_telegram_message(f"Command {specific_cmd} not found. Try /help for a list of commands.", force=True)
return

    # Собираем команды по категориям
    categories_order = ["Статистика", "Конфигурация", "Активность", "Управление", "Инструменты", "Справка"]
    grouped = {}
    for cmd, entry in COMMAND_REGISTRY.items():
        cat = entry.get("category", "Прочее")
        grouped.setdefault(cat, []).append((cmd, entry))

    help_msg = "🤖 *Available Commands by Category:*\n\n"
    for cat in categories_order:
        if cat in grouped:
            help_msg += f"🔹 *{cat}*:\n"
            for cmd, info in grouped[cat]:
                short_desc = info["help"].split("\n")[0].strip()
                help_msg += f"   {cmd} — {short_desc}\n"
            help_msg += "\n"

    # Остальные (не попавшие в categories_order)
    for cat, commands_list in grouped.items():
        if cat not in categories_order:
            help_msg += f"🔹 *{cat}*:\n"
            for cmd, info in commands_list:
                short_desc = info["help"].split("\n")[0].strip()
                help_msg += f"   {cmd} — {short_desc}\n"
            help_msg += "\n"

    send_telegram_message(help_msg, force=True, parse_mode="MarkdownV2")
    log("[Telegram] Help information sent", level="INFO")

# ------------------------------------------------

# handle_telegram_command

# ------------------------------------------------

def handle_telegram_command(message, state, stop_event=None):
"""
Главный обработчик Telegram-команд с использованием REGISTER.
"""
from telegram.telegram_ip_commands import handle_ip_and_misc_commands

    # Проверяем, не legacy ли IP-команда:
    text = message.get("text", "").strip().lower()
    if text in ["/router_reboot", "/cancel_reboot", "/ipstatus", "/forceipcheck", "/pairstoday", "/debuglog", "/signalblocks", "/reasons", "/runtime"]:
        handle_ip_and_misc_commands(text, _initiate_stop)
        return

    # Далее — проверка registry
    base_command = text.split()[0]
    cmd_entry = COMMAND_REGISTRY.get(base_command)
    if cmd_entry:
        try:
            cmd_entry["handler"](message, state, stop_event)
        except Exception as e:
            log(f"[Telegram] Error executing {base_command}: {e}", level="ERROR")
            send_telegram_message(f"❌ Error executing {base_command}: {e}", force=True)
    else:
        send_telegram_message("Command not recognized. Try /help for a list of commands.", force=True)

Примечания к коду
Многие хендлеры (типо handle_open_command, handle_runtime_command) можно оставить как приватные функции, а декоратор-функции лишь вызывают их, передавая message/state.

Для /help добавили поле category="..." при регистрации команды, чтобы группировать в выводе help.

Старые elif text == "/open": handle_open_command(state) (и т.п.) — удалены, чтобы не дублировать логику.

При желании можно часть этого файла разбить на более мелкие модули (commands_admin.py, commands_status.py, etc.).

Вывод
Так мы не ломаем текущую структуру, а улучшаем:

Все команды теперь оформлены единообразно через @register_command.

/help показывает команды по категориям, автоматически.

telegram_utils.py чистим от дублей.

После этого рефакторинга у вас будет корректная, консистентная система команд, готовая к дальнейшему расширению.

## summary

## ✅ BinanceBot v1.7 — Финальный план рефакторинга и прозрачности

### 🎯 Цель

Полный отказ от `score`, `HTF_CONFIDENCE`, `relax_factor` и старых адаптаций. Внедрение простой логики сигналов “1 основной + 1 дополнительный”. Поддержка смешанного списка пар: fixed + dynamic. Прозрачная фильтрация по `ATR`, `Volume`, `RSI`. Аналитика и отчёты в Telegram.

---

### 📦 Что уже реализовано

| Компонент                                | Статус | Описание                                                     |
| ---------------------------------------- | ------ | ------------------------------------------------------------ |
| `strategy.py`                            | ✅     | Вход по `passes_1plus1`, без score                           |
| `signal_utils.py`                        | ✅     | `get_signal_breakdown()`, `passes_1plus1()` и др.            |
| `trade_engine.py`                        | ✅     | qty, TP/SL без расчёта score; можно варьировать по типу пары |
| `pair_selector.py`                       | ✅     | Фильтрация по ATR/Volume, сохраняется `type: fixed/dynamic`  |
| `continuous_scanner.py`                  | ✅     | Логирует inactive-пары с `type="inactive"` и атрибутами      |
| `signal_feedback_loop.py`                | ✅     | TP2 winrate → risk, max_positions; runtime адаптация         |
| `runtime_config.json`                    | ✅     | Минималистичный, без устаревших полей                        |
| `entry_logger.py / component_tracker.py` | ✅     | Логируются `breakdown`, `type`, `is_successful`              |
| `main.py`                                | ✅     | Полностью очищен от score и HTF, запуск через clean loop     |

---

### 🔁 Структура и логика пар

-   `SYMBOLS_FILE`: список словарей `[{symbol, type, atr, volume_usdc, risk_factor}]`
-   `fixed_pairs`: стабильные монеты (BTC, ETH, BNB, ADA и т.д.)
-   `dynamic_pairs`: отбор по фильтрам (ATR, Volume)
-   Telegram-уведомления указывают количество fixed / dynamic

---

### 📉 Фильтрация и сигналка

-   Основной вход: `passes_1plus1(breakdown) == True`
-   Фильтры: `rsi_15m`, `rel_volume_15m`, `atr_15m`
-   `entry_log.csv`, `debug_monitoring_summary.json` логируют `type`, `reason`, `breakdown`
-   Компоненты логируются через `component_tracker.py`

---

### 💬 Telegram-команды

| Компонента                                   | Статус                                          |
| -------------------------------------------- | ----------------------------------------------- |
| Система декораторов `@register_command`      | ✅ Завершено                                    |
| `/help` с категориями                        | ✅ Завершено                                    |
| `/signalstats` (анализ по компонентам)       | ✅ Переписан через `component_tracker_log.json` |
| `/filters`, `/blockers`, `/runtime`, `/risk` | ✅ Готово                                       |
| `/scoreboard`, `/heatmap`                    | 🔥 Удалить (устарели)                           |
| `/rejections`, `/topmissed`, `/near`         | 🟡 Опциональные улучшения                       |

#### Следующий шаг по Telegram:

-   Удалить устаревшие команды (`/scoreboard`, `/heatmap`)
-   Добавить / адаптировать `/rejections`, `/signalstats`
-   Документировать все команды через `docstring`

---

### 🛠 Что ещё осталось сделать

| Задача / Файл                   | Статус | Что сделать                                                                                   |
| ------------------------------- | ------ | --------------------------------------------------------------------------------------------- |
| `strategy.py`                   | 🟡     | `symbol_type_map`, логировать `type`, вставить в `log_entry()`                                |
| `entry_logger.py`               | 🟡     | Принимать и логировать `type` в CSV                                                           |
| `trade_engine.py`               | 🟡     | (опц.) варьировать `cooldown`, SL/TP по `pair_type`                                           |
| `telegram_commands.py`          | 🔄     | Удалить `/scoreboard`, адаптировать `/signalstats`, добавить `/rejections`                    |
| `debug_monitoring_summary.json` | 🔄     | Удалить `score`, `HTF_STATE`, `near_signals`. Оставить `breakdown`, `reason`, `passes_1plus1` |

---

### 📌 Почему это важно

-   Прозрачность: видно, какие пары активны и почему выбраны
-   Аналитика: легче строить winrate по типам (fixed vs dynamic)
-   Надёжность: отказ от сложной адаптации, стабильные фильтры
-   Гибкость: можно расширять, варьировать TP/SL, cooldown

---

### ✅ Подтверждение по каждому шагу

1. ✅ `pair_selector.py`: сохраняет пары с type и метаинфой
2. 🟡 `strategy.py`: логирует type пары, вставляет в entry log, может передавать в trade_engine
3. 🟡 `entry_logger.py`: добавляет поле `type` в CSV
4. 🟡 `trade_engine.py`: можно варьировать поведение по `pair_type`
5. 🔄 `telegram_commands.py`: /rejections, /failstats, /signalstats → обновить под новую модель
6. 🔄 `debug_monitoring_summary`: адаптировать под breakdown-модель

---

### 📈 Состояние проекта: **~90% завершено**

✅ Стратегия, фильтры, входы, сигналы — завершены
🟡 Осталось логирование type, Telegram-команды и monitoring JSON

---

## monitor results during run

Да, файл debug_monitoring_summary.json содержит очень полезную информацию, особенно для ручной диагностики и настройки фильтров. Вот ключевые выводы и идеи, которые можно из него извлечь:

✅ Общая картина:
📊 Всего проверено: 32 символа

🟢 Прошли фильтры (filtered: false): 12 пар

🔴 Заблокированы фильтрами (filtered: true): 20 пар

🔍 Основные причины фильтрации:
low_atr: слишком низкая волатильность

low_volume: слишком маленький объём (в USDC)

📈 Диагностика фильтров:
Причина Сколько символов отфильтровано
low_atr ~18 символов
low_volume ~10 символов

🔧 Это означает, что фильтр ATR — наиболее жёсткий. Возможно, его стоит немного ослабить, например:

json
Copy
Edit
"atr_threshold_percent": 0.001 → 0.0009
💡 Примеры, которые на грани:
ETH/USDC:USDC: atr_pct = 0.00285 — почти проходит (если у тебя стоит 0.0030)

FIL/USDC:USDC: volume = 6928 — норм, но atr_pct = 0.0025, и этого не хватает

LINK/USDC:USDC: volume нормальный (3642.9), но atr_pct = 0.00268 — чуть не проходит

⚙️ Возможно, стоит:

слегка ослабить ATR-требования,

либо включить расслабляющие этапы более активно, если они пока не используются (в logs они были пустыми).

📌 Полезные пары с высокой волатильностью:
Ты можешь явно выделить те, кто уже хорош по atr_pct и volume:

ETHFI: atr_pct = 0.00774, volume = 13,729

WIF: atr_pct = 0.00611, volume = 114k

KAITO: atr_pct = 0.00621, volume = 5.3k

BOME, ARB, CRV, NEAR, 1000PEPE, SUI — все хорошие кандидаты

🧠 Что можно сделать:

1. Снизить ATR-порог до 0.0025 или 0.0020
   Чтобы не блокировать ETH, FIL, XRP, LINK, AVAX, NEO, которые сейчас на грани.

2. Добавить лог tier_stage в debug-результаты
   Чтобы видеть, на каком этапе релаксации пара прошла (Standard, Moderate, и т.п.).

3. Логировать общее кол-во отфильтрованных и причины в Telegram
   Пример:

yaml
Copy
Edit
Filtered: 20/32
Most common reason: low_atr
✅ Вывод:
Файл отлично работает. Сейчас у тебя строгий ATR-фильтр, из-за чего многие сильные пары (ETH, LINK и др.) едва не проходят. Чуть снизив atr_threshold_percent, ты можешь увеличить число допустимых пар и улучшить охват рынка.

✅ Да, выводы от Pro полностью подтверждаются и логически обоснованы.
Они чётко описывают весь pipeline принятия решения о входе и точки, где может “гаснуть” сигнал. Подчеркну ключевые моменты, которые совпадают с твоим реальным кейсом:

🔎 1. debug_monitor ≠ гарантия входа
Даже если "filtered": false, это ещё не значит, что бот попытается войти в сделку.

Следующий обязательный шаг — прохождение сигнальной логики, то есть should_enter_trade(...).

✅ Подтверждается: ты видишь пары, прошедшие фильтры, но 0 входов — причина не в debug_monitor.

🧠 2. Критичность passes_1plus1()
Основной барьер: passes_1plus1(breakdown) → False

Это чаще всего причина блокировки, даже при хорошем ATR/Volume.

✅ Подтверждается: у тебя нет логов про signals breakdown — и мы не видим попыток входа даже на “хороших” парах (ETHFI, BOME, WIF).

🪵 3. Не хватает логов в should_enter_trade()
Pro правильно советует:

python
Copy
Edit
log(f"[1+1] {symbol} => breakdown={breakdown}, result={passes_1plus1(breakdown)}", level="DEBUG")
log(f"[Reject] {symbol} => {failure_reasons}", level="DEBUG")
✅ Это даст прозрачность: ты сразу поймёшь, где и почему бот отказал.

💬 4. Отсутствие сообщений “🚀 OPEN…” = 100% признак, что входа не было
Это Telegram-уведомление говорит, что вход состоялся.

Если ни одного такого не было — сигналы блокируются ДО фазы trade_manager.open_trade(...).

✅ Подтверждается на 100% — и ты уже это видел в логах.

📁 5. entry_log.csv = честный трекер
Если он пустой, или все записи — FAIL/NO_TRADE, а не SUCCESS → сигналов реально не было.

✅ Абсолютно верно, и это прямой индикатор результата.

🧪 6. Ослабление фильтров = вариант
Если debug_monitor показывает, что даже ETH, XRP, LINK не проходят по atr_pct, то имеет смысл ослабить:

json
Copy
Edit
"atr_threshold_percent": 0.001 → 0.0008
"volume_threshold_usdc": 1000 → 500
✅ Подтверждается: ты явно упёрся в слишком строгие фильтры.

🟢 Вывод:
Все рекомендации Pro логичны, практичны и прямо применимы к твоей текущей ситуации.
Если хочешь — могу помочь вставить логи и быстро зафиксировать, где именно и почему сигналы отваливаются (до входа).

## ✅ Current TODO (обновлённый)

✅ Current TODO (обновлено на 100%)
✅ Основная логика:
✔️ Вся цепочка main → should_enter_trade → enter_trade → trade_manager завершена

✔️ Входы, qty, ATR, SL, TP1 работают стабильно

✔️ TP2 убран, trailing активируется после TP1

✔️ Telegram-уведомления при входе, TP1, SL приходят

✔️ DRY_RUN и REAL_RUN полностью отлажены

✅ CSV и мониторинг:
✔️ record_trade_result(...) и log_trade_result(...) переписаны:

пишется type, atr, commission, net_pnl, exit_reason

нет дубликатов

✔️ tp_performance.csv расширен и используется как источник для:

/last

/dailycsv (если добавишь)

send_daily_summary()

✅ main.py обновлён:
✔️ Добавлен cron:

python
Copy
Edit
scheduler.add_job(send_daily_summary, 'cron', hour=23, minute=59)
✔️ Удалены дублирующие заголовки HTF, ADX, BB Width в CSV

✔️ Грамотно подключён Telegram, IP, мониторинг, decay

🟢 Осталось по желанию:
Задача Статус Комментарий
/positions (упрощённый /open) 🔄 Показывает текущие позиции без расчётов
/dailycsv — файл в TG 🔄 Отправляет tp_performance.csv
/pnl_today — краткий итог дня 🔄 Использует get_daily_stats()
risk_adjuster.py 🕐 Auto-risk на основе winrate / equity
debug_monitoring_summary.json 🕐 Можно убрать score, HTF и оставить только breakdown
entry_logger.py ✅ Уже логирует type, priority_pair, expected_profit
strategy.py ✅ Использует breakdown, log_entry() реализован

📊 Итоговый статус проекта:
Компонент Статус
Торговая логика ✅ завершена
TP/SL/Trailing ✅ завершены
Telegram ✅ стабильно
CSV / логирование ✅ финализировано
Monitoring ✅ работает
Daily summary ✅ cron активен
Расширенные команды 🟡 по желанию
Auto-risk 🕐 в планах
WebSocket ❌ ещё polling
Smart-fallback ❌ не реализовано

---

✅ Что реализовано по TP / SL / trailing / soft exit:
Компонент Статус Где реализовано
TP1 / TP2 ✅ calculate_tp_levels, enter_trade, monitor_active_position
SL (ATR-based) ✅ should_enter_trade и enter_trade используют ATR для расчёта SL

Trailing stop ✅ run_adaptive_trailing_stop(...), активируется после TP1 (если включён)
Soft exit ✅ run_soft_exit(...), активируется после TP1, снижает часть позиции
Auto-profit exit ✅ run_auto_profit_exit(...) — закрывает сделку при +X% даже до TP1
Micro-profit exit ✅ run_micro_profit_optimizer(...) — используется для небольших позиций
Monitoring TP1/TP2/SL ✅ В monitor_active_position(...) с Telegram уведомлениями

☑️ Все флаги (tp1_hit, sl_hit, soft_exit_hit, tp2_hit) логируются и используются в логике.

📊 Вывод по приоритету из оставшихся задач:
🔝 1 место: risk_adjuster.py (Auto-Risk)
Почему:

У тебя уже есть:

get_adaptive_risk_percent(...) используется в strategy.py, trade_engine.py

trade_stats в config_loader.py (win/loss streak, total pnl) — готово для оценки динамики

Осталось только: автоматически обновлять risk_percent в runtime_config в зависимости от winrate / streak.

🟢 Это даст адаптацию риска: на серии лоссов — снижать до 0.5%, при серии побед — повышать к 1.5–2%.

✅ Подтверждение: ты уже всё реализовал по TP/SL/exit, и лучше, чем в большинстве стратегий.
📌 Хочешь — могу:

Сгенерировать risk_adjuster.py (весь файл)

Добавить cron-задачу для него (run every hour) в main.py

Подключить auto-update поля risk_multiplier в runtime

---

## 🔐 Финальная проверка:

Компонент Статус Комментарий
TP/SL, trailing, soft_exit ✅ Готово Все методы отлажены и логируются
Логика 1+1 сигналов ✅ Реализована Через passes_1plus1 и breakdown
risk_adjuster.py (auto-risk) ✅ Активен Запускается по scheduler каждый час
Telegram команды ✅ Работают /open, /status, /summary, /pairstoday и т.д.
DRY_RUN → REAL_RUN ✅ Проверено DRY отключён, Telegram работает, API ключи готовы
Логирование в CSV ✅ Завершено tp_performance.csv содержит ATR, Type, Exit Reason, Commission, Net PnL
Monitoring и decay ✅ Работает schedule_failure_decay, track_missed_opportunities, фильтры ослабляются
main.py финализирован ✅ Все потоки, scheduler, cron-задачи подключены
Риск-защита / ограничение Notional ✅ Проверяется при входе

🟢 Что ты имеешь:
Полностью адаптивный, безопасный и прозрачный скальпер

Telegram-интерфейс с расширенными командами

Runtime-адаптация риска на базе winrate и streak

Готовность к визуализации, WebSocket, и Phase 2.8

📌 Можешь запускать main.py с настоящими API-ключами и наблюдать:

Telegram-уведомления по сделкам

tp_performance.csv обновляется

/summary, /runtime, /log дают актуальные данные
