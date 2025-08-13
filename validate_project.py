#!/usr/bin/env python3
"""
validate_project.py — structural & import sanity checks for the repo.
Exit codes:
 0 OK
 1 Error
"""

from __future__ import annotations

import importlib
import os
import re
from pathlib import Path

REQUIRED_FILES = ["main.py", "requirements.txt"]
REQUIRED_DIRS = ["tests"]

FORBIDDEN_IMPORT_PATTERNS = [
    re.compile(r"^\s*from\s+core\.legacy\s+import\s+", re.M),
    re.compile(r"^\s*import\s+core\.legacy\b", re.M),
    re.compile(r"^\s*from\s+archive\b", re.M),
    re.compile(r"^\s*import\s+archive\b", re.M),
]

SEARCH_DIRS = ["core", "strategies", "tools"]

SKIP_DIR_NAMES = {".git", "venv", ".venv", "env", ".tox", "node_modules", ".pytest_cache"}


def should_skip_dir(path_str: str) -> bool:
    parts = path_str.replace("\\", "/").split("/")
    if any(name in parts for name in SKIP_DIR_NAMES):
        return True
    # explicitly ignore any site-packages anywhere in path
    return "site-packages" in parts


def fail(msg: str) -> int:
    print(f"[FAIL] {msg}")
    return 1


def ok(msg: str) -> None:
    print(msg)


def has_env_file(repo: Path) -> bool:
    return (repo / ".env").exists() or (repo / ".env.example").exists()


def tests_outside_tests(repo: Path) -> list[Path]:
    test_rx = re.compile(r"(?:^|/|\\)(?:test_.*\.py|.*_test\.py)$", re.I)
    results: list[Path] = []
    tests_dir = repo / "tests"
    for rp, dirnames, files in os.walk(repo):
        if should_skip_dir(rp):
            dirnames[:] = []
            continue
        for f in files:
            p = Path(rp) / f
            if test_rx.search(p.as_posix()):
                try:
                    p.relative_to(tests_dir)
                except ValueError:
                    results.append(p)
    return results


def scan_forbidden_imports(repo: Path) -> list[Path]:
    offenders: list[Path] = []
    for base in SEARCH_DIRS:
        base_p = repo / base
        if not base_p.exists():
            continue
        for rp, dirnames, files in os.walk(base_p):
            if should_skip_dir(rp):
                dirnames[:] = []
                continue
            for f in files:
                if not f.endswith(".py"):
                    continue
                p = Path(rp) / f
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                for rx in FORBIDDEN_IMPORT_PATTERNS:
                    if rx.search(text):
                        offenders.append(p)
                        break
    return offenders


def import_smoke_tests() -> list[str]:
    mods = ["core.config", "core.exchange_client"]
    errors = []
    for m in mods:
        try:
            importlib.import_module(m)
        except Exception as e:
            errors.append(f"{m}: {e.__class__.__name__}: {e}")
    return errors


def main(argv=None) -> int:
    repo = Path.cwd()
    # 1. required files/dirs
    for f in REQUIRED_FILES:
        if not (repo / f).exists():
            return fail(f"required file missing: {f}")
    for d in REQUIRED_DIRS:
        if not (repo / d).exists():
            return fail(f"required dir missing: {d}")
    if not has_env_file(repo):
        return fail("missing .env or .env.example")

    # 2. tests outside tests/
    stray = tests_outside_tests(repo)
    if stray:
        print("[FAIL] tests outside tests/:")
        for p in stray[:20]:
            print("  -", p.as_posix())
        if len(stray) > 20:
            print(f"  ... and {len(stray) - 20} more")
        return 1

    # 3. forbidden imports
    offenders = scan_forbidden_imports(repo)
    if offenders:
        print("[FAIL] forbidden imports detected:")
        for p in offenders:
            print("  -", p.as_posix())
        return 1

    # 4. smoke imports
    errs = import_smoke_tests()
    if errs:
        print("[FAIL] smoke import errors:")
        for e in errs:
            print("  -", e)
        return 1

    ok("OK: structure, imports, dependencies look sane")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
