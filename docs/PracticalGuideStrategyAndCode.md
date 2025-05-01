# Practical Guide: Binance USDC Futures Bot — Strategy + Code (v1.6.4)

## 🌟 Goal

Automated USDC Futures scalping bot for Binance with:

- Multi-timeframe signal logic
- Risk-based trade sizing (5%)
- TP1 / TP2 / SL adaptive execution
- Commission-aware profit filter
- Target: $50/day with capital scaling from $44 to $1500

---

## 🔢 Strategy Logic Summary

### Timeframes:

- **1h** → Trend filter: EMA50 > EMA200
- **15m** → Signal generation: MACD, RSI, ATR
- **5m** → Entry confirmation: Stochastic RSI + Volume/BB filters

### Entry Conditions:

- Trend confirmed (1h) ✅ _(if HTF enabled)_
- MACD > Signal & RSI < 50 (buy), inverse for sell (15m)
- Stoch RSI < 20 or > 80 (5m)
- Score >= dynamic threshold
- Min profit after fees ✔ (TP1 - commission >= MIN_NET_PROFIT)
- Notional <= balance \* leverage

### Exit Structure:

- TP1 / TP2 adaptive via `tp_utils.py`
- SL from ATR or fixed percent (via regime detection)
- Soft Exit, Break-even, Trailing Stop
- Max Hold: 90 min (+30 if near TP1)

---

## 🧩 Step-by-Step Code Summary

### 1. Fetch & Filter Symbols

```python
if avg_volume < 10000 or score < threshold:
    return None
```

### 2. Calculate Indicators

```python
df['EMA50'] = EMA(df['close'], 50)
df['MACD'], df['MACD_signal'] = MACD(df['close'])
df['RSI'] = RSI(df['close'])
df['ATR'] = ATR(df)
df['BB_width'] = BB_Width(df['close'])
df['Stoch_K'] = StochRSI(df['close']) * 100
```

### 3. Trend Confirmation (1h)

```python
if df_1h['EMA50'].iloc[-1] > df_1h['EMA200'].iloc[-1]:
    trend = 'bullish'
```

### 4. Generate Signal (15m)

```python
if trend == 'bullish' and MACD > Signal and RSI < 50:
    signal = 'buy'
```

### 5. Confirm Entry (5m)

```python
if signal == 'buy' and Stoch_K < 20:
    confirmed = True
```

### 6. Risk Sizing + Order Qty

```python
from order_utils import calculate_order_quantity
qty = calculate_order_quantity(entry, stop, balance, risk_percent)
```

### 7. TP / SL Calculation

```python
from tp_utils import calculate_tp_levels
tp1, tp2, sl, share1, share2 = calculate_tp_levels(entry, side, regime)
```

### 8. Check Net Profit

```python
commission = 2 * qty * entry_price * TAKER_FEE_RATE
min_net = get_min_net_profit(balance)
if (tp1 - entry_price) * share1 * qty - commission < min_net:
    return None
```

### 9. Execute Orders

```python
create_limit_order(..., qty*0.7, tp1)
create_limit_order(..., qty*0.3, tp2)
create_stop_order(..., qty, sl)
```

### 10. Run Exit Threads

```python
Thread(target=run_soft_exit, args=(...)).start()
Thread(target=run_break_even, args=(...)).start()
Thread(target=run_trailing_stop, args=(...)).start()
```

---

## 🔧 Config Highlights

| Param          | Value     | Description                  |
| -------------- | --------- | ---------------------------- |
| RISK_PERCENT   | 0.01-0.05 | 1%-5% per trade              |
| TP1_PERCENT    | 0.007     | default (regime-scaled)      |
| TP2_PERCENT    | 0.013     | default (regime-scaled)      |
| SL_PERCENT     | 0.01      | or ATR-based                 |
| MIN_NET_PROFIT | 0.3-2.0   | per config, adaptive by size |
| MAX_POSITIONS  | 5-10      | by balance                   |
| LEVERAGE       | 5–10x     | per-symbol, auto-applied     |

---

## 🔍 Features Summary

- ✅ Commission-aware entry filtering
- ✅ Adaptive SL/TP logic (market regime aware)
- ✅ Automatic leverage set via API
- ✅ Modular architecture: `order_utils.py`, `tp_utils.py`
- ✅ DRY_RUN safe execution for testing
- ✅ Full Telegram control + stats

---

> Version: `v1.6.4` • Updated: April 15, 2025
