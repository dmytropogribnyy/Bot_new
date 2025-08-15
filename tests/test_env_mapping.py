import json
import warnings

import pytest

from core.config import TradingConfig


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("ALLOW_SHORTS", "false")
    monkeypatch.setenv("MAX_POSITIONS", "3")
    monkeypatch.setenv("STOP_LOSS_PERCENT", "0.8")
    monkeypatch.setenv(
        "TP_LEVELS",
        json.dumps(
            [
                {"percent": 1.0, "size": 0.5},
                {"percent": 2.0, "size": 0.5},
            ]
        ),
    )
    # Additional fields overrides
    monkeypatch.setenv("BASE_POSITION_SIZE_USDT", "20.0")
    monkeypatch.setenv("MIN_POSITION_SIZE_USDT", "20.0")
    monkeypatch.setenv("ALLOW_AUTO_INCREASE_FOR_MIN", "true")
    monkeypatch.setenv("MAX_AUTO_INCREASE_USDT", "150.0")
    monkeypatch.setenv("MAX_SPREAD_PCT", "5.0")
    monkeypatch.setenv("BALANCE_PERCENTAGE", "0.95")
    monkeypatch.setenv("TRADING_DEPOSIT", "400")
    monkeypatch.setenv("USE_DYNAMIC_BALANCE", "false")
    monkeypatch.setenv("WORKING_TYPE", "MARK_PRICE")

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        cfg = TradingConfig().from_env()
        assert not any("PydanticDeprecatedSince20" in str(item.message) for item in w)

    assert cfg.allow_shorts is False
    assert cfg.max_positions == 3
    assert abs(cfg.stop_loss_percent - 0.8) < 1e-9
    assert isinstance(cfg.tp_levels, list) and len(cfg.tp_levels) == 2
    assert cfg.tp_levels[0]["percent"] == 1.0
    # Extended assertions
    assert abs(cfg.base_position_size_usdt - 20.0) < 1e-9
    assert abs(cfg.min_position_size_usdt - 20.0) < 1e-9
    assert cfg.allow_auto_increase_for_min is True
    assert abs(cfg.max_auto_increase_usdt - 150.0) < 1e-9
    assert abs(cfg.max_spread_pct - 5.0) < 1e-9
    assert abs(cfg.balance_percentage - 0.95) < 1e-9
    assert abs(cfg.trading_deposit - 400.0) < 1e-9
    assert cfg.use_dynamic_balance is False
    assert cfg.working_type == "MARK_PRICE"
