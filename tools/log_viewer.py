#!/usr/bin/env python3
"""
Simple log viewer for BinanceBot logs.

Features:
- Tail readable log `logs/main.log`
- Show JSONL analytics `logs/main.jsonl`
- Grep filter
- Follow mode
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Iterable
from pathlib import Path


def tail_file(path: Path, follow: bool = False) -> Iterable[str]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8", errors="replace") as f:
        if follow:
            f.seek(0, os.SEEK_END)
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.2)
                    continue
                yield line
        else:
            for line in f:
                yield line


def main() -> int:
    parser = argparse.ArgumentParser(description="View BinanceBot logs")
    parser.add_argument("--json", action="store_true", help="Show JSONL analytics (main.jsonl)")
    parser.add_argument("--follow", "-f", action="store_true", help="Follow output like tail -f")
    parser.add_argument("--grep", type=str, default="", help="Filter lines containing pattern")
    parser.add_argument("--dir", type=str, default="logs", help="Logs directory")
    args = parser.parse_args()

    log_dir = Path(args.dir)
    path = log_dir / ("main.jsonl" if args.json else "main.log")

    if not path.exists():
        print(f"No log file found at: {path}")
        return 1

    pattern = args.grep.lower()
    try:
        for line in tail_file(path, follow=args.follow) or []:
            if pattern and pattern not in line.lower():
                continue
            if args.json:
                try:
                    obj = json.loads(line)
                    ts = obj.get("ts", "")
                    lvl = obj.get("level", "")
                    tag = obj.get("tag", "")
                    msg = obj.get("msg", "")
                    print(f"{ts} | {lvl:<7} | [{tag:<10}] {msg}")
                except Exception:
                    print(line.rstrip())
            else:
                print(line.rstrip())
    except KeyboardInterrupt:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
