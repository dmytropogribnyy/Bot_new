#!/usr/bin/env python3
"""
WS → OMS acceptance tests (Stage E minimal)
Simulate ORDER_TRADE_UPDATE and ACCOUNT_UPDATE events and verify OrderManager updates state.
"""

import pytest


class DummyLogger:
    def __init__(self):
        self.events: list[tuple[str, str, str, object]] = []

    def log_event(self, component: str, level: str, message: str, details=None, channels=None):
        self.events.append((component, level, message, details))


@pytest.mark.asyncio
async def test_order_trade_update_triggers_position_close(order_manager):
    om = order_manager
    # Replace logger with dummy to capture events
    dummy = DummyLogger()
    om.logger = dummy  # type: ignore

    # Ensure pos cache exists and simulate zero position
    if not hasattr(om, "positions"):
        om.positions = {}
    om.positions["BTCUSDT"] = {"contracts": 0.0, "unrealized_pnl": 0.0}

    event = {
        "e": "ORDER_TRADE_UPDATE",
        "E": 1234567890,
        "o": {
            "s": "BTCUSDT",
            "X": "FILLED",
            "ot": "TAKE_PROFIT",
            "x": "TRADE",
            "R": True,  # reduceOnly
            "rp": "2.5",
            "i": 98765,
            "c": "client-abc",
        },
    }

    await om.handle_ws_event(event)

    # Verify state updated (reported exit recorded)
    assert hasattr(om, "_reported_exits")
    assert ("BTCUSDT", 98765) in om._reported_exits  # type: ignore[attr-defined]

    # Verify logging captured the close
    assert any(
        comp == "WS" and level in {"INFO", "WARNING"} and "Position closed" in msg
        for comp, level, msg, _ in dummy.events
    )


@pytest.mark.asyncio
async def test_account_update_updates_position_cache(order_manager):
    om = order_manager
    dummy = DummyLogger()
    om.logger = dummy  # type: ignore

    # Seed with non-zero position to exercise zeroing branch
    if not hasattr(om, "positions"):
        om.positions = {}
    om.positions["BTCUSDT"] = {"contracts": 1.25, "unrealized_pnl": 0.0}

    event = {
        "e": "ACCOUNT_UPDATE",
        "E": 1234567900,
        "a": {
            "B": [],
            "P": [
                {
                    "s": "BTCUSDT",
                    "pa": "0",
                    "ep": "0",
                    "up": "0",
                }
            ],
        },
    }

    await om.handle_ws_event(event)

    # Position should be zeroed in cache
    assert om.positions["BTCUSDT"]["contracts"] == 0.0

    # Verify logging captured zeroed message
    assert any(
        comp == "WS" and level in {"INFO", "WARNING"} and "Position zeroed via ACCOUNT_UPDATE" in msg
        for comp, level, msg, _ in dummy.events
    )
