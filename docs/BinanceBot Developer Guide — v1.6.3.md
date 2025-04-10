# BinanceBot Developer Guide — v1.6.3

## 📁 Structure

```
project/
  config.py
  main.py
  core/
    strategy.py
    trade_engine.py
    score_evaluator.py
    volatility_controller.py
    htf_optimizer.py
    tp_optimizer.py
    tp_optimizer_ml.py
    aggressiveness_controller.py
    entry_logger.py
  telegram/
    telegram_utils.py
    telegram_commands.py
    telegram_handler.py
    telegram_ip_commands.py
  utils/
    utils_core.py
    utils_logging.py
  pair_selector.py
  binance_api.py
  ip_monitor.py
  data/
    tp_performance.csv
    backups/
    logs/
```

## ⚙️ Core Modules

### `main.py`

- Starts all threads: trading loop, symbol rotation, report loops
- DRY_RUN/REAL_RUN split
- Cyclic group scanning (5 pairs at a time)

### `trade_engine.py`

- Executes entries and exits (TP1/TP2/SL/Breakeven)
- Validates signal, score, symbol status
- Handles smart switching logic

### `strategy.py`

- Builds indicators (EMA, MACD, RSI, BB, ADX, ATR)
- Applies filters (score, volatility, HTF trend)

### `score_evaluator.py`

- Combines weighted components into a single score
- Uses `SCORE_WEIGHTS` and dynamic thresholds

### `pair_selector.py`

- Selects top 15–30 symbols based on volatility \* volume
- Saves to `dynamic_symbols.json`
- Runs every 60 min in background

## 🌎 API + Exchange

### `binance_api.py`

- Wrapper for all Binance REST calls
- Will be abstracted for KuCoin/Bybit later

### `exchange` object

- Defined in `config.py` via ccxt
- Passed implicitly via imports

## 🎓 Intelligence

### `tp_optimizer.py`

- Calculates winrate for TP1/TP2/SL
- Adjusts TP % levels if deviation > threshold
- Also optimizes ATR/ADX/BB thresholds per symbol

### `tp_optimizer_ml.py`

- Uses historical trades to propose new TP1/TP2 per symbol
- Updates `config.py` with safe bounds (via rewrite)

### `htf_optimizer.py`

- Analyzes winrate with vs without HTF filter
- Enables or disables HTF dynamically

### `aggressiveness_controller.py`

- Evaluates PnL/streak to switch strategy mode
- If loss streak > N or drawdown > threshold → SAFE MODE

## 📊 Logs / Data

- `tp_logger.py`: logs every trade (TP1/TP2/SL), duration, PnL, filters
- `tp_performance.csv`: main file for optimizer analysis
- `entry_logger.py`: logs every signal (even ignored ones)
- `bot_state.json`: persists flags (pause, stop, shutdown)

## 📈 Reports

- `stats.py` + `main.py` generate:
  - Daily (21:00)
  - Weekly (Sun)
  - Monthly / Quarterly / Yearly
  - Heatmap (score per symbol)
- All sent via Telegram

## 📢 Telegram Integration

- `telegram_utils.py`: all send functions, MarkdownV2 safe
- `telegram_commands.py`: `/start`, `/stop`, `/summary`, `/log`, etc
- `telegram_handler.py`: command listener in thread
- `telegram_ip_commands.py`: `/ipstatus`, `/router_reboot`, etc

## 🚫 DRY_RUN Protections

- DRY_RUN = True → all writes/logs skipped
- Only console output allowed
- Used for testing and evaluation

## 🚀 Next: WebSocket (v1.7+)

- Will live in `core/websocket_listener.py`
- Uses Binance Futures Stream API
- Monitors live price and symbol state
- Replaces polling loop in `run_trading_cycle`

---

> For bug reports or module debugging, enable `LOG_LEVEL = "DEBUG"` in config.
> All logs saved to `telegram_log.txt` with auto-rotation and filelock.
