#!/usr/bin/env python3
"""
Lightweight Trade Engine (v2) for Binance USDC Futures

This engine orchestrates:
- Symbol discovery (USDC perpetuals)
- Strategy evaluation (ScalpingV1)
- Basic risk checks (max positions, cooldown)
- Position entry via OrderManager with TP/SL

It intentionally avoids legacy dependencies from core/trade_engine.py.
"""

from __future__ import annotations

from core.config import TradingConfig
from core.exchange_client import OptimizedExchangeClient
from core.order_manager import OrderManager
from core.risk_guard import is_symbol_blocked, is_symbol_recently_traded, update_symbol_last_entry
from core.symbol_manager import SymbolManager
from core.unified_logger import UnifiedLogger
from strategies.scalping_v1 import ScalpingV1


class TradeEngineV2:
    """Minimal orchestrator for scan → evaluate → risk → execute."""

    def __init__(
        self,
        config: TradingConfig,
        exchange: OptimizedExchangeClient,
        order_manager: OrderManager,
        logger: UnifiedLogger,
    ) -> None:
        self.config = config
        self.exchange = exchange
        self.order_manager = order_manager
        self.logger = logger

        # Core helpers
        self.symbol_manager = SymbolManager(config, exchange, logger)
        self.strategy = ScalpingV1(config, logger)

        # State
        self._last_symbols: list[str] = []

    async def run_cycle(self) -> None:
        """Run a single scan/evaluate/execute cycle."""
        try:
            if not self.exchange.is_initialized:
                return

            # Respect max positions
            if self.order_manager.get_position_count() >= self.config.max_positions:
                return

            # Discover symbols with basic volume filter
            symbols = await self.symbol_manager.get_symbols_with_volume_filter(
                min_volume_usdc=getattr(self.config, "volume_threshold_usdc", 20000)
            )
            self._last_symbols = symbols

            for symbol in symbols[:5]:  # Limit per cycle
                if await self.order_manager.has_position(symbol):
                    continue

                # RiskGuard gates
                if is_symbol_blocked(symbol):
                    self.logger.log_event("ENGINE", "DEBUG", f"{symbol}: blocked by SL-streak cooldown")
                    continue
                if is_symbol_recently_traded(symbol, pause_seconds=self.config.entry_cooldown_seconds):
                    self.logger.log_event("ENGINE", "DEBUG", f"{symbol}: skip due to recent entry cooldown")
                    continue

                direction, breakdown = await self._evaluate_symbol(symbol)
                if not direction:
                    continue

                entry_price = breakdown.get("entry_price")
                if not entry_price:
                    # Fetch last price as fallback
                    ticker = await self.exchange.get_ticker(symbol)
                    if not ticker:
                        continue
                    entry_price = ticker.get("last") or ticker.get("close")
                if not entry_price:
                    continue

                # Position sizing: ensure minimum notional
                notional_min = getattr(self.config, "min_notional_open", 15.0)
                qty = max(
                    getattr(self.config, "min_trade_qty", 0.001),
                    round(float(notional_min) / float(entry_price), 6),
                )

                leverage = self.config.get_leverage_for_symbol(symbol)

                # Execute entry with TP/SL managed by OrderManager
                try:
                    result = await self.order_manager.place_position_with_tp_sl(
                        symbol=symbol,
                        side=direction,
                        quantity=qty,
                        entry_price=float(entry_price),
                        leverage=int(leverage),
                    )
                    if result and result.get("success"):
                        self.logger.log_event(
                            "ENGINE",
                            "INFO",
                            f"Entered {symbol} {direction} qty={qty} @ {entry_price}",
                        )
                        update_symbol_last_entry(symbol)
                except Exception as e:
                    self.logger.log_event(
                        "ENGINE",
                        "ERROR",
                        f"Failed to enter {symbol} {direction}: {e}",
                    )

        except Exception as e:
            self.logger.log_event("ENGINE", "ERROR", f"run_cycle error: {e}")

    async def _evaluate_symbol(self, symbol: str) -> tuple[str | None, dict]:
        """Evaluate a single symbol using ScalpingV1 directly."""
        try:
            ohlcv = await self.exchange.get_ohlcv(symbol, timeframe="5m", limit=150)
            if not ohlcv or len(ohlcv) < 30:
                return None, {"reason": "no_data"}

            # Convert to DataFrame inline to avoid StrategyManager coupling
            import pandas as pd

            df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)

            return await self.strategy.should_enter_trade(symbol, df)
        except Exception as e:
            self.logger.log_event("ENGINE", "ERROR", f"{symbol}: evaluate error: {e}")
            return None, {"error": str(e)}
