# 📌 BinanceBot — LIGHT TODO v1.6.2 [Priority View]

Быстрый рабочий список с актуальными кодовыми вставками и шагами для тестирования.
Обновлено по итогам аудита `v1.6.1-final-clean` и плана `v1.6.2-dev`.

---

## 🔝 Priority 1 — Adaptive MIN_TRADE_SCORE

🔧 Вставить в `strategy.py`:

```python
from tp_logger import get_trade_stats
trade_count, winrate = get_trade_stats()
min_required = get_adaptive_min_score(trade_count, winrate)

if DRY_RUN:
    log(f"{symbol} 🔎 Final Score: {score}/5 (Required: {min_required})")

if score < min_required:
    return None
```

🛠 Функция в `tp_logger.py`:

```python
def get_trade_stats():
    if not os.path.exists(EXPORT_PATH):
        return 0, 0.0
    df = pd.read_csv(EXPORT_PATH)
    df = df[df["Result"].isin(["TP1", "TP2", "SL"])]
    total = len(df)
    win = len(df[df["Result"].isin(["TP1", "TP2"])])
    return total, (win / total) if total else 0.0
```

✅ Протестировать:

- DRY_RUN: вывод логов с winrate и min_required
- REAL_RUN: сделки не открываются при низком score

---

## 🔝 Priority 2 — TP_THRESHOLDS per symbol

🔧 В `config.py`:

```python
TP_THRESHOLDS = {
    "BTC/USDC": {"tp1": 0.007, "tp2": 0.013},
    "ETH/USDC": {"tp1": 0.008, "tp2": 0.015},
    "default": {"tp1": TP1_PERCENT, "tp2": TP2_PERCENT},
}
```

🔧 В `trade_engine.py`:

```python
tp1_percent = TP_THRESHOLDS.get(symbol, {}).get("tp1", TP1_PERCENT)
tp2_percent = TP_THRESHOLDS.get(symbol, {}).get("tp2", TP2_PERCENT)
```

🛠 В `tp_optimizer_ml.py` — обновлённая `_update_config()`:

```python
def _update_config(symbol, tp1, tp2):
    with open(CONFIG_FILE, "r") as f:
        content = f.read()
    import re
    pattern = r"TP_THRESHOLDS\s*=\s*\{.*?\}"
    new_entry = f'    "{symbol}": {{"tp1": {tp1}, "tp2": {tp2}}},'
    if re.search(pattern, content, re.DOTALL):
        updated = re.sub(pattern, f'TP_THRESHOLDS = {{
{new_entry}
}}', content, flags=re.DOTALL)
    else:
        updated = content + f'
TP_THRESHOLDS = {{
{new_entry}
}}'
    with open(CONFIG_FILE, "w") as f:
        f.write(updated)
    log(f"Updated TP_THRESHOLDS for {symbol}: TP1={tp1}, TP2={tp2}", level="INFO")
```

замечание - дополнение по update config:
Функция \_update_config в tp_optimizer_ml.py:
Реализация с регулярным выражением обновлена, но есть нюанс: текущий код перезаписывает весь TP_THRESHOLDS, оставляя только новую запись ({symbol: {tp1, tp2}}), вместо добавления к существующему словарю. Это может сломать конфиг, если уже есть другие символы. Мое предложение было чуть сложнее — парсить текущий словарь и добавлять/обновлять запись. Вот исправленный вариант:

def \_update_config(symbol, tp1, tp2):
with open(CONFIG_FILE, "r") as f:
content = f.read()
import re
pattern = r"TP_THRESHOLDS\s*=\s*\{.\*?\}"
match = re.search(pattern, content, re.DOTALL)
if match: # Парсим текущий словарь
current_dict_str = match.group(0)
current_dict = eval(current_dict_str.replace("TP_THRESHOLDS =", "").strip()) # Обновляем или добавляем запись
current_dict[symbol] = {"tp1": tp1, "tp2": tp2}
updated = re.sub(pattern, f"TP_THRESHOLDS = {repr(current_dict)}", content)
else: # Если TP_THRESHOLDS нет, добавляем новый
new_entry = f' "{symbol}": {{"tp1": {tp1}, "tp2": {tp2}}},'
updated = content + f'\nTP_THRESHOLDS = {{\n{new_entry}\n}}'
with open(CONFIG_FILE, "w") as f:
f.write(updated)
log(f"Updated TP_THRESHOLDS for {symbol}: TP1={tp1}, TP2={tp2}", level="INFO")
Это сохранит существующие записи и добавит новые.
Тестирование:
Добавлено про Telegram-лог кастомных TP — хорошее дополнение, которого не было в вашем исходном варианте.
Вывод: Всё почти идеально, кроме \_update_config — нужно доработать, чтобы не терять старые данные.

✅ Протестировать:

- REAL_RUN: TP1/TP2 подставляются из config
- Telegram-лог: добавить сообщение об использовании кастомных TP

---

## 🔝 Priority 3 — Централизация фильтров (ATR, ADX, BB)

🔧 Функция в `strategy.py`:

```python
def passes_filters(df, symbol):
    filters = FILTER_THRESHOLDS.get(symbol, {"atr": 0.0015, "adx": 7, "bb": 0.008})
    atr_thres = filters["atr"] * (0.6 if DRY_RUN else 1.0)
    adx_thres = filters["adx"] * (0.6 if DRY_RUN else 1.0)
    bb_thres = filters["bb"] * (0.6 if DRY_RUN else 1.0)

    price = df["close"].iloc[-1]
    atr = df["atr"].iloc[-1] / price
    adx = df["adx"].iloc[-1]
    bb_width = df["bb_width"].iloc[-1] / price

    if atr < atr_thres:
        log(f"{symbol} ⛔️ Rejected: ATR too low ({atr:.5f} < {atr_thres})")
        return False
    if adx < adx_thres:
        log(f"{symbol} ⛔️ Rejected: ADX too low ({adx:.2f} < {adx_thres})")
        return False
    if bb_width < bb_thres:
        log(f"{symbol} ⛔️ Rejected: BB Width too low ({bb_width:.5f} < {bb_thres})")
        return False
    return True
```

📌 Использовать в `should_enter_trade`:

```python
if not passes_filters(df, symbol):
    return None
```

✅ Протестировать:

- DRY_RUN: логи причин отклонения
- Поведение сигналов в фильтре

---

## 🔝 Priority 4 — PnL график

🔧 В `stats.py`:

```python
def generate_pnl_graph(days=7):
    df = pd.read_csv(EXPORT_PATH, parse_dates=["Date"])
    df = df[df["Date"] >= datetime.now() - timedelta(days=days)]
    if df.empty: return
    df["Cumulative PnL"] = df["PnL (%)"].cumsum()
    plt.figure(figsize=(10, 6))
    plt.plot(df["Date"], df["Cumulative PnL"], label="Cumulative PnL (%)")
    plt.title(f"PnL Over Last {days} Days")
    plt.xlabel("Date")
    plt.ylabel("Cumulative PnL (%)")
    plt.legend()
    plt.grid()
    plt.savefig("data/pnl_graph.png")
    plt.close()
    send_telegram_image("data/pnl_graph.png", caption=escape_markdown_v2(f"PnL Graph ({days}d)"))
    log("PnL graph sent", level="INFO")
```

📌 Добавить в `start_report_loops()`:

```python
if t.weekday() == 4 and t.hour == 20 and t.minute == 0:
    generate_pnl_graph(days=7)
```

✅ Протестировать:

- Генерация PNG
- Отправка в Telegram
- Проверка читаемости и масштабов

---

✅ Использовать вместе с `PROJECT_PLAN_v1.6.2.md` как боевой `dev helper` для реализации.
