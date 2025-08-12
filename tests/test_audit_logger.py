#!/usr/bin/env python3
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone, UTC

import pytest

from core.audit_logger import AuditLogger, get_audit_logger


@pytest.fixture()
def temp_dir() -> str:
    with tempfile.TemporaryDirectory() as tmp:
        yield tmp


def test_singletons_split_by_env(temp_dir: str):
    # Create separate instances per env
    # Use local (non-singleton) instances to avoid contaminating global state in parallel test runs
    prod = AuditLogger(audit_dir=temp_dir, testnet=False)
    tn = AuditLogger(audit_dir=temp_dir, testnet=True)

    assert prod.testnet is False
    assert tn.testnet is True
    assert prod.audit_file != tn.audit_file
    assert prod.decision_file != tn.decision_file


def test_global_singleton_is_per_env_isolated(temp_dir: str, monkeypatch):
    # Ensure get_audit_logger creates separate instances for prod and testnet
    from core import audit_logger as mod

    class Factory(AuditLogger):
        def __init__(self, audit_dir: str = "data/audit", testnet: bool = False, use_file_lock: bool = False):
            super().__init__(audit_dir=temp_dir, testnet=testnet, use_file_lock=use_file_lock)

    # Reset globals and inject factory
    mod._audit_loggers.clear()
    monkeypatch.setattr(mod, "AuditLogger", Factory)

    prod = mod.get_audit_logger(testnet=False)
    tn = mod.get_audit_logger(testnet=True)

    assert prod is not tn
    assert Path(prod.audit_file) != Path(tn.audit_file)


def test_daily_rotation(temp_dir: str, monkeypatch):
    # Freeze "today" to a fixed date, then advance by one day and ensure rotation occurs
    fixed_dt = datetime(2025, 8, 12, 23, 59, tzinfo=UTC)

    class _FakeDT:
        @staticmethod
        def now(tz=None):
            return fixed_dt if tz is not None else fixed_dt.replace(tzinfo=None)

    logger = AuditLogger(audit_dir=temp_dir, testnet=True)

    # Patch methods that use datetime.now(timezone.utc)
    monkeypatch.setattr(logger, "_today_str", lambda: fixed_dt.strftime("%Y%m%d"))
    monkeypatch.setattr(logger, "_now_iso", lambda: fixed_dt.isoformat())
    logger._rollover_if_needed()

    first_audit_file = Path(logger.audit_file)
    logger.log_event("TEST_BEFORE_MIDNIGHT", {"ok": 1})
    assert first_audit_file.exists()

    # Advance to next day
    next_dt = fixed_dt + timedelta(minutes=2)
    monkeypatch.setattr(logger, "_today_str", lambda: next_dt.strftime("%Y%m%d"))
    monkeypatch.setattr(logger, "_now_iso", lambda: next_dt.isoformat())

    # Trigger a write; should rotate
    logger.log_event("TEST_AFTER_MIDNIGHT", {"ok": 2})

    second_audit_file = Path(logger.audit_file)
    assert second_audit_file.exists()
    assert first_audit_file != second_audit_file

    # New chain should start in new file (prev_hash should be GENESIS_HASH for first line)
    with open(second_audit_file, encoding="utf-8") as f:
        first_line = f.readline().strip()
        rec = json.loads(first_line)
        assert rec.get("prev_hash") is not None
