# Practical Guide: Binance USDC‑Futures Bot — Strategy + Code (v2.0.0)

_Last major update: May 2025_

---

## 🌟 Primary Objectives

-   **Phase 1 (micro‑deposit 120 USDC)** — average **+10 USDC per day** (\~8 %) with controlled risk.
-   **Phase 2‑4 (scaling to 1 500 USDC+)** — stair‑step growth to **60 USDC +/day** while _reducing_ %‑risk per trade.

---

## 🔢 Strategy Logic Snapshot

| TF       | Purpose       | Core Indicators                         |
| -------- | ------------- | --------------------------------------- |
| **1 h**  | Trend gate    | EMA 50 > EMA 200                        |
| **15 m** | Signal        | MACD cross, RSI (14), ATR %, ADX filter |
| **5 m**  | Entry trigger | Stoch RSI, Volume Δ, BB ± 1σ            |

Entry ▶️ _trend ok_ ➜ _signal score ≥ S_ ➜ _entry trigger_ ➜ _commission‑filter_ ➜ _dynamic filter passes_.

Exit ▶️ TP1/TP2 (ATR %), break‑even, trailing, micro‑profit timeout, hard SL.

---

## ⚙️ Dynamic Pair Filter (ATR % + Volume)

```python
# core/dynamic_filters.py
BASE_ATR  = 0.19   # %
BASE_VOL  = 16_000  # USDC
FLOOR_ATR = 0.17
FLOOR_VOL = 13_000

def get_dynamic_filter_thresholds(symbol, market_regime=None):
    atr = BASE_ATR
    vol = BASE_VOL
    if market_regime == "breakout":
        atr *= 0.75; vol *= 0.75
    elif market_regime == "trend":
        atr *= 0.85; vol *= 0.85
    elif market_regime == "flat":
        atr *= 1.05
    aggr = get_aggressiveness_score()
    if aggr > 0.7:
        atr *= 0.9; vol *= 0.9
    return {
        "min_atr_percent": max(atr, FLOOR_ATR),
        "min_volume_usdc": max(vol, FLOOR_VOL),
    }
```

---

## 💰 Adaptive Risk Management

```python
# core/risk_utils.py
BASES = [(0, 0.020), (100, 0.023), (150, 0.028)]  # balance → base‑risk

CAPS  = {
    (0.70, 1.80): 0.035,   # win‑rate, PF → cap
    (0.75, 2.00): 0.038,
}

def get_adaptive_risk_percent(balance, atr_pct, vol_usdc, win_streak, score):
    base = next(r for b, r in reversed(BASES) if balance >= b)
    bonus = 0
    if atr_pct > 0.40: bonus += 0.008
    elif atr_pct > 0.30: bonus += 0.005
    if vol_usdc > 100_000: bonus += 0.006
    elif vol_usdc > 50_000: bonus += 0.004
    bonus += min(win_streak*0.002, 0.006)
    if score > 4: bonus += 0.006
    elif score > 3.5: bonus += 0.003
    cap = 0.030
    wr, pf = get_performance_stats().values()
    for (w,p), c in CAPS.items():
        if wr >= w and pf >= p: cap = c
    return min(base + bonus, cap)
```

Limits: **max 2 open positions** when balance < 150 USDC.

---

## 🎯 TP / SL (15‑m)

```
TP1_PERCENT = 0.008   # 0.8 %
TP2_PERCENT = 0.016   # 1.6 %
SL_PERCENT  = 0.007   # 0.7 %
TP1_SHARE   = 0.80    # 80 % size closed at TP1
BREAKEVEN_TRIGGER = 0.30  # move SL → BE after 30 % path
```

---

## 🔐 Protection Stack

-   **Drawdown guard:** risk −25 % at max(8 %, 50 USDC); bot pause at max(15 %, 100 USDC).
-   **Performance breaker:** if 20‑trade rolling Win < 50 % _and_ PF < 1 → risk × 0.6.
-   **Auto‑stop on empty position** in `trailing_*` functions.

---

## 📈 Scaling Roadmap

| Deposit   | Risk %  | Max pos | Leverage cap                     | Daily target | KPI gate to next tier                   |
| --------- | ------- | ------- | -------------------------------- | ------------ | --------------------------------------- |
| 120‑300   | 2.3‑3.8 | 2‑3     | ≤ 6× (8× if WR ≥ 72 %, PF ≥ 1.9) | 10‑25        | WR ≥ 70 %, PF ≥ 1.8, ≥ 90 % target 14 d |
| 300‑750   | 2.0‑3.2 | 3‑5     | ≤ 6×                             | 25‑40        | WR +2 %, PF +0.2                        |
| 750‑1 500 | 1.8‑3.0 | 5‑7     | ≤ 5×                             | 40‑80        | "                                       |
| 1 500+    | 1.5‑2.5 | 7‑10    | ≤ 5×                             | 80+          | "                                       |

Volume filter: **+5 k USDC** per +250 USDC deposit. ATR % floor unchanged.

---

## 🔍 Quick Feature Checklist

✅ Dynamic ATR/Volume filter ✅ Progressive risk cap ✅ TP1/TP2/SL 0.8‑1.6‑0.7 % ✅ 2‑position limit (<150 USDC) ✅ Drawdown 8 %/15 % ✅ Circuit‑breaker ✅ Pair rotation 5 min ✅ Candle‑analyzer (toggle) ✅ Micro‑profit monitor ✅ Telegram commands `/risk`, `/filters`, `/goal`.

---

## 🗂️ File Map (v2.0.0)

```
core/
 ├─ dynamic_filters.py      # ATR/Volume thresholds
 ├─ risk_utils.py           # adaptive risk + drawdown guard
 ├─ candle_analyzer.py      # optional candle‑strength filter
 ├─ pair_rotation.py        # 5‑min priority list
trade_engine.py            # trailing fixes + micro‑profit
telegram_commands.py       # /risk /filters /goal
config_loader.py           # TP/SL + leverage map
stats.py                   # performance & circuit‑breaker
position_manager.py        # open‑position limits
```

---

## 📝 Notes for Future Review

-   **Latency watch:** ensure added filters keep total decision time < 15 ms.
-   **CUR target:** keep Capital Utilization Rate 55‑70 %; adjust filters if < 40 %.
-   **Tier promotions** auto‑trigger via `scaling_manager.check_tier()`.

---

Happy scaling & safe trades! 🚀
