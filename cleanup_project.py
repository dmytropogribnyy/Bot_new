#!/usr/bin/env python3
"""
cleanup_project.py — cross‑platform cleaner for preparing the repo before tests.

Usage examples:
  python cleanup_project.py --dry-run
  python cleanup_project.py --purge-archives --archive-stages --days-logs 10
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# ---- config ----
ARCHIVE_EXTS = {".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".bz2", ".xz"}
BINARY_EXTS = {".exe", ".dll", ".so", ".dylib", ".pyd"}
CACHE_DIRS = {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}
CACHE_FILES = {".pyc", ".pyo"}
TEST_PATTERNS = (re.compile(r"(^|/|\\)test_.*\.py$", re.I), re.compile(r"(^|/|\\).*_test\.py$", re.I))

# Target .gitignore rules to ensure (deduplicated append)
GITIGNORE_RULES = [
    # caches
    "pycache/",
    "*.pyc",
    "*.pyo",
    ".pytest_cache/",
    ".ruff_cache/",
    ".mypy_cache/",
    # archives/backups
    "backup_*/",
    "tests/archive/",
    # logs
    "logs/*.log",
    # IDE
    ".vscode/",
    ".idea/",
    "*.swp",
    "*.swo",
]

DEV_REQUIREMENTS = """\
# Testing
pytest>=8.2.0
pytest-asyncio>=0.23.0
pytest-mock>=3.14.0

# Code quality
ruff>=0.4.0
mypy>=1.10.0
black>=24.4.0
"""


@dataclass
class Plan:
    remove_files: list[Path] = field(default_factory=list)
    remove_dirs: list[Path] = field(default_factory=list)
    move_tests: list[tuple[Path, Path]] = field(default_factory=list)  # (src, dst)
    create_dirs: list[Path] = field(default_factory=list)
    append_gitignore: bool = False
    create_req_dev: bool = False
    space_reclaimed: int = 0


def is_test_file(p: Path) -> bool:
    rel = str(p.as_posix())
    return any(rx.search(rel) for rx in TEST_PATTERNS)


def find_repo_root(start: Path) -> Path:
    # Heuristic: stay where script is executed
    return start.resolve()


SKIP_DIR_NAMES = {
    ".git",
    "archive",
    "venv",
    ".venv",
    "ENV",
    "env",
    "references_archive",
    ".tox",
    "node_modules",
    ".pytest_cache",
}


def should_skip_dir(path_str: str) -> bool:
    parts = path_str.replace("\\", "/").split("/")
    if any(name in parts for name in SKIP_DIR_NAMES):
        return True
    return "site-packages" in parts


def size_of(path: Path) -> int:
    try:
        if path.is_file():
            return path.stat().st_size
        total = 0
        for rp, _, files in os.walk(path):
            for f in files:
                fp = Path(rp) / f
                try:
                    total += fp.stat().st_size
                except Exception:
                    pass
        return total
    except Exception:
        return 0


def plan_cleanup(repo: Path, purge_archives: bool, archive_stages: bool, days_logs: int) -> Plan:
    plan = Plan()
    tests_dir = repo / "tests"
    tests_archive = tests_dir / "archive"

    # 0) ensure basic dirs
    if not tests_dir.exists():
        plan.create_dirs.append(tests_dir)
    if archive_stages and not tests_archive.exists():
        plan.create_dirs.append(tests_archive)

    # 1) python caches & cache files
    for rp, dirs, files in os.walk(repo):
        # skip VCS, venvs, and legacy archives entirely
        if should_skip_dir(rp):
            dirs[:] = []
            continue
        # mark cache dirs
        for d in list(dirs):
            if d in CACHE_DIRS:
                plan.remove_dirs.append(Path(rp) / d)
        # mark cache files
        for f in files:
            p = Path(rp) / f
            if p.suffix in CACHE_FILES:
                plan.remove_files.append(p)

    # 2) tests outside tests/
    for rp, dirs, files in os.walk(repo):
        if should_skip_dir(rp):
            dirs[:] = []
            continue
        for f in files:
            p = Path(rp) / f
            if p.is_file() and p.suffix.lower() == ".py" and is_test_file(p):
                # Is it inside tests/ already?
                try:
                    p.relative_to(tests_dir)
                    inside = True
                except ValueError:
                    inside = False
                if not inside:
                    dst = tests_dir / p.name
                    plan.move_tests.append((p, dst))

    # 3) stage tests -> tests/archive/
    if archive_stages and tests_dir.exists():
        for p in tests_dir.glob("test_stage_*.py"):
            dst = tests_archive / p.name
            if p.resolve() != dst.resolve():
                plan.move_tests.append((p, dst))

    # 4) docs/archive & audits
    docs_archive = repo / "docs" / "Archive"
    audits = [repo / "AUDIT_REPORT.md", repo / "USDC_Audit_Plan.md"]
    if docs_archive.exists():
        if purge_archives:
            for child in docs_archive.rglob("*"):
                if child.is_file():
                    plan.remove_files.append(child)
        else:
            dest = repo / "archive" / "docs_old"
            if not dest.exists():
                plan.create_dirs.append(dest)
            for child in docs_archive.rglob("*"):
                if child.is_file():
                    plan.move_tests.append((child, dest / child.name))  # reusing move list for generic moves

    if not purge_archives:
        dest_aud = repo / "archive" / "audits"
        if any(p.exists() for p in audits) and not dest_aud.exists():
            plan.create_dirs.append(dest_aud)
        for a in audits:
            if a.exists():
                plan.move_tests.append((a, dest_aud / a.name))
    else:
        for a in audits:
            if a.exists():
                plan.remove_files.append(a)

    # 5) logs older than N days
    logs_dir = repo / "logs"
    if logs_dir.exists():
        threshold = time.time() - days_logs * 86400
        for p in logs_dir.rglob("*.log"):
            try:
                if p.stat().st_mtime < threshold:
                    plan.remove_files.append(p)
            except FileNotFoundError:
                pass

    # 6) archives & binaries
    if purge_archives:
        for rp, dirs, files in os.walk(repo):
            if should_skip_dir(rp):
                dirs[:] = []
                continue
            for f in files:
                p = Path(rp) / f
                ext = p.suffix.lower()
                if ext in ARCHIVE_EXTS or ext in BINARY_EXTS:
                    plan.remove_files.append(p)

    # 7) dev requirements presence
    if (repo / "requirements.txt").exists() and not (repo / "requirements-dev.txt").exists():
        plan.create_req_dev = True

    # 8) .gitignore append (idempotent)
    plan.append_gitignore = True

    # de-duplicate entries
    plan.remove_files = sorted(set(plan.remove_files), key=lambda x: x.as_posix())
    plan.remove_dirs = sorted(set(plan.remove_dirs), key=lambda x: x.as_posix())
    # combine move list (may contain generic moves too, not just tests)
    seen_moves = set()
    uniq_moves = []
    for src, dst in plan.move_tests:
        key = (src.resolve(), dst.resolve())
        if key not in seen_moves:
            seen_moves.add(key)
            uniq_moves.append((src, dst))
    plan.move_tests = uniq_moves
    return plan


def ensure_parent(d: Path, dry_run: bool):
    if not d.parent.exists():
        if dry_run:
            print(f"[MKDIR] {d.parent.as_posix()}")
        else:
            d.parent.mkdir(parents=True, exist_ok=True)


def execute(repo: Path, plan: Plan, dry_run: bool):
    reclaimed = 0

    for d in plan.create_dirs:
        if dry_run:
            print(f"[MKDIR] {d.as_posix()}")
        else:
            d.mkdir(parents=True, exist_ok=True)

    for src, dst in plan.move_tests:
        ensure_parent(dst, dry_run)
        if dry_run:
            print(f"[MOVE] {src.as_posix()} -> {dst.as_posix()}")
        else:
            try:
                if src.is_file():
                    if dst.exists():
                        # avoid overwriting: add suffix with timestamp
                        ts = datetime.now().strftime("%Y%m%d%H%M%S")
                        dst = dst.with_name(dst.stem + f"_{ts}" + dst.suffix)
                    shutil.move(str(src), str(dst))
            except Exception as e:
                print(f"[WARN] move failed {src} -> {dst}: {e}", file=sys.stderr)

    for f in plan.remove_files:
        sz = size_of(f)
        if dry_run:
            print(f"[DEL] {f.as_posix()}  ({sz} bytes)")
        else:
            try:
                f.unlink(missing_ok=True)
                reclaimed += sz
            except Exception as e:
                print(f"[WARN] delete failed {f}: {e}", file=sys.stderr)

    for d in plan.remove_dirs:
        sz = size_of(d)
        if dry_run:
            print(f"[RMDIR] {d.as_posix()}  (~{sz} bytes)")
        else:
            try:
                shutil.rmtree(d, ignore_errors=True)
                reclaimed += sz
            except Exception as e:
                print(f"[WARN] rmtree failed {d}: {e}", file=sys.stderr)

    # .gitignore (append only missing rules)
    if plan.append_gitignore:
        gi = repo / ".gitignore"
        try:
            existing = []
            if gi.exists():
                existing = [line.rstrip("\n") for line in gi.read_text(encoding="utf-8").splitlines()]
            existing_set = set(line.strip() for line in existing if line.strip())
            missing_rules = [rule for rule in GITIGNORE_RULES if rule not in existing_set]
            if missing_rules:
                if dry_run:
                    print("[APPEND] .gitignore will add:")
                    for r in missing_rules:
                        print(f"         {r}")
                else:
                    with open(gi, "a", encoding="utf-8") as fh:
                        fh.write("\n")
                        # add grouped with simple headers for readability
                        # caches
                        if any(
                            r in missing_rules
                            for r in ["pycache/", "*.pyc", "*.pyo", ".pytest_cache/", ".ruff_cache/", ".mypy_cache/"]
                        ):
                            fh.write("# Caches\n")
                        for r in ["pycache/", "*.pyc", "*.pyo", ".pytest_cache/", ".ruff_cache/", ".mypy_cache/"]:
                            if r in missing_rules:
                                fh.write(r + "\n")
                        # archives/backups
                        if any(r in missing_rules for r in ["backup_*/", "tests/archive/"]):
                            fh.write("\n# Archives / backups\n")
                        for r in ["backup_*/", "tests/archive/"]:
                            if r in missing_rules:
                                fh.write(r + "\n")
                        # logs
                        if "logs/*.log" in missing_rules:
                            fh.write("\n# Logs\n")
                            fh.write("logs/*.log\n")
                        # IDE
                        if any(r in missing_rules for r in [".vscode/", ".idea/", "*.swp", "*.swo"]):
                            fh.write("\n# IDE\n")
                        for r in [".vscode/", ".idea/", "*.swp", "*.swo"]:
                            if r in missing_rules:
                                fh.write(r + "\n")
        except Exception as e:
            print(f"[WARN] .gitignore update failed: {e}", file=sys.stderr)

    # requirements-dev.txt
    if plan.create_req_dev:
        target = repo / "requirements-dev.txt"
        if dry_run:
            print(f"[CREATE] {target.as_posix()}")
        else:
            try:
                with open(target, "w", encoding="utf-8") as fh:
                    fh.write(DEV_REQUIREMENTS)
            except Exception as e:
                print(f"[WARN] cannot create requirements-dev.txt: {e}", file=sys.stderr)

    plan.space_reclaimed = reclaimed


def human_size(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    v = float(n)
    while v >= 1024 and i < len(units) - 1:
        v /= 1024.0
        i += 1
    return f"{v:.1f} {units[i]}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Clean and organize repository before tests.")
    ap.add_argument("--dry-run", action="store_true", help="print actions only")
    ap.add_argument("--purge-archives", action="store_true", help="delete archives and old docs/audits")
    ap.add_argument("--archive-stages", action="store_true", help="move stage tests to tests/archive/")
    ap.add_argument("--days-logs", type=int, default=7, help="delete logs older than N days (default: 7)")
    args = ap.parse_args(argv)

    repo = find_repo_root(Path.cwd())
    plan = plan_cleanup(
        repo, purge_archives=args.purge_archives, archive_stages=args.archive_stages, days_logs=args.days_logs
    )

    # summary
    print("=== cleanup plan ===")
    print(f"repo: {repo}")
    print(f"create_dirs: {len(plan.create_dirs)}")
    print(f"move files: {len(plan.move_tests)}")
    print(f"remove files: {len(plan.remove_files)}")
    print(f"remove dirs: {len(plan.remove_dirs)}")
    print(f"append .gitignore: {plan.append_gitignore}")
    print(f"create requirements-dev.txt: {plan.create_req_dev}")
    print(f"dry-run: {args.dry_run}")
    print("====================")

    execute(repo, plan, dry_run=args.dry_run)

    print("\n=== summary ===")
    print(f"Moved: {len(plan.move_tests)}")
    print(f"Removed files: {len(plan.remove_files)}")
    print(f"Removed dirs: {len(plan.remove_dirs)}")
    print(f"Reclaimed: {human_size(plan.space_reclaimed)}")
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
