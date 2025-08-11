#!/usr/bin/env python3
import gzip
import hashlib
import json
import logging
import re
import shutil
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from core.config import env_bool, env_str

# Optional deps
try:
    from rich.console import Console  # type: ignore[import-not-found]
    from rich.logging import RichHandler  # type: ignore[import-not-found]

    RICH_AVAILABLE = True
except Exception:
    RICH_AVAILABLE = False

try:
    from colorama import Back, Fore, Style, init as colorama_init

    colorama_init(autoreset=True)
    COLORAMA_AVAILABLE = True
except Exception:
    COLORAMA_AVAILABLE = False


# ============= Filters =============
class DuplicateFilter(logging.Filter):
    def __init__(self, window_secs: int = 60):
        super().__init__()
        self.window_secs = window_secs
        self.cache: dict[str, tuple[int, float]] = {}

    def filter(self, record: logging.LogRecord) -> bool:
        msg_hash = hashlib.md5(record.getMessage().encode()).hexdigest()
        current_time = time.time()
        self.cache = {k: v for k, v in self.cache.items() if current_time - v[1] < self.window_secs}
        if msg_hash in self.cache:
            count, first_time = self.cache[msg_hash]
            self.cache[msg_hash] = (count + 1, first_time)
            if count % 10 == 0:
                record.msg = f"{record.msg} [repeated {count}x in {self.window_secs}s]"
                return True
            return False
        self.cache[msg_hash] = (1, current_time)
        return True


class RateLimitFilter(logging.Filter):
    def __init__(self, keys: list[str] | None = None, window_secs: int = 60):
        super().__init__()
        self.keys = keys or [
            "Telegram bot initialized",
            "Emergency shutdown flag",
            "fetching open orders without specifying a symbol",
        ]
        self.window_secs = window_secs
        self.last_seen: dict[str, float] = {}

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        for key in self.keys:
            if key in msg:
                current_time = time.time()
                last = self.last_seen.get(key)
                if last and current_time - last < self.window_secs:
                    return False
                self.last_seen[key] = current_time
                break
        return True


class OncePerRunFilter(logging.Filter):
    def __init__(self, messages: list[str] | None = None):
        super().__init__()
        self.messages = set(messages or ["Telegram bot initialized"])
        self.seen: set[str] = set()

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        for key in self.messages:
            if key in msg:
                if msg in self.seen:
                    return False
                self.seen.add(msg)
                break
        return True


# ============= Formatters =============
class ColoredFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": Fore.CYAN if COLORAMA_AVAILABLE else "",
        "INFO": Fore.GREEN if COLORAMA_AVAILABLE else "",
        "WARNING": Fore.YELLOW if COLORAMA_AVAILABLE else "",
        "ERROR": (Fore.RED + Style.BRIGHT) if COLORAMA_AVAILABLE else "",
        "CRITICAL": (Back.RED + Fore.WHITE + Style.BRIGHT) if COLORAMA_AVAILABLE else "",
    }
    EMOJIS = {"DEBUG": "🔍", "INFO": "✅", "WARNING": "⚠️", "ERROR": "❌", "CRITICAL": "🔥"}

    def __init__(self, use_emoji: bool = True, use_color: bool = True):
        super().__init__()
        self.use_emoji = use_emoji
        self.use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        levelname = record.levelname
        color = self.COLORS.get(levelname, "") if self.use_color else ""
        emoji = self.EMOJIS.get(levelname, "") if self.use_emoji else ""
        reset = Style.RESET_ALL if (COLORAMA_AVAILABLE and self.use_color) else ""
        time_str = self.formatTime(record, "%H:%M:%S")
        tag = getattr(record, "tag", "SYSTEM")
        parts: list[str] = [time_str]
        if emoji:
            parts.append(emoji)
        parts.append(f"[{tag:^10}]")
        prefix = " ".join(parts)
        message = record.getMessage()
        if self.use_color and COLORAMA_AVAILABLE:
            # Dynamically highlight the resolved quote coin without hardcoding USDT/USDC
            try:
                from core.config import TradingConfig  # lazy import to avoid cycles

                qc = TradingConfig.from_env().resolved_quote_coin
                message = re.sub(rf"\b{re.escape(qc)}\b", f"{Fore.CYAN}\\g<0>{Style.RESET_ALL}", message)
            except Exception:
                pass
            message = message.replace(" OK", f"{Fore.GREEN} OK{Style.RESET_ALL}")
        return f"{color}{prefix}{reset} {message}"


class JSONLFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "name": record.name,
            "tag": getattr(record, "tag", "SYSTEM"),
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in {
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "getMessage",
                "tag",
                "exc_info",
                "exc_text",
            }:
                try:
                    json.dumps(value)
                    log_obj[key] = value
                except Exception:
                    log_obj[key] = str(value)
        if record.exc_info:
            log_obj["exc"] = self.formatException(record.exc_info)
        return json.dumps(log_obj, ensure_ascii=False)


# ============= Smart handler with compression and total limit =============
class SmartRotatingHandler(RotatingFileHandler):
    def __init__(
        self,
        filename: str,
        maxBytes: int = 20 * 1024 * 1024,
        backupCount: int = 2,
        totalLimitMB: int = 100,
        compress: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(filename, maxBytes=maxBytes, backupCount=backupCount, **kwargs)
        self.totalLimitMB = totalLimitMB
        self.compress = compress

    def doRollover(self) -> None:
        super().doRollover()
        if self.compress:
            for i in range(1, self.backupCount + 1):
                source = Path(f"{self.baseFilename}.{i}")
                gz_path = Path(f"{self.baseFilename}.{i}.gz")
                if source.exists() and not gz_path.exists():
                    try:
                        with source.open("rb") as f_in, gzip.open(str(gz_path), "wb") as f_out:
                            shutil.copyfileobj(f_in, f_out)
                        source.unlink(missing_ok=True)
                    except Exception:
                        pass
        self._check_total_size()

    def _check_total_size(self) -> None:
        log_dir = Path(self.baseFilename).parent
        total_size = 0
        files: list[tuple[Path, float, int]] = []
        for pattern in ("*.log*", "*.jsonl*"):
            for file in log_dir.glob(pattern):
                if file.is_file():
                    try:
                        size = file.stat().st_size
                        total_size += size
                        files.append((file, file.stat().st_mtime, size))
                    except Exception:
                        continue
        files.sort(key=lambda x: x[1])
        limit_bytes = self.totalLimitMB * 1024 * 1024
        while total_size > limit_bytes and files:
            oldest = files.pop(0)
            try:
                oldest[0].unlink()
                total_size -= oldest[2]
            except Exception:
                pass


# ============= Setup function =============
def setup_logging(
    app_name: str = "binance_bot",
    log_dir: str = "logs",
    level_console: str | None = None,
    level_file: str | None = None,
) -> logging.Logger:
    level_console = level_console or env_str("LOG_CONSOLE_LEVEL", "INFO")
    level_file = level_file or env_str("LOG_FILE_LEVEL", "INFO")

    use_emoji = env_bool("LOG_EMOJI", True) and sys.stdout.isatty()
    use_rich = env_bool("LOG_RICH", True) and RICH_AVAILABLE and sys.stdout.isatty()
    use_color = env_bool("LOG_COLOR", True) and sys.stdout.isatty()

    rate_limit_secs = int(env_str("LOG_RATE_LIMIT_SECS", "60"))
    dedup_window_secs = int(env_str("LOG_DEDUP_WINDOW_SECS", "60"))

    max_size_mb = int(env_str("LOG_MAX_SIZE_MB", "20"))
    backup_count = int(env_str("LOG_BACKUP_COUNT", "2"))
    total_limit_mb = int(env_str("LOG_TOTAL_LIMIT_MB", "100"))
    compress = env_bool("LOG_COMPRESS", True)

    Path(log_dir).mkdir(exist_ok=True)

    logger = logging.getLogger(app_name)
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    # Console
    if use_rich:
        console_handler = RichHandler(
            rich_tracebacks=False,
            show_path=False,
            markup=True,
            log_time_format="%H:%M:%S",
            console=Console(force_terminal=True),
        )
    else:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(ColoredFormatter(use_emoji=use_emoji, use_color=use_color))
    console_handler.setLevel(getattr(logging, level_console.upper(), logging.INFO))
    console_handler.addFilter(DuplicateFilter(dedup_window_secs))
    console_handler.addFilter(RateLimitFilter(window_secs=rate_limit_secs))
    console_handler.addFilter(OncePerRunFilter())
    logger.addHandler(console_handler)

    # Readable file
    readable_handler = SmartRotatingHandler(
        f"{log_dir}/main.log",
        maxBytes=max_size_mb * 1024 * 1024,
        backupCount=backup_count,
        totalLimitMB=max(1, total_limit_mb // 2),
        compress=compress,
        encoding="utf-8",
    )
    readable_format = "%(asctime)s | %(levelname)-7s | [%(tag)-10s] %(message)s"
    readable_handler.setFormatter(logging.Formatter(readable_format, datefmt="%Y-%m-%d %H:%M:%S"))
    readable_handler.setLevel(getattr(logging, level_file.upper(), logging.INFO))
    logger.addHandler(readable_handler)

    # JSONL file
    jsonl_handler = SmartRotatingHandler(
        f"{log_dir}/main.jsonl",
        maxBytes=max_size_mb * 1024 * 1024,
        backupCount=backup_count,
        totalLimitMB=max(1, total_limit_mb // 2),
        compress=compress,
        encoding="utf-8",
    )
    jsonl_handler.setFormatter(JSONLFormatter())
    jsonl_handler.setLevel(getattr(logging, level_file.upper(), logging.INFO))
    logger.addHandler(jsonl_handler)

    # Reduce noise
    for noisy in ("telegram", "ccxt", "asyncio", "urllib3"):
        try:
            logging.getLogger(noisy).setLevel(logging.WARNING)
        except Exception:
            pass

    return logger


# ============= Helpers =============
def get_logger(name: str | None = None, tag: str | None = None) -> logging.LoggerAdapter:
    base = logging.getLogger(name or "binance_bot")
    if tag:
        return logging.LoggerAdapter(base, {"tag": tag})
    return logging.LoggerAdapter(base, {"tag": "SYSTEM"})


def set_tag(logger_obj: logging.LoggerAdapter, tag: str) -> None:
    if hasattr(logger_obj, "extra"):
        logger_obj.extra["tag"] = tag


# ============= Session banners =============
def print_session_banner_start(logger_obj: logging.LoggerAdapter | logging.Logger, run_id: str, mode: str) -> None:
    time_str = datetime.now().strftime("%H:%M:%S")
    banner = f"{'─' * 10} START [{run_id}] mode={mode} time={time_str} {'─' * 10}"
    underline = "_" * len(banner)
    emit = logger_obj.info if hasattr(logger_obj, "info") else print
    emit(banner)
    emit(underline)
    emit("")


def print_session_banner_end(
    logger_obj: logging.LoggerAdapter | logging.Logger, run_id: str, status: str, elapsed_sec: float
) -> None:
    mins, secs = divmod(int(elapsed_sec), 60)
    hours, mins = divmod(mins, 60)
    elapsed_str = f"{hours:02d}:{mins:02d}:{secs:02d}"
    banner = f"{'─' * 10} END [{run_id}] status={status} elapsed={elapsed_str} {'─' * 10}"
    underline = "_" * len(banner)
    emit = logger_obj.info if hasattr(logger_obj, "info") else print
    emit(banner)
    emit(underline)
    emit("")


# ============= Section context =============
@contextmanager
def section(logger_obj: logging.LoggerAdapter | logging.Logger, tag: str, title: str):
    start_time = time.perf_counter()
    sec_logger = get_logger(getattr(logger_obj, "name", None), tag)
    sec_logger.info(f"► {title} — start")
    try:
        yield sec_logger
    finally:
        elapsed = time.perf_counter() - start_time
        sec_logger.info(f"✓ {title} — done ({elapsed:.3f}s)")


# ============= Health test =============
def health() -> None:
    logger_obj = get_logger(tag="HEALTH")
    logger_obj.debug("Debug message")
    logger_obj.info("Info message")
    logger_obj.warning("Warning message")
    logger_obj.error("Error message")


# ============= Backward-compatible adapter =============
class UnifiedLogger:
    def __init__(self, config: Any | None = None):
        self.config = config
        self._base_logger = setup_logging(app_name="binance_bot", log_dir="logs")
        self._logger_adapter = get_logger("binance_bot")
        self._run_id = uuid.uuid4().hex[:8]
        self.telegram = None

    def attach_telegram(self, telegram_bot: Any) -> None:
        self.telegram = telegram_bot

    def log_event(self, component: str, level: str, message: str, details: Any = None, channels: list | None = None):
        level_num = getattr(logging, (level or "INFO").upper(), logging.INFO)
        extras = {"tag": component}
        if details is not None:
            extras["details"] = details
        try:
            self._base_logger.log(level_num, message, extra=extras)
        except Exception:
            self._base_logger.log(level_num, f"[{component}] {message}")
        if self.telegram and level_num >= logging.ERROR:
            try:
                txt = f"[{component}] {message}"
                if details is not None:
                    txt += f"\n{json.dumps(details, ensure_ascii=False) if isinstance(details, dict) else str(details)}"
                import asyncio

                asyncio.create_task(self.telegram.send_message(txt))
            except Exception:
                pass

    def log_runtime_status(self, status: str, details: dict[str, Any] | None = None) -> None:
        self.log_event("RUNTIME", "INFO", f"Status: {status}", details)

    @property
    def logger(self) -> logging.LoggerAdapter:
        return self._logger_adapter
