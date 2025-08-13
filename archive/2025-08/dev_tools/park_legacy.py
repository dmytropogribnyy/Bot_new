#!/usr/bin/env python3
"""
Park legacy V1 modules under core/legacy and retarget imports.

Steps:
- Replace imports 'from core.<m>' / 'import core.<m>' to 'core.legacy.<m>' for known legacy modules
- git mv core/<m>.py -> core/legacy/<m>.py (if file exists)
- Update .gitignore and remove tracked runtime artifacts from git index
- Create commits

Usage:
  python scripts/park_legacy.py

Idempotent: safe to re-run.
"""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Iterable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LEGACY_MODULES = [
    "trade_engine",
    "binance_api",
    "exchange_init",
    "position_manager",
    "order_utils",
    "engine_controller",
    "priority_evaluator",
    "risk_adjuster",
    "risk_utils",
    "fail_stats_tracker",
    "failure_logger",
    "entry_logger",
    "component_tracker",
    "signal_utils",
    "scalping_mode",
    "tp_sl_logger",
    "missed_signal_logger",
    "notifier",
    "balance_watcher",
    "runtime_state",
    "runtime_stats",
    "strategy",
    "symbol_processor",
    "tp_utils",
]

EXCLUDE_DIRS = {
    ".git",
    "venv",
    "__pycache__",
    "test-output",
    "core/legacy",
}

IMPORT_FROM_RE = re.compile(r"(^|\b)from\s+core\.(?P<mod>[a-zA-Z_][\w]*)\b")
IMPORT_PLAIN_RE = re.compile(r"(^|\b)import\s+core\.(?P<mod>[a-zA-Z_][\w]*)\b")


def iter_python_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        # Normalize slashes and check exclude
        norm = rel_dir.replace("\\", "/")
        if any(norm == ex or norm.startswith(ex + "/") for ex in EXCLUDE_DIRS):
            # Prune traversal into excluded dirs
            dirnames[:] = []
            continue
        for name in filenames:
            if name.endswith(".py"):
                yield Path(dirpath) / name


def retarget_imports() -> int:
    changed = 0
    for file_path in iter_python_files(REPO_ROOT):
        try:
            text = file_path.read_text(encoding="utf-8")
        except Exception:
            continue

        original = text

        def repl_from(m: re.Match) -> str:
            mod = m.group("mod")
            if mod in LEGACY_MODULES:
                return f"from core.legacy.{mod}"
            return m.group(0)

        def repl_plain(m: re.Match) -> str:
            mod = m.group("mod")
            if mod in LEGACY_MODULES:
                return f"import core.legacy.{mod}"
            return m.group(0)

        text = IMPORT_FROM_RE.sub(repl_from, text)
        text = IMPORT_PLAIN_RE.sub(repl_plain, text)

        if text != original:
            file_path.write_text(text, encoding="utf-8")
            changed += 1
            print(f"Updated imports: {file_path.relative_to(REPO_ROOT)}")
    return changed


def ensure_legacy_dir() -> None:
    (REPO_ROOT / "core/legacy").mkdir(parents=True, exist_ok=True)


def git_mv_legacy_modules() -> list[str]:
    moved: list[str] = []
    ensure_legacy_dir()
    for mod in LEGACY_MODULES:
        src = REPO_ROOT / f"core/{mod}.py"
        if src.exists():
            dst = REPO_ROOT / f"core/legacy/{mod}.py"
            # Skip if already moved
            if dst.exists():
                continue
            try:
                subprocess.run(["git", "mv", str(src), str(dst)], check=True)
                moved.append(mod)
                print(f"git mv: core/{mod}.py -> core/legacy/{mod}.py")
            except subprocess.CalledProcessError:
                # Fallback: os.rename then git add
                try:
                    os.replace(src, dst)
                    subprocess.run(["git", "add", str(dst)], check=False)
                    subprocess.run(["git", "rm", "--cached", str(src)], check=False)
                    moved.append(mod)
                    print(f"moved (fallback): core/{mod}.py -> core/legacy/{mod}.py")
                except Exception as e:
                    print(f"Failed to move core/{mod}.py: {e}")
    return moved


def update_gitignore_lines(lines: list[str]) -> bool:
    gi = REPO_ROOT / ".gitignore"
    existing = set()
    if gi.exists():
        try:
            existing = set(l.strip() for l in gi.read_text(encoding="utf-8").splitlines())
        except Exception:
            pass
    changed = False
    for ln in lines:
        if ln not in existing:
            existing.add(ln)
            changed = True
    if changed:
        # Preserve order: original + new lines appended
        orig_lines = []
        if gi.exists():
            try:
                orig_lines = gi.read_text(encoding="utf-8").splitlines()
            except Exception:
                pass
        # Append any missing
        for ln in lines:
            if ln not in orig_lines:
                orig_lines.append(ln)
        gi.write_text("\n".join(orig_lines) + "\n", encoding="utf-8")
        print("Updated .gitignore")
    return changed


def git_commit(message: str) -> None:
    subprocess.run(["git", "add", "-A"], check=False)
    subprocess.run(["git", "commit", "-m", message], check=False)


def clean_runtime_from_index() -> None:
    # Best-effort; ignore errors
    cmds = [
        ["git", "rm", "--cached", "-r", "logs"],
        ["git", "rm", "--cached", ".env"],
        ["git", "rm", "--cached", ".env.env.backup"],
        ["git", "rm", "--cached", "data/*.json"],
        ["git", "rm", "--cached", "runtime/*.json"],
        ["git", "rm", "--cached", "data/backup/*"],
    ]
    for cmd in cmds:
        subprocess.run(cmd, check=False, shell=False)


def main() -> int:
    print("🔎 Retargeting imports to core.legacy …")
    changed = retarget_imports()
    if changed:
        git_commit("refactor(legacy): retarget imports to core.legacy for V1 modules")
    else:
        print("No import updates needed")

    print("📦 Moving legacy modules to core/legacy …")
    moved = git_mv_legacy_modules()
    if moved:
        # Ensure legacy dir is ignored (optional)
        gi_changed = update_gitignore_lines(["core/legacy/"])
        if gi_changed:
            subprocess.run(["git", "add", ".gitignore"], check=False)
        git_commit("chore(legacy): park unused v1 modules under core/legacy")
    else:
        print("No legacy modules moved (already parked or missing)")

    print("🧹 Repo hygiene …")
    gi_changed = update_gitignore_lines(
        [
            "logs/",
            ".env",
            "data/*.json",
            "runtime/*.json",
        ]
    )
    if gi_changed:
        subprocess.run(["git", "add", ".gitignore"], check=False)
    clean_runtime_from_index()
    git_commit("chore(repo): remove runtime artifacts and secrets from VCS")

    print("✅ Stage A complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
