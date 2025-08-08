# core/leverage_manager.py

from datetime import datetime
from pathlib import Path
from typing import Any

import orjson


class LeverageManager:
    """Управление leverage с динамическими корректировками"""

    def __init__(self, config, logger=None):
        self.config = config
        self.logger = logger
        self.base_leverage_map = {}
        self.dynamic_adjustments = {}
        self.leverage_history = {}

        self.load_base_map()
        self.load_state()

    def load_base_map(self):
        """Загружает базовую карту левереджа из JSON"""
        path = Path(self.config.leverage_map_file)
        if not path.exists():
            raise FileNotFoundError(f"Leverage map file not found: {path}")

        with open(path, "rb") as f:
            self.base_leverage_map = orjson.loads(f.read())

    def get_optimal_leverage(self, symbol: str, market_data: dict[str, Any] = None) -> int:
        symbol = symbol.replace("/", "")
        base = self.base_leverage_map.get(
            symbol, self.base_leverage_map.get("DEFAULT", self.config.leverage_default)
        )

        if symbol in self.dynamic_adjustments:
            base = self.dynamic_adjustments[symbol]

        if market_data:
            atr = market_data.get("atr_percent", 0)
            if atr > 2.0:
                base = max(1, base - 2)
            elif atr < 0.5:
                base = min(20, base + 1)

        # Убеждаемся, что возвращаем int
        if base is None:
            base = self.config.leverage_default
        return int(base)

    def analyze_performance_and_suggest(self, symbol: str, stats: dict[str, Any]) -> int | None:
        current = self.get_optimal_leverage(symbol)
        suggested = current

        win_rate = stats.get("win_rate", 0.5)
        avg_drawdown = stats.get("avg_drawdown_percent", 0)
        sl_frequency = stats.get("sl_hit_rate", 0)

        # Handle missing drawdown data gracefully
        if avg_drawdown is None:
            avg_drawdown = 0

        if win_rate > 0.65 and avg_drawdown < 1.0:
            suggested = min(current + 1, 20)
        elif win_rate < 0.4 or avg_drawdown > 2.0:
            suggested = max(current - 2, 1)
        elif sl_frequency > 0.5:
            suggested = max(current - 1, 1)

        if suggested != current:
            return suggested
        return None

    def apply_suggestion(self, symbol: str, new_leverage: int, auto_apply: bool = False):
        if not auto_apply:
            return {
                "symbol": symbol,
                "current": self.get_optimal_leverage(symbol),
                "suggested": new_leverage,
                "pending": True,
            }

        old = self.get_optimal_leverage(symbol)
        self.dynamic_adjustments[symbol] = new_leverage

        if symbol not in self.leverage_history:
            self.leverage_history[symbol] = []

        self.leverage_history[symbol].append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "old": old,
                "new": new_leverage,
                "type": "optimization",
            }
        )

        self.save_state()

        if self.logger:
            self.logger.log_event(
                f"Leverage updated for {symbol}: {old}x -> {new_leverage}x",
                "INFO",
                "leverage_manager",
            )

        return {"symbol": symbol, "old": old, "new": new_leverage, "applied": True}

    def save_state(self):
        state = {
            "dynamic_adjustments": self.dynamic_adjustments,
            "leverage_history": self.leverage_history,
            "last_updated": datetime.utcnow().isoformat(),
        }
        path = Path("data/leverage_state.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            f.write(orjson.dumps(state, option=orjson.OPT_INDENT_2))

    def load_state(self):
        path = Path("data/leverage_state.json")
        if path.exists():
            with open(path, "rb") as f:
                state = orjson.loads(f.read())
                self.dynamic_adjustments = state.get("dynamic_adjustments", {})
                self.leverage_history = state.get("leverage_history", {})

    def get_leverage_report(self) -> dict[str, Any]:
        report = {
            "total_symbols": len(self.base_leverage_map),
            "custom_adjustments": len(self.dynamic_adjustments),
            "distribution": {},
            "risk_levels": {
                "conservative": [],
                "moderate": [],
                "aggressive": [],
                "very_aggressive": [],
            },
        }
        for symbol in self.base_leverage_map:
            leverage = self.get_optimal_leverage(symbol)
            if leverage not in report["distribution"]:
                report["distribution"][leverage] = 0
            report["distribution"][leverage] += 1

            if leverage <= 5:
                report["risk_levels"]["conservative"].append(symbol)
            elif leverage <= 10:
                report["risk_levels"]["moderate"].append(symbol)
            elif leverage <= 15:
                report["risk_levels"]["aggressive"].append(symbol)
            else:
                report["risk_levels"]["very_aggressive"].append(symbol)

        return report

    def batch_analyze_all_symbols(self, performance_data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        """Analyze all symbols and return suggestions"""
        suggestions = []

        for symbol, stats in performance_data.items():
            suggestion = self.analyze_performance_and_suggest(symbol, stats)
            if suggestion:
                suggestions.append({
                    "symbol": symbol,
                    "current": self.get_optimal_leverage(symbol),
                    "suggested": suggestion,
                    "stats": stats
                })

        # Sort by potential improvement
        suggestions.sort(key=lambda x: abs(x["suggested"] - x["current"]), reverse=True)
        return suggestions


__all__ = ["LeverageManager"]
