# Practical Guide: Binance USDC Futures Bot — Strategy + Code (v1.7.0)

## 🌟 Goal

Automated USDC Futures scalping bot for Binance with:

-   Multi-timeframe signal logic
-   Adaptive risk-based trade sizing (1-5%)
-   ATR-based TP/SL calculation with minimums
-   Commission-aware profit filtering
-   Target: Growing from $100-120 to $700+ USDC

---

## 🔢 Strategy Logic Summary

### Timeframes:

-   **1h** → Trend filter: EMA50 > EMA200
-   **15m** → Signal generation: MACD, RSI, ATR
-   **5m** → Entry confirmation: Stochastic RSI + Volume/BB filters

### Entry Conditions:

-   Trend confirmed (1h) ✅ _(if HTF enabled)_
-   MACD > Signal & RSI < 50 (buy), inverse for sell (15m)
-   Stoch RSI < 20 or > 80 (5m)
-   Score >= adaptive threshold (lower for small accounts)
-   Min profit after fees ✔ (TP1 - commission >= MIN_NET_PROFIT)
-   Risk/Reward ratio meets minimum for signal strength
-   Notional <= balance \* leverage

### Exit Structure:

-   TP1 / TP2 adaptive via ATR (min: 0.7% / 1.3%)
-   SL from ATR (min: 1.0%)
-   Soft Exit, Break-even, Trailing Stop
-   Max Hold: 90 min (+30 if near TP1)

---

## 🧩 Optimized for Small Accounts (100-120 USDC)

### 1. Risk Management:

```python
def get_adaptive_risk_percent(balance):
    if balance < 100:
        return 0.01  # 1%
    elif balance < 150:
        return 0.02  # 2%
    elif balance < 300:
        return 0.03  # 3%
    else:
        return 0.05  # 5%

def get_max_positions(balance):
    if balance < 100:
        return 1
    elif balance < 150:
        return 2
    elif balance < 300:
        return 3
    else:
        return 5
2. ATR-based TP/SL:
pythondef calculate_tp_levels(entry_price, side, regime, score, df):
    # Default static minimums
    tp1_pct = TP1_PERCENT  # 0.7%
    tp2_pct = TP2_PERCENT  # 1.3%
    sl_pct = SL_PERCENT    # 1.0%

    # Use ATR if available
    if df is not None and 'atr' in df.columns:
        atr = df['atr'].iloc[-1]
        atr_pct = atr / entry_price

        # ATR-based with minimums
        tp1_pct = max(atr_pct * 1.0, TP1_PERCENT)
        tp2_pct = max(atr_pct * 2.0, TP2_PERCENT)
        sl_pct = max(atr_pct * 1.5, SL_PERCENT)

    # Apply market regime adjustments
    # ...
3. Commission-Aware Profit Filter:
python# Calculate estimated profit after fees
commission = qty * entry_price * TAKER_FEE_RATE * 2  # Open and close
expected_profit = qty * tp1_share * abs(tp1_price - entry) - commission

# Skip unprofitable trades
min_profit = get_min_net_profit(balance)  # 0.2-0.3 USDC for small accounts
if expected_profit < min_profit:
    return None  # Skip trade

🔍 Features Summary

✅ Adaptive risk & position sizing based on account size
✅ ATR-based TP/SL with market regime adjustments
✅ Commission-aware profit filtering
✅ Priority pairs for small accounts (XRP, DOGE, ADA)
✅ Required Risk/Reward ratio based on signal quality
✅ 90% margin safety buffer
✅ Full Telegram control + stats



Version: v1.7.0 • Updated: May 2025
```
