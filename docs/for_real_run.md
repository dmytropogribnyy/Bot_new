Финальный документ по подготовке к тестовому запуску бота и переходу к полной автоматизации

1. Обзор
   Цель — провести первый тестовый запуск в реальном режиме (DRY_RUN = False) в течение 15 минут с депозитом 44 USD с минимальным риском, используя фиксированные параметры, а затем перейти к полной автоматизации управления рисками. На данном этапе важно:

Минимизировать риск на тесте: фиксировать RISK_PERCENT = 0.01 (1% риска, что соответствует 0,44 USD при депозите 44 USD) и MAX_POSITIONS = 1.

Установить DRY_RUN = False и VERBOSE = True для реального режима и подробного логирования.

После успешного теста заменить фиксированные значения на динамический расчёт через функции get_adaptive_risk_percent(balance) и get_max_positions(balance).

Устранить предупреждения линтера (ruff) в utils_core.py, связанные с неиспользуемыми импортами.

2. Изменения в config.py
   Внесите следующие изменения в конфигурационный файл для теста:

python
Copy

# config.py

# ... (предыдущий код)

# --- Risk Management ---

AGGRESSIVENESS_THRESHOLD = 0.6
AGGRESSIVE_THRESHOLD = 50
SAFE_THRESHOLD = 10
MIN_NOTIONAL = 5
MAX_HOLD_MINUTES = 90
RISK_DRAWDOWN_THRESHOLD = 5.0

# Фиксированные параметры для тестового запуска (15 минут, депозит 44 USD)

RISK_PERCENT = 0.01 # 1% риска на сделку (для теста)
MAX_POSITIONS = 1 # Максимум 1 сделка

# Функции для полной автоматизации (будут использоваться после теста)

def get_adaptive_risk_percent(balance):
"""Расчет адаптивного процента риска на основе баланса."""
if balance < 100:
return 0.01 # 1% для баланса < 100
elif balance < 300:
return 0.02 # 2% для баланса 100-300
elif balance < 1000:
return 0.03 # 3% для баланса 300-1000
else:
return 0.05 # 5% для баланса > 1000

def get_max_positions(balance):
"""Расчет максимального числа сделок на основе баланса."""
if balance < 100:
return 1 # 1 сделка для баланса < 100
elif balance < 300:
return 2 # 2 сделки для баланса 100-300
elif balance < 1000:
return 3 # 3 сделки для баланса 300-1000
else:
return 5 # 5 сделок для баланса > 1000

# --- Mode & Debug ---

DRY_RUN = False # Запуск в реальном режиме
VERBOSE = True # Подробное логирование
USE_DYNAMIC_IN_DRY_RUN = True
ADAPTIVE_SCORE_ENABLED = True

# ... (остальной код)

3. Изменения в utils_core.py
   Чтобы устранить предупреждения линтера и правильно использовать динамический расчет риска, выполните следующие действия:

Удалите старую версию функции get_adaptive_risk_percent из utils_core.py, которая использовала жёстко закодированные значения.

Отсортируйте импорты по алфавиту и удалите неиспользуемый импорт RISK_PERCENT. Используйте импортированную версию функции из config.py.

Обновленный блок импортов и функция set_leverage_for_symbols будут выглядеть так:

python
Copy

# utils_core.py

import json
import os
import time
from datetime import datetime
from threading import Lock

from config import exchange, get_adaptive_risk_percent, LEVERAGE_MAP, SYMBOLS_ACTIVE
from utils_logging import log

# Остальной код файла (например, работа с кешем, загрузка/сохранение состояния и т.д.)

def set_leverage_for_symbols():
for symbol in SYMBOLS_ACTIVE:
leverage = LEVERAGE_MAP.get(symbol, 5)
safe_call_retry(
exchange.set_leverage,
leverage,
symbol,
tries=3,
delay=1,
label=f"set_leverage {symbol}",
)
log("Leverage set for all symbols", level="INFO")
После этих правок линтер не будет выдавать предупреждения о неиспользуемых импортах.

4. Изменения в symbol_processor.py
   В файле symbol_processor.py необходимо использовать зафиксированное значение MAX_POSITIONS (для теста) из config.py, а также оставить использование функции get_adaptive_risk_percent(balance) для расчёта риска:

python
Copy

# symbol_processor.py

from config import DRY_RUN, MIN_NOTIONAL, SL_PERCENT, MAX_POSITIONS
from core.order_utils import calculate_order_quantity
from core.strategy import fetch_data, should_enter_trade
from core.trade_engine import (
dry_run_positions_count,
get_position_size,
open_positions_count,
open_positions_lock,
)
from utils_core import get_adaptive_risk_percent, get_cached_balance
from utils_logging import log

def process_symbol(symbol, balance, last_trade_times, lock):
try:
with open_positions_lock:
active_count = dry_run_positions_count if DRY_RUN else open_positions_count
if active_count >= MAX_POSITIONS:
log(
f"⏩ Skipping {symbol} — max open positions ({MAX_POSITIONS}) reached",
level="DEBUG",
)
return None

        if get_position_size(symbol) > 0:
            log(f"⏩ Skipping {symbol} — already in position", level="DEBUG")
            return None

        df = fetch_data(symbol)
        if df is None:
            log(f"⚠️ Skipping {symbol} — fetch_data returned None", level="WARNING")
            return None

        result = should_enter_trade(symbol, df, None, last_trade_times, lock)
        if result is None:
            log(f"❌ No signal for {symbol}", level="DEBUG")
            return None

        direction, score, is_reentry = result
        entry = df["close"].iloc[-1]
        stop = entry * (1 - SL_PERCENT) if direction == "buy" else entry * (1 + SL_PERCENT)
        # Используем функцию get_adaptive_risk_percent для расчета риска
        risk_percent = get_adaptive_risk_percent(balance)
        qty = calculate_order_quantity(entry, stop, balance, risk_percent)

        if qty * entry < MIN_NOTIONAL:
            log(f"⚠️ Notional too low for {symbol} — skipping", level="WARNING")
            return None

        log(
            f"{symbol} 🔍 Calculated qty: {qty:.3f}, entry: {entry:.2f}, notional: {qty * entry:.2f}",
            level="DEBUG",
        )

        return {
            "symbol": symbol,
            "direction": direction,
            "qty": qty,
            "entry": entry,
            "score": score,
            "is_reentry": is_reentry,
        }
    except Exception as e:
        log(f"🔥 Error in process_symbol for {symbol}: {e}", level="ERROR")
        return None

5. Резервное копирование и тестирование
   Перед тестированием:

Сохраните текущую версию кода и сделайте резервное копирование файла data/tp_performance.csv, чтобы можно было вернуться к стабильной версии в случае проблем.

Измените SYMBOLS_ACTIVE в config.py, оставив стабильные пары (например, BTC/USDC, ETH/USDC) для теста.

Запустите бота в реальном режиме (DRY_RUN = False) на 15 минут:

Следите за логами (telegram_log.txt) и уведомлениями в Telegram.

Проверьте корректность расчёта объёма сделки (qty), правильность установки плеча («Leverage set for all symbols») и работу механизмов входа/выхода (TP1, SL, Breakeven, Trailing Stop).

6. Дальнейшие действия после теста
   После успешного тестового запуска:

Проанализируйте логи, файлы tp_performance.csv и уведомления Telegram.

При подтверждении корректности работы замените фиксированные параметры (RISK_PERCENT и MAX_POSITIONS) на динамический расчет с помощью функций get_adaptive_risk_percent(balance) и get_max_positions(balance). Это позволит боту адаптироваться к изменению баланса без ручного вмешательства.

Этот документ включает все ключевые моменты: настройку параметров для минимизации риска на первом запуске, корректировки кода для устранения предупреждений линтера и дальнейший переход к полной автоматизации. Если всё соответствует требованиям, можно перейти к реализации и запуску теста.
