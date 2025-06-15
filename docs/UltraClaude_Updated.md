# 🤖 UltraClaude Bot Overview — Core Architecture & Capabilities

## 📌 Summary

UltraClaude (OptiFlow v2.9 Core) is a fully modular, resilient crypto trading bot designed for low-latency, high-safety execution on Binance (USDC pairs). It serves as the **foundational engine** for future scalping/HFT bots like OptiScalp A/B/C.

---

## ⚙️ Core Features (OptiFlow v2.9 Final)

### 🔁 Trading Logic

-   **1+1 Signal Model** with adaptive filtering (MACD, EMA, RSI + Volume, PA, HTF)
-   **ATR/Volume filters** with runtime tiers
-   **Notional & Spread filter** — ensures minimum size and liquidity
-   **Stepwise TP1/TP2/SL** via ATR regime
-   **Auto-profit logic** — closes on +2.5% profit if no TP1
-   **Timeout logic** with PnL escape (don’t close if +1.0%)
-   **Reactive re-entry** after safe_close

### 📉 Risk Protection

-   **Anti-reentry (5m)** per symbol (cooldown)
-   **Auto-pause after 3 SL** (15 min per symbol)
-   **Daily max loss stop** (if daily_pnl < -5 USDC)
-   **Drawdown control**: dynamic max_risk reduction and halt
-   **Max concurrent positions**: 12 (adaptive)
-   **Capital utilization limit**: max 80%
-   **Max trades/hour**: 6

### 📊 TP/SL Engine

-   **ATR-based TP1/TP2/SL levels** with regime (trend/flat/breakout)
-   **Stepwise TP1 (0.1 → 0.4)** with partial exits
-   **Trailing logic & TP extension** if strong momentum
-   **Auto-close after 60m if PnL < 1%**

### 📥 Entry System

-   **should_enter_trade(...)** uses multi-frame indicators, filters, and adaptive risk
-   **process_symbol(...)** enforces notional, margin, min_profit
-   **enter_trade(...)** manages safe entry, leverage, TP/SL placement, DRY_RUN
-   **fetch_data_multiframe(...)** processes 3m/5m/15m OHLCV with ta indicators

---

## 📬 Telegram Interface

-   `/summary`, `/runtime`, `/logtail`, `/pnl_today`, `/riskstatus`, `/shutdown`
-   Auto-escape markdown, error fallback enabled
-   Live PnL, risk, and TP reports
-   Recovery commands: `/panic`, `/restore`, `/backups`

---

## 🔄 Monitoring & Logs

-   **monitor_active_position(...)**: real-time tracking of TP1/TP2/SL, profit stages, timeout
-   **tp_performance.csv**: TP/SL hit log, used for optimization
-   **entry_log.csv**, `missed_opportunities.json`: for signal filtering audit
-   **component_tracker_log.json**: signal component statistics
-   **debug_monitoring_summary.json**: live status dump

---

## 🧠 Strategy Status

-   Fully compatible with parallel bot deployment (shared core)
-   DRY_RUN supported
-   Safe restart via `restore_active_trades()`
-   Ready for:

    -   🟢 OptiScalp A/B/C (HFT modules)
    -   🟢 Grid/Funding modules
    -   🟢 Swing/TP2-only strategies

---

## 🔐 Stability & Recovery

-   Crash-safe `main.py` with `stop_event`
-   Runtime config autoload, `parameter_history.json`
-   Safe close + cancel orders on panic
-   Auto-risk adjustment every hour
-   Compatible with pm2/systemd

---

## ✅ Current Deployment Status

-   Production-ready (v2.9 Final)
-   All 1.1 core components refactored and tested
-   Telegram/Runtime protection layers active
-   Core validated on real balance (≈ \$225 USDC)

---

Want to scale? Use `parallel_launcher.py` with configs like:

-   `runtime_config_optiscalpA.json`
-   `runtime_config_optiswingB.json`

---

For advanced usage:

-   Add WebSocket triggers (ws_price_listener.py)
-   Add `/signalstats`, `/topmissed` via Telegram
-   Adapt `entry_logger.py` to include all `exit_reason`
