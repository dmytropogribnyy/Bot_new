#!/usr/bin/env python3
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from core.config import TradingConfig
from core.unified_logger import UnifiedLogger

# Single global logger adapter for legacy calls
_CFG = TradingConfig()
_ULOG = UnifiedLogger(_CFG)

_LEVELS = {"DEBUG": "DEBUG", "INFO": "INFO", "WARNING": "WARNING", "ERROR": "ERROR"}


def _map_level(level: str, important: bool) -> str:
    lvl = (level or "INFO").upper()
    if important and lvl == "INFO":
        return "WARNING"
    return _LEVELS.get(lvl, "INFO")


def log(message: str, important: bool = False, level: str = "INFO") -> None:
    try:
        lvl = _map_level(level, important)
        _ULOG.log_event("UTIL", lvl, str(message))
    except Exception:
        try:
            print(f"[{level}] {message}")
        except Exception:
            pass


def get_recent_logs(n: int = 50) -> str:
    log_file = Path("logs/main.log")
    try:
        if not log_file.exists():
            log(f"Log file {log_file} not found.", level="WARNING")
            return "Log file not found."
        with log_file.open(encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        return "".join(lines[-n:])
    except Exception as e:
        log(f"Failed to read logs: {e}", level="ERROR")
        return ""


def now() -> datetime:
    return datetime.now(timezone.utc)


def backup_config(source_file: str = "data/runtime_config.json") -> Optional[str]:
    try:
        src = Path(source_file)
        if not src.exists():
            log(f"Config file not found: {source_file}", level="WARNING")
            return None
        backup_dir = Path("data/backups")
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M")
        backup_file = backup_dir / f"runtime_config_{timestamp}.json"
        shutil.copy(str(src), str(backup_file))
        log(f"Backed up config to {backup_file}", level="INFO")
        return str(backup_file)
    except Exception as e:
        log(f"Error backing up config: {e}", level="ERROR")
        return None


def restore_config(backup_file: Optional[str] = None, target_file: str = "data/runtime_config.json") -> bool:
    try:
        backup_dir = Path("data/backups")
        if not backup_dir.exists():
            log("No config backups found.", level="WARNING")
            return False
        if not backup_file:
            backups = sorted(backup_dir.glob("runtime_config_*.json"), reverse=True)
            if not backups:
                log("No config backups found.", level="WARNING")
                return False
            chosen = backups[0]
        else:
            chosen = backup_dir / backup_file if not os.path.isabs(backup_file) else Path(backup_file)
        shutil.copy(str(chosen), target_file)
        log(f"Restored config from {chosen}", level="INFO")
        # keep only latest 5 backups
        backups = sorted(backup_dir.glob("runtime_config_*.json"), reverse=True)
        for old in backups[5:]:
            try:
                old.unlink()
            except Exception:
                pass
        return True
    except Exception as e:
        log(f"Error restoring config: {e}", level="ERROR")
        return False


def notify_ip_change(old_ip: str, new_ip: str, timestamp: str, forced_stop: bool = False) -> None:
    try:
        note = f"IP changed: {old_ip} -> {new_ip} at {timestamp}" + ("; forced stop" if forced_stop else "")
        log(note, level="WARNING")
    except Exception:
        pass


def add_log_separator() -> None:
    try:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")
        sep = "=" * 80
        log(f"\n{sep}\n NEW BOT RUN - {ts}\n{sep}\n", level="INFO")
    except Exception:
        pass
