#!/usr/bin/env python3
"""
Short monitored run of the trading bot (~60 seconds) with graceful shutdown.
Designed for CI/ops to validate startup, basic loop health, and shutdown logic
without manual Ctrl+C.
"""

import asyncio
import os
import sys


async def _run_for_seconds(seconds: int = 60) -> None:
    from main import SimplifiedTradingBot

    bot = SimplifiedTradingBot()
    await bot.initialize()
    try:
        await asyncio.sleep(seconds)
    finally:
        # Graceful shutdown will cancel orders and close positions if any
        await bot.shutdown()


def main() -> None:
    # Windows compatibility
    if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Respect --dry-run flag from args for safer runs
    if any(arg == "--dry-run" for arg in sys.argv[1:]):
        os.environ["DRY_RUN"] = "true"

    seconds = 60
    for arg in sys.argv[1:]:
        if arg.startswith("--seconds="):
            try:
                seconds = int(arg.split("=", 1)[1])
            except Exception:
                pass

    asyncio.run(_run_for_seconds(seconds))


if __name__ == "__main__":
    main()

