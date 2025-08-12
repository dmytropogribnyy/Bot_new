#!/usr/bin/env python3
"""Move known dev-orphan utilities into tools/ to keep production tree clean.

Safe: only moves files if they exist; never deletes.
"""

from pathlib import Path
from shutil import move

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
TOOLS.mkdir(exist_ok=True)

ORPHANS = [
    "refactor_imports.py",
    "restore_backup.py",
    "safe_compile.py",
    "missed_tracker.py",
    "tp_optimizer.py",
]


def main():
    moved = []
    for rel in ORPHANS:
        src = ROOT / rel
        if src.exists() and src.is_file():
            dest = TOOLS / src.name
            print(f"[MOVE] {src} -> {dest}")
            move(str(src), str(dest))
            moved.append(str(dest))
        else:
            print(f"[SKIP] {src} not found")
    print("\nDone. Moved:", moved)


if __name__ == "__main__":
    main()
