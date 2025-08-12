#!/usr/bin/env python3
"""
Audit logger (P-block P0/P3 core) with:
- Environment-scoped singleton (prod vs testnet)
- UTC timestamps and daily file rotation
- Append-only JSONL with hash-chain integrity
- Basic fsync for safer writes and secret redaction

Notes:
- For multi-process safety you may enable portalocker by setting
  use_file_lock=True when constructing AuditLogger (optional dependency).
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

try:  # Optional for multi-process file lock
    import portalocker  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    portalocker = None  # type: ignore


GENESIS_HASH = "0" * 64


class AuditLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    DECISION = "DECISION"  # P3
    RISK = "RISK"  # P1
    ORDER = "ORDER"  # P2
    CRITICAL = "CRITICAL"
    ERROR = "ERROR"


class AuditLogger:
    """
    Append-only audit logger with hash-chain integrity and daily rotation.

    Files per environment per day:
      - audit_{prod|testnet}_YYYYMMDD.jsonl
      - decisions_{prod|testnet}_YYYYMMDD.jsonl
      - daily_{prod|testnet}_YYYYMMDD.json
    """

    def __init__(
        self,
        audit_dir: str = "data/audit",
        testnet: bool = False,
        use_file_lock: bool = False,
    ) -> None:
        self.testnet = testnet
        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self.use_file_lock = use_file_lock and portalocker is not None

        self._rollover_date = self._today_str()
        self._set_files()

        self.last_hash = self._get_last_hash()
        self.session_id = self._generate_session_id()
        self.event_counter = 0

        # Start of session record
        self._write_event(
            AuditLevel.INFO,
            "SESSION_START",
            {"session_id": self.session_id, "testnet": testnet},
        )

    # --------- Time helpers (UTC) ---------
    # Backward-compatible UTC alias for Python < 3.11
    _UTC = getattr(datetime, "UTC", UTC)

    def _today_str(self) -> str:
        return datetime.now(self._UTC).strftime("%Y%m%d")

    def _now_iso(self) -> str:
        return datetime.now(self._UTC).isoformat()

    # --------- File management / rotation ---------
    def _set_files(self) -> None:
        env = "testnet" if self.testnet else "prod"
        date_str = self._rollover_date
        self.audit_file = self.audit_dir / f"audit_{env}_{date_str}.jsonl"
        self.decision_file = self.audit_dir / f"decisions_{env}_{date_str}.jsonl"
        self.daily_report_file = self.audit_dir / f"daily_{env}_{date_str}.json"

    def _rollover_if_needed(self) -> None:
        current = self._today_str()
        if current != self._rollover_date:
            self._rollover_date = current
            self._set_files()
            # Begin a new chain within a new file/day
            self.last_hash = self._get_last_hash()

    # --------- Integrity / hashing ---------
    def _generate_session_id(self) -> str:
        return hashlib.sha256(self._now_iso().encode()).hexdigest()[:12]

    def _get_last_hash(self) -> str:
        path = self.audit_file
        if not path.exists() or path.stat().st_size == 0:
            return GENESIS_HASH
        try:
            with open(path, "rb") as f:
                # Read last up to 8KB to find last line
                size = path.stat().st_size
                f.seek(-min(8192, size), os.SEEK_END)
                lines = f.read().decode("utf-8", "ignore").strip().split("\n")
                last = json.loads(lines[-1])
                return last.get("hash", GENESIS_HASH)
        except Exception:
            return GENESIS_HASH

    def _compute_hash(self, record_without_hash: dict[str, Any]) -> str:
        content = json.dumps(record_without_hash, sort_keys=True) + self.last_hash
        return hashlib.sha256(content.encode()).hexdigest()

    # --------- Secret redaction ---------
    def _redact(self, data: Any) -> Any:
        sensitive_keys = {
            "api_key",
            "apiKey",
            "api_secret",
            "apiSecret",
            "secret",
            "secretKey",
            "listenKey",
            "password",
            "access_token",
            "refresh_token",
            "token",
        }

        def mask(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {k: ("***" if k in sensitive_keys else mask(v)) for k, v in obj.items()}
            if isinstance(obj, list):
                return [mask(v) for v in obj]
            return obj

        return mask(data)

    # --------- I/O ---------
    def _append_jsonl(self, path: Path, payload: dict[str, Any]) -> None:
        line = json.dumps(payload) + "\n"
        if self.use_file_lock and portalocker is not None:  # pragma: no cover - optional path
            with portalocker.Lock(path, timeout=1) as f:  # type: ignore[attr-defined]
                f.write(line)
                f.flush()
                os.fsync(f.fileno())
            return

        with open(path, "a", buffering=1, encoding="utf-8") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())

    # --------- Core write ---------
    def _write_event(self, level: AuditLevel, event: str, data: Any = None) -> dict[str, Any]:
        self._rollover_if_needed()
        self.event_counter += 1

        record_without_hash: dict[str, Any] = {
            "timestamp": self._now_iso(),
            "session_id": self.session_id,
            "event_id": self.event_counter,
            "level": level.value,
            "event": event,
            "data": self._redact(data),
            "prev_hash": self.last_hash,
        }
        record: dict[str, Any] = dict(record_without_hash)
        record["hash"] = self._compute_hash(record_without_hash)

        self._append_jsonl(self.audit_file, record)
        self.last_hash = record["hash"]
        return record

    # --------- Public API ---------
    def log_event(self, event: str, data: Any = None, level: AuditLevel = AuditLevel.INFO) -> dict[str, Any]:
        return self._write_event(level, event, data)

    # P1: Risk events
    def log_risk_event(self, event: str, data: dict[str, Any]) -> dict[str, Any]:
        return self._write_event(AuditLevel.RISK, f"RISK_{event}", data)

    def log_sl_streak(self, streak: int, symbols: list[str], action: str) -> dict[str, Any]:
        return self.log_risk_event(
            "SL_STREAK",
            {
                "streak": streak,
                "symbols": symbols,
                "action": action,
                "timestamp": self._now_iso(),
            },
        )

    def log_daily_limit(self, loss: float, limit: float, action: str) -> dict[str, Any]:
        return self.log_risk_event(
            "DAILY_LIMIT",
            {"daily_loss": loss, "limit": limit, "action": action, "timestamp": self._now_iso()},
        )

    # P2: Order events
    def log_order_event(
        self, event: str, order: dict[str, Any], metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        data: dict[str, Any] = {
            "order_id": order.get("id"),
            "symbol": order.get("symbol"),
            "side": order.get("side"),
            "type": order.get("type"),
            "price": order.get("price"),
            "amount": order.get("amount"),
            "status": order.get("status"),
        }
        if metadata:
            data["metadata"] = metadata
        return self._write_event(AuditLevel.ORDER, f"ORDER_{event}", data)

    def log_order_placed(self, order: dict[str, Any], reason: str | None = None) -> dict[str, Any]:
        return self.log_order_event("PLACED", order, {"reason": reason} if reason else None)

    def log_order_filled(
        self, order: dict[str, Any], fill_price: float | None = None, slippage: float | None = None
    ) -> dict[str, Any]:
        return self.log_order_event("FILLED", order, {"fill_price": fill_price, "slippage": slippage})

    def log_order_cancelled(self, order: dict[str, Any], reason: str | None = None) -> dict[str, Any]:
        return self.log_order_event("CANCELLED", order, {"reason": reason} if reason else None)

    # P3: Decision records
    def record_entry_decision(
        self,
        symbol: str,
        side: str,
        signals: dict[str, Any],
        risk_check: dict[str, Any],
        position_size: float,
        rationale: str,
    ) -> dict[str, Any]:
        decision = {
            "type": "ENTRY",
            "symbol": symbol,
            "side": side,
            "signals": self._redact(signals),
            "risk_check": risk_check,
            "position_size": position_size,
            "rationale": rationale,
            "timestamp": self._now_iso(),
        }
        self._write_event(AuditLevel.DECISION, "ENTRY_DECISION", decision)
        self._append_jsonl(self.decision_file, decision)
        return decision

    def record_exit_decision(
        self,
        symbol: str,
        reason: str,
        pnl: float,
        exit_signals: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        decision = {
            "type": "EXIT",
            "symbol": symbol,
            "reason": reason,
            "pnl": pnl,
            "exit_signals": self._redact(exit_signals) if exit_signals else None,
            "metadata": metadata,
            "timestamp": self._now_iso(),
        }
        self._write_event(AuditLevel.DECISION, "EXIT_DECISION", decision)
        self._append_jsonl(self.decision_file, decision)
        return decision

    def record_skip_decision(self, symbol: str, reason: str, signals: dict[str, Any] | None = None) -> dict[str, Any]:
        decision = {
            "type": "SKIP",
            "symbol": symbol,
            "reason": reason,
            "signals": self._redact(signals) if signals else None,
            "timestamp": self._now_iso(),
        }
        self._write_event(AuditLevel.DECISION, "SKIP_DECISION", decision)
        return decision

    # P4: Daily report
    def generate_daily_report(self, stats: dict[str, Any]) -> dict[str, Any]:
        report = {
            "date": datetime.now(self._UTC).strftime("%Y-%m-%d"),
            "generated_at": self._now_iso(),
            "session_id": self.session_id,
            "statistics": stats,
            "events_logged": self.event_counter,
            "audit_hash": self.last_hash,
        }
        # Write report as JSON
        with open(self.daily_report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        self._write_event(AuditLevel.INFO, "DAILY_REPORT_GENERATED", {"report_file": str(self.daily_report_file)})
        return report

    # Utilities
    def verify_integrity(self) -> tuple[bool, list[str]]:
        """Verify hash-chain integrity for the current audit file."""
        if not self.audit_file.exists():
            return True, []

        errors: list[str] = []
        prev = GENESIS_HASH
        try:
            with open(self.audit_file, encoding="utf-8") as f:
                for idx, line in enumerate(f, start=1):
                    record = json.loads(line.strip())
                    if record.get("prev_hash") != prev:
                        errors.append(f"Line {idx}: Previous hash mismatch")
                    stored_hash = record.get("hash", "")
                    copy = {k: v for k, v in record.items() if k not in {"hash"}}
                    expected = hashlib.sha256((json.dumps(copy, sort_keys=True) + prev).encode()).hexdigest()
                    if stored_hash != expected:
                        errors.append(f"Line {idx}: Hash verification failed")
                    prev = stored_hash or prev
        except Exception as e:  # pragma: no cover - unexpected I/O issue
            errors.append(f"Verification error: {e}")

        return len(errors) == 0, errors

    def get_session_summary(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "events_logged": self.event_counter,
            "audit_file": str(self.audit_file),
            "decision_file": str(self.decision_file),
            "last_hash": self.last_hash,
        }


# Environment-scoped singleton storage
_audit_loggers: dict[bool, AuditLogger] = {}


def get_audit_logger(testnet: bool = False) -> AuditLogger:
    """
    Return a singleton AuditLogger instance per environment.
    - testnet=True -> separate instance and files
    - testnet=False -> production instance
    """
    if testnet not in _audit_loggers:
        _audit_loggers[testnet] = AuditLogger(testnet=testnet)
    return _audit_loggers[testnet]
