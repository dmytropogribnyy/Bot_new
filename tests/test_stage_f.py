#!/usr/bin/env python3
"""Stage F tests - Global daily risk guard"""

from core.config import TradingConfig
from core.risk_guard_stage_f import RiskGuardStageF


def test_stage_f_sl_streak_block(tmp_path):
    cfg = TradingConfig()
    cfg.enable_stage_f_guard = True
    cfg.max_sl_streak = 2
    # isolate state
    cfg.stage_f_state_path = str(tmp_path / "stage_f_state.json")

    class _Logger:
        def log_event(self, *_args, **_kwargs):
            return None

    guard = RiskGuardStageF(cfg, _Logger())
    # two consecutive losses of any pct
    guard.record_trade_close(-1.0)
    guard.record_trade_close(-0.5)
    can, reason = guard.can_open_new_position()
    assert can is False
    assert "SL streak" in reason


def test_stage_f_daily_loss_block(tmp_path):
    cfg = TradingConfig()
    cfg.enable_stage_f_guard = True
    cfg.daily_drawdown_pct = 2.0
    cfg.stage_f_state_path = str(tmp_path / "stage_f_state2.json")

    class _Logger:
        def log_event(self, *_args, **_kwargs):
            return None

    guard = RiskGuardStageF(cfg, _Logger())
    # Accumulate losses to exceed threshold
    guard.record_trade_close(-1.1)
    guard.record_trade_close(-1.0)
    can, reason = guard.can_open_new_position()
    assert can is False
    assert "Daily loss" in reason
