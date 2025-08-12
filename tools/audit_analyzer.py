#!/usr/bin/env python3
"""
Audit Analyzer - simple utility to load and analyze audit logs
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path


class AuditAnalyzer:
    def __init__(self, audit_dir: str = "data/audit") -> None:
        self.audit_dir = Path(audit_dir)
        self.decisions: list[dict] = []
        self.events: list[dict] = []
        self.orders: list[dict] = []
        self.risks: list[dict] = []

    def load_latest_audit(self, env: str = "prod", date: str | None = None) -> bool:
        if date is None:
            date = datetime.now().strftime("%Y%m%d")
        audit_file = self.audit_dir / f"audit_{env}_{date}.jsonl"
        decision_file = self.audit_dir / f"decisions_{env}_{date}.jsonl"

        if not audit_file.exists():
            print(f"❌ Audit file not found: {audit_file}")
            return False

        with open(audit_file, encoding="utf-8") as f:
            for line in f:
                record = json.loads(line.strip())
                self.events.append(record)
                level = record.get("level")
                if level == "ORDER":
                    self.orders.append(record)
                elif level == "RISK":
                    self.risks.append(record)
                elif level == "DECISION":
                    self.decisions.append(record)

        if decision_file.exists():
            with open(decision_file, encoding="utf-8") as f:
                for line in f:
                    self.decisions.append(json.loads(line.strip()))

        print(f"✅ Loaded {len(self.events)} events from {audit_file.name}")
        return True

    def verify_integrity(self) -> bool:
        if not self.events:
            print("❌ No events loaded")
            return False
        import hashlib

        prev = "0" * 64
        errors: list[str] = []
        for idx, record in enumerate(self.events):
            if record.get("prev_hash") != prev:
                errors.append(f"Event {idx + 1}: Previous hash mismatch")
            copy = {k: v for k, v in record.items() if k not in {"hash"}}
            expected = hashlib.sha256((json.dumps(copy, sort_keys=True) + prev).encode()).hexdigest()
            if record.get("hash") != expected:
                errors.append(f"Event {idx + 1}: Hash verification failed")
            prev = record.get("hash", prev)

        if errors:
            print("❌ Integrity check failed:")
            for e in errors[:5]:
                print("  -", e)
            return False

        print("✅ Integrity check passed - audit log is tamper-free")
        return True

    def analyze_decisions(self) -> None:
        if not self.decisions:
            print("No decisions found")
            return
        entry = [d for d in self.decisions if d.get("type") == "ENTRY" or "ENTRY" in d.get("event", "")]
        exit_ = [d for d in self.decisions if d.get("type") == "EXIT" or "EXIT" in d.get("event", "")]
        skip = [d for d in self.decisions if d.get("type") == "SKIP" or "SKIP" in d.get("event", "")]

        print("\n📊 DECISION ANALYSIS")
        print("=" * 60)
        print(f"Total Decisions: {len(self.decisions)}")
        print(f"├── Entry Decisions: {len(entry)}")
        print(f"├── Exit Decisions: {len(exit_)}")
        print(f"└── Skip Decisions: {len(skip)}")

    def analyze_risk_events(self) -> None:
        if not self.risks:
            print("\n✅ No risk events triggered")
            return
        print("\n⚠️ RISK EVENTS")
        print("=" * 60)
        by_type: dict[str, list[dict]] = defaultdict(list)
        for ev in self.risks:
            by_type[ev.get("event", "").replace("RISK_", "")].append(ev)
        for rtype, events in by_type.items():
            print(f"\n{rtype}: {len(events)} events")
            if events:
                last = events[-1]
                print(f"  Last occurrence: {last.get('timestamp')}")

    def analyze_orders(self) -> None:
        if not self.orders:
            print("\n📋 No orders found")
            return
        print("\n📋 ORDER ANALYSIS")
        print("=" * 60)
        by_type: dict[str, list[dict]] = defaultdict(list)
        for ev in self.orders:
            by_type[ev.get("event", "").replace("ORDER_", "")].append(ev)
        placed = len(by_type.get("PLACED", []))
        filled = len(by_type.get("FILLED", []))
        cancelled = len(by_type.get("CANCELLED", []))
        print(f"Total Orders: {len(self.orders)}")
        print(f"├── Placed: {placed}")
        print(f"├── Filled: {filled}")
        print(f"└── Cancelled: {cancelled}")

    def generate_timeline(self, last_hours: int = 24) -> None:
        if not self.events:
            print("No events to display")
            return
        print(f"\n📅 EVENT TIMELINE (Last {last_hours} hours)")
        print("=" * 60)
        cutoff = datetime.now() - timedelta(hours=last_hours)
        recent: list[dict] = []
        for ev in self.events:
            ts = ev.get("timestamp")
            if not ts:
                continue
            try:
                dt = datetime.fromisoformat(ts)
            except Exception:
                continue
            if dt > cutoff:
                recent.append(ev)
        if not recent:
            print("No events in timeframe")
            return
        hourly: dict[str, list[dict]] = defaultdict(list)
        for ev in recent:
            dt = datetime.fromisoformat(ev["timestamp"])  # type: ignore[arg-type]
            key = dt.strftime("%Y-%m-%d %H:00")
            hourly[key].append(ev)
        for hour, events in sorted(hourly.items()):
            print(f"\n{hour} ({len(events)} events)")


def _main() -> int:
    parser = argparse.ArgumentParser(description="Analyze audit logs")
    parser.add_argument("--env", choices=["prod", "testnet"], default="prod")
    parser.add_argument("--date", help="YYYYMMDD date", default=None)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--timeline", type=int, default=24)
    args = parser.parse_args()

    analyzer = AuditAnalyzer()
    if not analyzer.load_latest_audit(env=args.env, date=args.date):
        return 1
    if args.verify:
        analyzer.verify_integrity()
    analyzer.analyze_decisions()
    analyzer.analyze_risk_events()
    analyzer.analyze_orders()
    analyzer.generate_timeline(last_hours=args.timeline)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
