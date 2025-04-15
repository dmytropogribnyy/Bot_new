# BinanceBot TODO — v1.6.4 Roadmap (April 2025)

## ⭐ Priority 0 — Completed ✅

- Full trade strategy (multi-TF, score-based)
- TP1/TP2/SL execution, breakeven, trailing
- Smart Switching between signals
- HTF filter + auto optimizer
- TP/Filter Optimizers (manual + ML)
- Symbol rotation every 60 min with score-based sorting
- Telegram: all commands, logs, IP monitor, reports
- DRY_RUN isolation from real logs/files
- ✅ Commission-aware entry filter (TP1 net profit check)
- ✅ Modular order/TP logic via `order_utils.py` and `tp_utils.py`
- ✅ Auto leverage setup via API using LEVERAGE_MAP
- ✅ Margin check before entry (notional <= balance × leverage)

## ⭐ Priority 1 — Core Enhancements (Next)

**Timeline: 1–3 Weeks**

1. **Fix DRY_RUN Isolation for open_positions_count**

   - Fix increment logic to avoid interfering with real counters.
   - Effort: Low - Completed ✅

2. **Improve Graceful Shutdown**

   - Add global flag (`running`) tied to state, safely exit loops.
   - Effort: Low - Completed ✅

3. **Merge last_trade_times into trade_manager**

   - Unify control logic for re-entry.
   - Effort: Low

4. **Auto TP/SL Scaling by Trend**

   - Apply scaling factor in `get_market_regime()`
   - Effort: Low

5. **Realistic Profit (PnL) Accounting**

   - Subtract commission from PnL in reports/logs.
   - Effort: Low

6. **Fix tp_optimizer_ml Config Writer**

   - Switch to `config_dynamic.json`, remove line parsing.
   - Effort: Low

7. **Re-entry Module (Refactor)**

   - Create `reentry_manager.py`, move cooldown logic.
   - Effort: Medium

8. **Heatmap-based Score Tuner**

   - Tune `SCORE_WEIGHTS` dynamically based on recent wins.
   - Add `/tune_score` command.
   - Effort: Medium

9. **Improve Sell Signal Logic**

   - Add MACD slope & volume/RSI filters for short entries.
   - Effort: Medium

10. **Telegram Auto Summary & Heatmap**

    - Schedule daily/weekly reports.
    - Include score heatmap.
    - Effort: Medium

11. **DRY_RUN Trade Tracker Refactor**

    - Move DRY_RUN tracking fully into `trade_manager`.
    - Use in `/open`, `/stop`, `/status`, `/summary`.
    - Effort: Low

12. **WebSocket Integration**

    - Replace polling with Binance Futures WebSocket API.
    - Add fallback to REST.
    - Effort: Medium

## ⭐ Priority 2 — Analytics & Scaling

**Timeline: 1 Month After Priority 1**

13. **Correct Soft Exit PnL in Stats**

    - Adjust weighted average logic.
    - Effort: Low

14. **Portfolio Auto-Scaling**

    - Scale risk and max positions by balance.
    - Effort: Low

15. **Live Dashboard for Reports**

    - Use Plotly to generate visuals.
    - Save `dashboard.html`, send via Telegram.
    - Effort: Medium

16. **Dynamic Aggressiveness Adjuster**

    - Modify threshold based on streaks/PnL curve.
    - Effort: Medium

## ⭐ Priority 3 — Ecosystem & UX

**Timeline: Post-v1.7**

17. **Web UI for Logs + Control**

    - Flask app for web dashboard.

18. **Strategy Hot-Swap System**

    - Plug-and-play strategies via `strategy_base.py`.

19. **KuCoin/Bybit Port Adapters**

    - Modularize exchange adapter interface.

---

**Updated:** April 15, 2025
**Status:** Synced with v1.6.4 features and testing.
