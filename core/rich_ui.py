#!/usr/bin/env python3
"""
Rich UI helpers for console dashboards.
This module is optional and only used when `rich` is installed.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

try:
    from rich.console import Group  # type: ignore[import-not-found]
    from rich.live import Live  # type: ignore[import-not-found]
    from rich.panel import Panel  # type: ignore[import-not-found]
    from rich.progress import Progress, SpinnerColumn, TextColumn  # type: ignore[import-not-found]
    from rich.table import Table  # type: ignore[import-not-found]

    RICH_AVAILABLE = True
except Exception:
    RICH_AVAILABLE = False


@dataclass
class RichDashboard:
    """Simple Rich dashboard with periodic refresh.

    Usage:
      dash = RichDashboard(data_provider=my_func)
      dash.start()
      ...
      dash.stop()
    """

    data_provider: Callable[[], dict[str, Any]]
    refresh_secs: float = 1.0
    _thread: threading.Thread | None = field(default=None, init=False)
    _stop: threading.Event = field(default_factory=threading.Event, init=False)

    def start(self) -> None:
        if not RICH_AVAILABLE:
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="rich_dashboard", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not RICH_AVAILABLE:
            return
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _render(self) -> Any:
        data = {}
        try:
            data = self.data_provider() or {}
        except Exception:
            data = {"error": "data provider failed"}

        table = Table(title="BinanceBot Runtime", expand=True)
        table.add_column("Key", no_wrap=True, justify="right")
        table.add_column("Value", overflow="fold")
        for k, v in data.items():
            table.add_row(str(k), str(v))

        progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold green]Running..."),
            transient=True,
        )
        panel = Panel(table, title="Status", border_style="cyan")
        return Group(panel, progress)

    def _run(self) -> None:
        assert RICH_AVAILABLE
        with Live(self._render(), refresh_per_second=max(1, int(1 / self.refresh_secs))) as live:
            while not self._stop.is_set():
                try:
                    live.update(self._render())
                except Exception:
                    pass
                time.sleep(self.refresh_secs)
