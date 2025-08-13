#!/usr/bin/env python3
r"""
Preflight checks for BinanceBot repo (v2.3).

Run:
    python tools/preflight_check.py

Exit codes:
    0 -> PASS
    1 -> FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# ---- Tunables ---------------------------------------------------------------
VERSION_STR = "2.3.0"
MAJOR_MINOR = VERSION_STR.rsplit(".", 1)[0]  # "2.3"
BANNER_RE = r"Starting\s+BinanceBot\s+v"  # generic banner presence
WS_URL_NEEDLES = ("stream.binancefuture.com", "fstream.binance.com", "dstream.binance.com")
ABSENT_ROOT_FILES = ("tp_optimizer.py", "pair_selector.py", "tp_logger.py")
EXCLUDE_DIRS = {
    ".git",
    ".github",
    ".venv",
    "venv",
    "__pycache__",
    "archive",
    "test-output",
    "docs",
    "tools",
    "dist",
    "build",
    "data",  # exclude backups and runtime artifacts
}
RUNTIME_EXCLUDE = EXCLUDE_DIRS | {"tests"}  # exclude tests for runtime-only checks


# ---- Utils ------------------------------------------------------------------
def rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT)).replace("\\", "/")
    except Exception:
        return str(p)


def read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def py_files(exclude_dirs: set[str]) -> list[Path]:
    out = []
    for p in ROOT.rglob("*.py"):
        rp = rel(p)
        parts = set(rp.split("/"))
        if parts & exclude_dirs:
            continue
        out.append(p)
    return out


def ok(msg: str) -> bool:
    print(f"✅ {msg}")
    return True


def fail(msg: str) -> bool:
    print(f"❌ {msg}")
    return False


def warn(msg: str) -> None:
    print(f"⚠️  {msg}")


# ---- Checks -----------------------------------------------------------------
def check_absent_root_files() -> bool:
    all_absent = True
    for name in ABSENT_ROOT_FILES:
        p = ROOT / name
        if p.exists():
            all_absent = False
            print(f"❌ Found leftover file in repo root: {name}")
    if all_absent:
        print("✅ No orphan root files present:", ", ".join(ABSENT_ROOT_FILES))
    return all_absent


def check_no_legacy_dir() -> bool:
    p = ROOT / "core" / "legacy"
    if p.exists():
        return fail("core/legacy/ still exists — remove it before deploy")
    return ok("core/legacy/ removed")


def check_no_legacy_imports() -> bool:
    offenders = []
    for f in py_files(RUNTIME_EXCLUDE):
        t = read_text(f)
        if re.search(r"\bfrom\s+core\.legacy\b|\bimport\s+core\.legacy\b", t):
            offenders.append(rel(f))
    if offenders:
        return fail("Runtime imports from core.legacy detected:\n  - " + "\n  - ".join(offenders[:20]))
    return ok("No runtime imports from core.legacy")


def check_version_and_banner() -> bool:
    main_candidates = [ROOT / "main.py"] + list(ROOT.glob("**/main.py"))
    main_candidates = [p for p in main_candidates if p.exists()]
    ver_ok = False
    banner_present = False
    banner_version_ok = False

    # Accept either exact v2.3.0 or shortened v2.3 (but NOT v2.3.X)
    exact_pat = rf"Starting\s+BinanceBot\s+v{re.escape(VERSION_STR)}"
    short_pat = rf"Starting\s+BinanceBot\s+v{re.escape(MAJOR_MINOR)}(?!\.\d)"

    for p in main_candidates:
        t = read_text(p)
        if re.search(rf'__version__\s*=\s*["\']{re.escape(VERSION_STR)}["\']', t):
            ver_ok = True
        if re.search(BANNER_RE, t):
            banner_present = True
        # Accept either exact hardcoded version, short major.minor, or dynamic formatting using v%s
        dynamic_fmt = re.search(r"Starting\s+BinanceBot\s+v%s", t)
        if re.search(exact_pat, t) or re.search(short_pat, t) or (dynamic_fmt and ver_ok):
            banner_version_ok = True

    res = True
    res &= (
        ok(f"__version__ = '{VERSION_STR}' present in main.py")
        if ver_ok
        else fail(f"Missing __version__ = '{VERSION_STR}' in main.py")
    )
    if not banner_present:
        res &= fail("Startup banner 'Starting BinanceBot v...' not found in main.py")
    else:
        res &= ok("Startup banner present")
        res &= (
            ok(f"Startup banner shows v{MAJOR_MINOR} / {VERSION_STR}")
            if banner_version_ok
            else fail(f"Startup banner does not show v{MAJOR_MINOR} or {VERSION_STR}")
        )
    return res


def check_ws_flag_and_urls() -> bool:
    cfg = ROOT / "core" / "config.py"
    flag_ok = False
    if cfg.exists():
        t = read_text(cfg)
        flag_ok = ("ENABLE_WEBSOCKET" in t) and bool(re.search(r"enable_websocket", t))
    else:
        print("❌ core/config.py not found")
    urls_ok = False
    for candidate in [ROOT / "core" / "ws_client.py", ROOT / "main.py"]:
        if candidate.exists():
            t = read_text(candidate)
            if all(u in t for u in WS_URL_NEEDLES):
                urls_ok = True
    res = True
    res &= (
        ok("ENABLE_WEBSOCKET supported (TradingConfig/from_env)")
        if flag_ok
        else fail("ENABLE_WEBSOCKET missing in core/config.py")
    )
    res &= ok("Dynamic WS URLs present (testnet/fstream/dstream)") if urls_ok else fail("Dynamic WS URLs not all found")
    return res


def check_no_bare_except() -> bool:
    offenders = []
    pat = re.compile(r"(^|\n)\s*except\s*:\s*", re.MULTILINE)
    for f in py_files(RUNTIME_EXCLUDE):
        t = read_text(f)
        if pat.search(t):
            offenders.append(rel(f))
    if offenders:
        return fail("Bare 'except:' in runtime:\n  - " + "\n  - ".join(offenders[:20]))
    return ok("No bare 'except:' in runtime")


def fyi_sleep_stats() -> None:
    total = 0
    files = 0
    for f in py_files(RUNTIME_EXCLUDE):
        c = read_text(f).count("time.sleep(")
        if c:
            total += c
            files += 1
    if total:
        warn(f"time.sleep occurrences: total={total}, files={files} (consider asyncio.sleep in async paths)")
    else:
        print("ℹ️ time.sleep occurrences: none")


# ---- Main -------------------------------------------------------------------
def main() -> int:
    print(f"== BinanceBot Preflight (root: {ROOT}) ==")
    passed = True
    passed &= check_absent_root_files()
    passed &= check_no_legacy_dir()
    passed &= check_no_legacy_imports()
    passed &= check_version_and_banner()
    passed &= check_ws_flag_and_urls()
    passed &= check_no_bare_except()
    fyi_sleep_stats()
    print("\nResult:", "PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
