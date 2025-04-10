BinanceBot TODO — v1.6.3 Roadmap (April 2025)
⭐ Priority 0 — Completed ✅
Full trade strategy (multi-TF, score-based)
TP1/TP2/SL execution, breakeven, trailing
Smart Switching between signals
HTF filter + auto optimizer
TP/Filter Optimizers (manual + ML)
Symbol rotation every 60 min with score-based sorting
Telegram: all commands, logs, IP monitor, reports
DRY_RUN isolation from real logs/files
⭐ Priority 1 — Core Enhancements (Next)
Timeline: 1-3 Weeks

1. Fix DRY_RUN Isolation for open_positions_count
   Problem: enter_trade increments open_positions_count in DRY_RUN, breaking isolation.
   Fix: In trade_engine.py, wrap open_positions_count += 1 in with open_positions_lock: with if not DRY_RUN:. Track DRY_RUN positions separately in trade_manager.
   Why: Ensures DRY_RUN is stateless, avoiding false position limits.
   Effort: Low (1 day).
2. Improve Graceful Shutdown
   Problem: os.\_exit(0) in engine_controller.py kills threads abruptly.
   Fix: Add a global running flag in utils_core.py. Check in all loops (e.g., run_trading_cycle, trailing threads) and exit cleanly when False. Tie to state["shutdown"].
   Why: Prevents data corruption, critical for REAL_RUN reliability.
   Effort: Low (1 day).
3. Merge last_trade_times into trade_manager
   Problem: Dual sources of truth in strategy.py vs. trade_manager.
   Fix: Move last_trade_times into TradeInfoManager as self.\_trades[symbol]["last_entry_time"]. Update strategy.py and symbol_processor.py to use trade_manager.get_last_entry_time(symbol).
   Why: Centralizes re-entry control, reducing bugs and lock contention.
   Effort: Low (1 day).
4. WebSocket Integration
   Approach:
   Create core/websocket_listener.py using Binance WebSocket API (wss://fstream.binance.com).
   Subscribe to ticker streams for active symbols (from pair_selector.py).
   Replace fetch_ticker/fetch_ohlcv polling in strategy.py with real-time updates, caching OHLCV in memory (e.g., asyncio queue).
   Add REST fallback in binance_api.py (reconnect every 5s).
   Why: Cuts latency from ~1s to milliseconds, improving signal timing and execution—key for scalping.
   Effort: Medium (2-3 days).
5. Auto TP/SL Scaling by Trend
   Approach:
   Enhance get_market_regime in trade_engine.py to return a scaling factor (e.g., 1.0 neutral, 0.8 flat, 1.2 trend via ADX).
   Adjust tp1_percent, tp2_percent, sl_percent in enter_trade: tp1_percent \*= scaling_factor.
   Why: Boosts profitability in trends, reduces losses in flats.
   Effort: Low (1 day).
6. Realistic Profit (PnL) Accounting
   Approach:
   In trade_engine.py, modify record_trade_result to subtract commission (e.g., 0.04% for Binance Futures).
   Include commission estimate in Telegram summary and logs.
   Why: Reflects true profitability.
   Effort: Low (1 day).
7. Fix tp_optimizer_ml Config Writer
   Approach:
   Replace line parsing in \_update_config with a JSON-based config_dynamic.json.
   Load/save TP values dynamically in config.py.
   Why: Improves maintainability and robustness.
   Effort: Low (1 day).
8. Re-entry Module (Refactor)
   Approach:
   Create core/reentry_manager.py to track profitable exits (store in trade_manager with PnL > 0).
   Add check_reentry: if score > last_score + 1.5 and cooldown (30 min) elapsed, trigger enter_trade(..., is_reentry=True).
   Move cooldown logic from strategy.py to trade_manager.
   Make thresholds adjustable in config.py.
   Why: Enhances returns via recurring opportunities.
   Effort: Medium (1-2 days).
9. Heatmap-based Score Tuner
   Approach:
   Add tune_weights() in score_heatmap.py to analyze recent winning signals (e.g., boost SCORE_WEIGHTS["MACD"] if correlated with wins).
   Update score_evaluator.py to use dynamic weights.
   Add /tune_score command in telegram_commands.py.
   Why: Adapts scoring to market shifts, improving signal accuracy.
   Effort: Medium (2 days).
10. Improve Sell Signal Logic
    Approach:
    In strategy.py, add MACD slope check (reject SELL if MACD rising).
    Optional: Add volume shrink or RSI > 70 filters in should_enter_trade.
    Consider EMA slope or candle patterns for confirmation.
    Why: Reduces false sell signals, improving accuracy.
    Effort: Medium (1-2 days).
    ⭐ Priority 2 — Analytics & Scaling
    Timeline: 1 Month After Priority 1

11. Correct Soft Exit PnL in Stats
    Approach:
    In trade_engine.py, adjust record_trade_result to compute effective exit price for Soft Exit partials (e.g., weighted average of soft exit and final exit).
    Why: Ensures accurate PnL reporting.
    Effort: Low (1 day).
12. Portfolio Auto-Scaling
    Approach:
    Extend get_adaptive_risk_percent in utils_core.py to scale risk (3% → 7% as balance grows from $100 to $1500).
    Adjust max_open_positions in symbol_processor.py similarly.
    Why: Optimizes capital use for growth.
    Effort: Low (1 day).
13. Live Dashboard for Reports
    Approach:
    Use Plotly in stats.py to generate HTML/PNG stats (trades, PnL, heatmap).
    Save to data/dashboard.html and send via Telegram.
    Why: Enhances monitoring beyond Telegram, aiding decision-making.
    Effort: Medium (2-3 days).
14. Dynamic Aggressiveness Adjuster
    Approach:
    In aggressiveness_controller.py, adjust AGGRESSIVENESS_THRESHOLD based on streaks/PnL (e.g., lower after 3 losses, raise after 5% PnL gain).
    Update config.py live.
    Why: Fine-tunes risk dynamically, reducing drawdowns.
    Effort: Medium (2 days).
    ⭐ Priority 3 — Ecosystem & UX
    Timeline: Post-v1.7

15. Web UI for Logs + Control
    Approach:
    Build a simple Flask app for logs, commands, and stats.
    Why: Provides a centralized interface for management.
16. Strategy Hot-Swap System
    Approach:
    Define a Strategy base class in core/strategy_base.py.
    Load/unload strategy modules dynamically in main.py.
    Implement a plug-and-play class interface.
    Why: Enables flexible strategy experimentation.
17. KuCoin/Bybit Port Adapters
    Approach:
    Move REST calls into binance_api.py.
    Abstract exchange into exchange_adapter.py with swappable implementations.
    Why: Expands bot compatibility to other exchanges.
    ⭐ Archived / Done
    ✅ ML TP Optimizer with per-symbol logic
    ✅ HTF trend auto-enabler with backup
    ✅ Symbol status tracking (boost, disable)
    ✅ DRY_RUN logic split + protection of all logs
    🔧 Technical Debts & Audit Fixes
    (Merged into Priority 1 & 2 where applicable)

18. CSV Result Field in TP Logs
    Status: Already done in tp_logger.py (confirmed in code).
    Details: Added "Result" field (TP1 / TP2 / SL / Soft Exit) to tp_logger.py. Unified stats with generate_daily_report().
19. Correct Soft Exit PnL in Stats
    Moved to Priority 2 #1
20. Fix DRY_RUN open_positions_count
    Moved to Priority 1 #1
21. Merge last_trade_times into trade_manager
    Moved to Priority 1 #3
22. Improve Graceful Shutdown
    Moved to Priority 1 #2
    Timeline & Order
    Immediate (1 Week)
    Tasks:
    Fix DRY_RUN isolation, graceful shutdown, merge last_trade_times (technical debts).
    Action: Test in DRY_RUN to confirm stability.
    Short-Term (2-3 Weeks)
    Tasks:
    WebSocket integration (speed boost).
    Auto TP/SL scaling (profit boost).
    Realistic PnL accounting (accuracy).
    Fix tp_optimizer_ml config writer (maintainability).
    Action: Test in DRY_RUN (target: 100+ trades, winrate > 60%, PnL > 0.5% after commissions). Deploy to REAL_RUN if stable.
    Mid-Term (1 Month)
    Tasks:
    Re-entry module (profit opportunity).
    Heatmap-based score tuner (adaptability).
    Improve sell signal logic (precision).
    Correct Soft Exit PnL (reporting).
    Action: Test thoroughly in DRY_RUN.
    Ongoing
    Tasks:
    Monitor via Telegram after each change.
    Scale to Priority 2 (analytics) once core upgrades are proven.
    Notes
    Updated: April 10, 2025 — synced with config.py, strategy.py, tp_optimizer.py, Telegram modules.
    Structure: Keeps all original items, integrates my roadmap, and merges technical debts into actionable priorities.
    REAL_RUN Readiness: Short-Term (2-3 weeks) is the recommended launch point, as discussed, balancing stability and performance.
    This roadmap is comprehensive, structured, and ready to guide your next steps. Start with the Immediate fixes, then hit the Short-Term upgrades—your first REAL_RUN is just 2-3 weeks away! Let me know if you need code snippets or further clarification!
