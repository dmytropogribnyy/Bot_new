# Binance USDC Futures Smart Bot — Full Documentation

**Version**: 1.2 STABLE
**Last Updated**: April 2025

This document provides a detailed overview of the Binance USDC Futures Smart Bot, including its functionality, architecture, and development roadmap. It’s designed for developers, optimizers, and strategists to understand the project’s current state and future direction.

---

## 🔧 Overview

The Binance USDC Futures Smart Bot is an advanced, autonomous trading bot for Binance USDC-M Futures perpetuals. It combines a multi-indicator strategy, adaptive risk management, and Telegram integration to deliver a robust, user-friendly trading experience.

### Key Features

- **📊 Multi-Indicator Strategy**: RSI, EMA, MACD, ATR, ADX, Bollinger Bands for signal generation.
- **🧠 Signal Strength**: Score-based filtering with logging to `score_history.csv`.
- **⚖️ Adaptive Risk Management**: Per-trade risk calculation, drawdown protection, SAFE/AGGRESSIVE modes.
- **🎯 TP1/TP2/SL**: Break-even, ADX-aware trailing stop, time-based limits with auto-extension.
- **📂 Dynamic Pair Selection**: 15–30 active pairs, auto-selected by volatility and volume.
- **📬 Telegram Integration**: Commands, notifications, and reports with MarkdownV2 formatting.
- **📈 Trade Tracking**: Logs trades to `tp_performance.csv`.
- **🔀 Self-Learning**: Auto-updates TP levels, filters, and pair statuses.
- **🧪 DRY_RUN Mode**: Simulates trading with softened filters, retaining real-mode logic.

---

## ✅ Phase 1: Stability and Protection (Completed)

**Status**: Fully implemented and stable.

- **Core Functionality**: Trading logic, entry filters, Telegram commands, logging, auto-backup, DRY_RUN mode.
- **Protection**: Auto-pause, auto-shutdown, failover for IP changes and API errors.

---

## 🔄 Phase 2: Profit Growth and Signal Quality (Mostly Completed)

**Status**: Most tasks done; some in progress.

- ✅ Enhanced Entry Strategy: Improved scoring and filtering (`strategy.py`).
- ✅ TP Optimizer: Logs TP outcomes, adjusts levels (`tp_performance.csv`, `tp_optimizer.py`).
- ✅ Smart Switching: Prioritizes stronger signals.
- ✅ Position Hold Timer: Limits hold time with auto-extension.
- ✅ Dynamic Pair Selection: 15–30 pairs, updated every 4 hours (`pair_selector.py`).
- ✅ Long/Short Filter Separation: Per-symbol filters (`FILTER_THRESHOLDS[symbol]["long"/"short"]`).
- ✅ Backtesting: 15m timeframe for BTC/USDC and ETH/USDC (`strategy.py`).
- ✅ Score History Logging: Signal scores logged to `score_history.csv`.
- 🟡 Smart Pair Rotation: Fully implemented; ongoing refinement.
- 🟡 Mini-Deployment: Planned for 50–100 USDC with loss control.

---

## 🛠 Phase 3: Usability and Informativeness (Optional)

**Status**: Not prioritized; planned post-Phase 2.

- Web dashboard for stats.
- Customizable Telegram reports with graphs.
- Interactive Telegram features (e.g., charts).

---

## 🚀 Phase 4: Advanced Trading (Future)

**Status**: Planned after Phases 2 and 3.

- Multi-strategy support.
- Multi-exchange architecture.
- Machine learning for TP and filter optimization.

---

## ⚙️ Additional Logic (Implemented)

- **Time-Based Filter**: No entries in the first 5 minutes of each hour.
- **Anti-Flood**: 30-minute re-entry cooldown per symbol.
- **Trend Confirmation**: 1h EMA validation.
- **Auto-Pairs**: Anchor pairs (e.g., BTC/USDC) plus dynamic selection.

**Status**: Stable, no further changes needed.

---

## 📬 Telegram Integration

**Status**: Stable, with MarkdownV2 formatting across most messages.

### Commands

| Command          | Description                                      |
| ---------------- | ------------------------------------------------ |
| `/help`          | List commands                                    |
| `/summary`       | Session stats (PnL, winrate)                     |
| `/status`        | Bot status (balance, mode, positions)            |
| `/open`          | List open positions                              |
| `/last`          | Last closed trade                                |
| `/mode`          | Current mode (SAFE/AGGRESSIVE)                   |
| `/pause`         | Pause new trades                                 |
| `/resume`        | Resume trading                                   |
| `/stop`          | Stop after closing positions                     |
| `/shutdown`      | Full exit after closing positions                |
| `/panic`         | Force-close all trades (confirm with "YES")      |
| `/log`           | Send daily log                                   |
| `/router_reboot` | 30-min IP monitoring (safe reboot)               |
| `/cancel_reboot` | Cancel reboot mode                               |
| `/ipstatus`      | Current/previous IP, reboot status               |
| `/forceipcheck`  | Force IP check                                   |
| `/pairstoday`    | Today’s active pairs                             |
| `/cancel_stop`   | Cancel pending stop                              |
| `/debuglog`      | Last 50 log lines (DRY_RUN only)                 |
| `/close_dry`     | Close DRY position (e.g., `/close_dry BTC/USDC`) |

### IP Change Behavior

1. **Unplanned Change** (e.g., outage):

   - Notifies with old/new IP and time (Bratislava).
   - Triggers `/stop`; cancellable with `/cancel_stop`.

   **Example:**

   ```
   ⚠️ IP Address Changed!
   🕒 04 Apr 2025, 15:16 (Bratislava)
   🌐 Old IP: 91.22.33.12
   🌐 New IP: 91.22.33.44
   🚫 Bot will stop after closing orders.
   ```

2. **Planned Reboot** (`/router_reboot`):

   - 30-min mode, checks IP every 3 mins.
   - Notifies on change but doesn’t stop.

   **Example:**

   ```
   ⚠️ IP Address Changed!
   🕒 04 Apr 2025, 15:16 (Bratislava)
   🌐 Old IP: 91.22.33.12
   🌐 New IP: 91.22.33.44
   ```

3. **Normal Operation**:
   - Checks IP every 30 mins.
   - Use `/ipstatus` or `/forceipcheck` for manual checks.

---

## 🔍 MarkdownV2: Challenges and Solutions

**Status**: Fixed and stable; applied across most messages.

### Challenges

- **Unescaped Characters**: `_` or `-` caused parsing errors.
- **Inconsistent Escaping**: Static vs. dynamic text mismatches.
- **Double Escaping**: Over-escaped characters.
- **Python Warnings**: Invalid escape sequences (e.g., `\,`).

### Solutions

- **Full Message Escaping**: Apply `escape_markdown_v2` to entire messages (`telegram_utils.py`).
- **No Manual Escaping**: Removed `\` in templates.
- **Centralized Logic**: Generators (e.g., `generate_summary`) escape output.
- **Simplified Structure**: Avoid reserved characters in static text.

### Best Practices

- Escape entire messages once.
- Test with special characters in a Telegram chat.
- Monitor API responses (logged in `utils.py`).

**Impact**: No parsing errors; improved readability and scalability.

---

## 📌 Current Priorities

1. **Binance WebSocket**: Replace polling with real-time data (`strategy.py`).
2. **Mini-Deployment**: Test with 50–100 USDC, focusing on loss control.
3. **Telegram Logic**: Simplify `telegram_utils.py`.
4. **Config Cleanup**: Merge volatility params in `config.py`.
5. **API Reliability**: Add auto-reconnect (`utils.py`).

---

## ✅ Project Status (v1.2 STABLE)

- **Core Features**: Fully functional (strategy, Telegram, IP monitoring, TP/SL).
- **Stability**: Ready for real-mode with robust error handling.
- **Architecture**: Modular (e.g., `main.py`, `strategy.py`, `ip_monitor.py`).

---

## 📝 Example Code

### Long/Short Filters (`config.py`)

```python
FILTER_THRESHOLDS = {
"BTC/USDC": {
   "long": {"atr": 0.0015, "adx": 7, "bb": 0.008},
   "short": {"atr": 0.0017, "adx": 8, "bb": 0.009},
},
}
filters = FILTER_THRESHOLDS[symbol]["long" if result == "buy" else "short"]
```

### MarkdownV2 Escaping (`telegram_utils.py`)

```python
def escape_markdown_v2(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    return "".join("\\" + char if char in escape_chars else char for char in str(text))
```

### Signal Scoring (`strategy.py`)

```python
def should_enter_trade(symbol, df):
    direction = "long" if last["close"] > last["ema"] else "short"
    filters = FILTER_THRESHOLDS.get(symbol, default_filters)[direction]
    score = 0
    if direction == "long" and last["rsi"] < 30: score += 1
    if direction == "short" and last["rsi"] > 70: score += 1
    if last["macd"] > last["signal"]: score += 1
    with open("data/score_history.csv", "a") as f:
        f.write(f"{datetime.now()},{symbol},{score}\n")
    return "buy" if direction == "long" and score >= MIN_TRADE_SCORE else "sell"
```

---

## 📋 Testing the Bot

Run:

```bash
python main.py
```

Verify:

- Starts in DRY_RUN without errors.
- Logs dry entries (e.g., "Dry entry log: BUY on BTC/USDC at 12345.67890").
- Test commands: `/help`, `/summary`, `/forceipcheck`.
- Stop with Ctrl+C: "🛑 Bot manually stopped".

Check Logs:

- No MarkdownV2 errors.
- Confirm "✅ Message sent successfully" in logs.

---

## 🗓 Next Steps

- Transition to WebSocket for real-time performance.
- Deploy with 50–100 USDC to validate in real mode.
- Refine Telegram logic and configuration for scalability.
