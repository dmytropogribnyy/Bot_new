# BinanceBot — Project Plan (v1.6.3, April 2025)

## ✨ Mission

Build an adaptive, semi-autonomous trading bot for **Binance USDC-M Futures**, optimized for small accounts (from $44) with a focus on risk-managed growth, learning, and smart signal handling.

## 🔄 Strategy Summary

### Multi-Timeframe Scalping Logic

- **HTF (1h)**: Trend confirmation (optional, ML-based toggle)
- **MTF (15m)**: Signal zone detection via indicators (RSI, MACD, EMA, BB)
- **LTF (5m)**: Entry execution based on score

### Signal Score System

- Each signal is evaluated based on weighted criteria:
  - MACD cross confirmation
  - RSI + EMAs
  - BB width / squeeze
  - Volume / volatility
  - HTF trend (if enabled)
- Adaptive threshold: base score varies with strategy phase and account size

### Entry Filters

- Symbol selection based on **volatility x volume**
- Smart dynamic filter thresholds (ATR / ADX / BB Width)
- Priority symbols and disabling of underperformers

## ⚖️ Risk Management

- **Adaptive position sizing**
- **Max concurrent trades**: 5–10 depending on balance
- **Daily loss protection** with auto SAFE or FULL STOP
- **Smart switching** between trades if new high-score signal appears
- **Symbol cooldowns** (30–60 min) to avoid overtrading

## 📈 Trade Structure

- Entry at signal score > adaptive threshold
- TP1 / TP2 with adaptive ratio (e.g., 0.7 / 0.3)
- SL based on ATR (dynamic per symbol)
- **Breakeven** and **trailing stop** support
- **Soft Exit** if trade nears TP1 and weakens
- Max Hold: 90 min (with possible +30 extension)

## 🪐 Intelligence Modules

- **HTF Optimizer**: Enables HTF only if winrate > 10% better
- **TP Optimizer**: Adjusts global and per-symbol TP1/TP2 levels weekly
- **ML TP Optimizer**: Uses winrate/SL data to adjust thresholds
- **Volatility Controller**: Skips too-flat symbols (optional in DRY_RUN)
- **Aggressiveness Score**: Switches mode based on PnL + streak

## 🚀 Infrastructure

- Modular codebase (`core/`, `telegram/`, `utils/`, `strategies/`, etc)
- DRY_RUN vs REAL_RUN logic with file-write protection
- Telegram Integration:
  - Full command interface (`/start`, `/stop`, `/status`, `/summary`, etc)
  - Daily / Weekly / Monthly / Quarterly / Yearly reports
  - IP monitor and reboot-safe protection
- Symbol Rotation every 60 min + cyclic group monitoring

## 🧪 Config Highlights (`config.py`)

- All risk and strategy parameters are centralized
- Threshold profiles: `default`, `default_light`, and per-symbol
- TP/SL ratios, volatility limits, HTF toggles, ML switches
- DRY_RUN/REAL_RUN behavior split

## 📊 Phased Roadmap

### Phase 1.0–1.5 — Complete

- Full strategy engine (multi-TF, indicators)
- Entry system, TP1/TP2/SL execution
- Telegram commands, summary, DRY_RUN
- HTF/ML/TP optimizer integration
- Aggressiveness detection + SAFE mode

### Phase 1.6 — In Progress / Finalizing

- ✅ Symbol rotation by group + score
- ✅ DRY_RUN-safe architecture
- ✅ TP Logger, Optimizers (HTF, TP, ML)
- ✅ Adaptive filters and per-symbol TP
- ✅ Telegram upgrades + IP Monitor

### Phase 1.7+ — Next

- **WebSocket integration**
  - Faster signal reaction (vs REST polling)
  - Live price tracking
  - Failover protection
- **Open Interest / Funding Rate filters**
- **Live signal statistics dashboard**
- **Portfolio auto-scaling**
- **Re-entry system with cooldown logic**

## 🔍 External Expansion (Future)

- CEX support modularization (e.g., KuCoin, Bybit)
- Strategy plug-and-play loading
- Backtest runner for CSV + live simulation
- Simple UI or Web Panel for reports

## ✅ Status (April 10, 2025)

- ✅ Stable release: `BinanceBot v1.6.3`
- ✅ All core features completed, test coverage via DRY_RUN
- ✅ Modular architecture, config-based control, Telegram synced
- ✅ Adaptive scoring, TP/SL, volatility filters, ML/HTF

---

> Next stop: Phase 1.7 — WebSocket, performance boost, re-entry AI
