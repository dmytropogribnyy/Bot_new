# 📌 BinanceBot — LIGHT TODO v1.6.2 [Priority View]

Используется как быстрый рабочий список с кодовыми вставками.

---

## 🔝 Priority 1 — Adaptive MIN_TRADE_SCORE

🔧 Вставить в `strategy.py`:

```python
from tp_logger import get_trade_stats
trade_count, winrate = get_trade_stats()
min_required = get_adaptive_min_score(trade_count, winrate)
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

✅ Протестировать: log в DRY_RUN и поведение входа в сделку

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
tp1 = TP_THRESHOLDS.get(symbol, {}).get("tp1", TP1_PERCENT)
tp2 = TP_THRESHOLDS.get(symbol, {}).get("tp2", TP2_PERCENT)
```

🛠 В `tp_optimizer_ml.py`: изменить `_update_config()` для корректной вставки

---

## 🔝 Priority 3 — Централизация фильтров

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

    if atr < atr_thres or adx < adx_thres or bb_width < bb_thres:
        return False
    return True
```

📌 Использовать в `should_enter_trade`:

```python
if not passes_filters(df, symbol):
    return None
```

---

## 🔝 Priority 4 — PnL график

🔧 В `stats.py`:

```python
def generate_pnl_graph(days=7):
    df = pd.read_csv(EXPORT_PATH, parse_dates=["Date"])
    df = df[df["Date"] >= datetime.now() - timedelta(days=days)]
    if df.empty: return
    df["Cumulative PnL"] = df["PnL (%)"].cumsum()
    plt.plot(df["Date"], df["Cumulative PnL"])
    plt.savefig("data/pnl_graph.png")
    send_telegram_image("data/pnl_graph.png", caption="PnL Graph")
```

🧪 Добавить в еженедельный цикл или по команде

---

✅ Использовать вместе с `PROJECT_PLAN_v1.6.2.md` как боевой чеклист + dev helper