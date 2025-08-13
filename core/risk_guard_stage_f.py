#!/usr/bin/env python3
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass
class GlobalRiskState:
    sl_streak: int = 0
    daily_loss_pct: float = 0.0
    last_reset_date: str = ""


class RiskGuardStageF:
    """
    Global per-day guard: blocks ALL new positions if:
      - consecutive SLs >= max_sl_streak
      - daily_loss_pct >= daily_drawdown_pct
    Independent from risk_utils.check_drawdown_protection (which is cumulative).
    State persists in config.stage_f_state_path.
    """

    def __init__(self, config, logger):
        self.cfg = config
        self.logger = logger
        self.state_path = getattr(config, "stage_f_state_path", "data/runtime/stage_f_state.json")
        self.state = self._load_state()

    def _log(self, message: str, level: str = "INFO"):
        try:
            # UnifiedLogger expects log_event(component, level, message)
            if hasattr(self.logger, "log_event"):
                self.logger.log_event("RISK_F", level, message)
            else:
                # fallback: callable logger
                self.logger(message)
        except Exception:
            pass

    def _load_state(self) -> GlobalRiskState:
        try:
            if os.path.exists(self.state_path):
                with open(self.state_path, encoding="utf-8") as f:
                    data = json.load(f)
                return GlobalRiskState(**data)
        except Exception:
            pass
        today = datetime.now(UTC).date().isoformat()
        return GlobalRiskState(sl_streak=0, daily_loss_pct=0.0, last_reset_date=today)

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(self.state.__dict__, f)
        except Exception:
            pass

    def _rollover_if_new_day(self):
        today = datetime.now(UTC).date().isoformat()
        if self.state.last_reset_date != today:
            self.state.sl_streak = 0
            self.state.daily_loss_pct = 0.0
            self.state.last_reset_date = today
            self._log("[StageF] Daily reset", level="INFO")
            self._save()

    def record_trade_close(self, pnl_pct: float):
        self._rollover_if_new_day()
        try:
            pnl_val = float(pnl_pct)
        except Exception:
            pnl_val = 0.0
        if pnl_val < 0:
            self.state.sl_streak += 1
            self.state.daily_loss_pct += abs(pnl_val)
            self._log(
                f"[StageF] Loss: streak={self.state.sl_streak}, daily={self.state.daily_loss_pct:.2f}%",
                level="WARNING",
            )
        else:
            if self.state.sl_streak > 0:
                self._log("[StageF] Profit: reset SL streak", level="INFO")
            self.state.sl_streak = 0
        self._save()

    def can_open_new_position(self) -> tuple[bool, str]:
        if not getattr(self.cfg, "enable_stage_f_guard", True):
            return True, "Stage F disabled"
        self._rollover_if_new_day()
        try:
            max_sl = int(getattr(self.cfg, "max_sl_streak", 3))
            dd_limit = float(getattr(self.cfg, "daily_drawdown_pct", 3.0))
        except Exception:
            max_sl, dd_limit = 3, 3.0
        if self.state.sl_streak >= max_sl:
            return False, f"SL streak {self.state.sl_streak}/{max_sl}"
        if self.state.daily_loss_pct >= dd_limit:
            return False, f"Daily loss {self.state.daily_loss_pct:.2f}%/{dd_limit:.2f}%"
        return True, "OK"

    def status(self) -> dict:
        self._rollover_if_new_day()
        return dict(self.state.__dict__)
