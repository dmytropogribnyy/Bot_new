# Practical Guide: Binance USDC Futures Bot — Strategy + Code (v1.6.3)

## 🎯 Goal

Automated USDC Futures scalping bot for Binance with:

- Multi-timeframe signal logic
- Risk-based trade sizing (5%)
- TP1 / TP2 / SL adaptive execution
- Target: $50/day with capital scaling from $44 to $1500

---

## 📐 Strategy Logic Summary

### Timeframes:

- **1h** → Trend filter: EMA50 > EMA200
- **15m** → Signal generation: MACD, RSI, ATR
- **5m** → Entry confirmation: Stochastic RSI

### Entry Conditions:

- ✅ Trend confirmed (1h)
- ✅ MACD > Signal & RSI < 50 (buy), inverse for sell (15m)
- ✅ Stoch RSI < 20 or > 80 (5m)

### Exit Conditions:

- **TP1** at +0.7%, **TP2** at +1.3%
- **SL** at -1.0% or ATR \* 1.5
- ✅ Break-even, Soft Exit, Trailing Stop (threads)

---

## 🧩 Step-by-Step Implementation (Code-driven)

### 1. Fetch & Filter Symbols

```python
if avg_volume < 10000:
    log(f"{symbol} rejected: low liquidity")
    return None
```

### 2. Calculate Indicators

```python
df['EMA50'] = EMA(df['close'], 50)
df['MACD'], df['MACD_signal'] = MACD(df['close'])
df['RSI'] = RSI(df['close'])
df['ATR'] = ATR(df)
df['Stoch_RSI_K'] = StochRSI(df['close']) * 100
```

### 3. Get Trend (1h)

```python
if df_1h['EMA50'].iloc[-1] > df_1h['EMA200'].iloc[-1]:
    trend = 'bullish'
```

### 4. Generate Signal (15m)

```python
if trend == 'bullish' and MACD > MACD_signal and RSI < 50:
    signal = 'buy'
```

### 5. Confirm Entry (5m)

```python
if signal == 'buy' and Stoch_RSI_K < 20:
    confirmed = True
```

### 6. Calculate Risk / SL / TP

```python
risk_amount = balance * 0.05
qty = risk_amount / abs(entry_price - sl)
sl = entry - ATR * 1.5
tp1 = entry + ATR * 2
```

### 7. Execute Entry

```python
safe_call_retry(create_limit_order, ..., qty*0.7, tp1)
safe_call_retry(create_limit_order, ..., qty*0.3, tp2)
safe_call_retry(create_stop_order, ..., qty, sl_price)
```

### 8. Launch Exit Threads

```python
Thread(target=run_soft_exit, args=(...)).start()
Thread(target=run_break_even, args=(...)).start()
Thread(target=run_trailing_stop, args=(...)).start()
```

### 9. Main Loop

```python
for symbol in active_symbols:
    df_1h, df_15m, df_5m = fetch(...)
    if signal and confirm:
        enter_trade(...)
```

---

## 🧪 Backtesting (Basic)

```python
class MultiTimeframeStrategy(bt.Strategy):
    def next(self):
        if EMA50 > EMA200:
            self.buy()
```

---

## 🛡️ Error Handling

```python
@retry(wait=wait_exponential(...))
def fetch_data_retry(...):
    return exchange.fetch_ohlcv(...)
```

---

## ⚙️ Performance Optimizations

- Use `ccxt.async_support`
- Cache positions, balance (TTL = 30s)
- Group fetches in batches

---

## 🔐 Security Tips

```python
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
```

---

## 📊 Monitoring & Scaling

- Daily/Weekly stats via `stats.py` and Telegram
- Scale to $500 → $1000 → $1500 based on winrate
- Use ML/HTF Optimizers for automated param tuning

---

## ✅ Summary Table

| Param         | Value | Description            |
| ------------- | ----- | ---------------------- |
| RISK_PERCENT  | 0.05  | 5% per trade           |
| TP1_PERCENT   | 0.007 | 0.7% target            |
| TP2_PERCENT   | 0.013 | 1.3% target            |
| SL_PERCENT    | 0.01  | 1.0% stop loss         |
| MAX_POSITIONS | 1-5   | Based on balance       |
| MIN_NOTIONAL  | 2     | Binance min trade size |

---

> Built for reliability, speed, and adaptive risk control. All logic DRY_RUN safe and modular.
