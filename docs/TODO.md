# TODO: Binance USDC Futures Smart Bot

Version: 1.2 STABLE
Last Updated: April 2025

This file tracks ongoing and planned tasks for the Binance USDC Futures Smart Bot, organized by priority and status.

---

## Completed Tasks

- API Caching — get_cached_balance, get_cached_positions in utils.py
- Thread Safety — Locks added for trade_stats, last_trade_info in config.py, trade_engine.py
- Critical Event Logging — Logs limited to ERROR in real mode (REAL_RUN)
- Backtesting — 15m for BTC/USDC and ETH/USDC (strategy.py)
- Score History Logging — Scoring to score_history.csv
- Smart Pair Rotation — Refreshes every 4 hours via main.py, pair_selector.py
- MarkdownV2 Fixes — Unified escaping using escape_markdown_v2 (telegram_utils.py)
- Long/Short Filter Separation — Implemented per-symbol filters in strategy.py, config.py

---

## Priority 1: Core Enhancements

- Binance WebSocket Integration

  - Replace polling with real-time price updates
  - Modify fetch_data in strategy.py
  - Estimate: 6–8 hours

- Mini-Deployment with Loss Control
  - Test real-mode logic with 50–100 USDC and safety net
  - Controlled launch via main.py, validate loss limits
  - Estimate: 3–4 hours + live testing

---

## Priority 2: Usability and Refinement

- Simplify Telegram Logic

  - Refactor send_telegram_message() in telegram_utils.py
  - Estimate: 1–2 hours

- Clean Up config.py

  - Merge volatility-related configs like VOLATILITY_ATR_THRESHOLD
  - Example: effective_atr = VOLATILITY_ATR_THRESHOLD \* (0.6 if DRY_RUN else 1)
  - Estimate: 2 hours

- Complete MarkdownV2 Formatting
  - Ensure all Telegram messages are escaped properly
  - Check all send_telegram_message() calls across modules
  - Estimate: 2–3 hours

---

## Priority 3: Reliability and Scalability

- Auto-Reconnect on API Failures
  - Improve resilience of exchange calls in real mode
  - Add tenacity retry logic in utils.py
  - Example: retry with wait_exponential in fetch_balance_with_retry()
  - Estimate: 2 hours

---

## Priority 4: Optional Features

- PnL and Balance Charts
  - Visual performance summary in Telegram
  - Add chart generation via matplotlib or ASCII in stats.py
  - Estimate: 4–6 hours

---

## Execution Order

1. Binance WebSocket Integration
2. Mini-Deployment with Loss Control
3. Complete MarkdownV2 Formatting
4. Simplify Telegram Logic
5. Clean Up config.py
6. Auto-Reconnect on API Failures
7. PnL and Balance Charts (optional)

---

## Notes

Priority 1: Critical for performance and real-world validation
Priority 2: Developer-friendly improvements and maintainability
Priority 3: Resilience and long-term uptime
Priority 4: Bonus features for user experience

Next Focus: Start with WebSocket integration to enable real-time reactions and reduce latency.
