# core/symbol_priority_manager.py
import json
import os
import time
from collections import defaultdict
from typing import List, Tuple

from common.config_loader import GLOBAL_SCALPING_TEST, get_priority_small_balance_pairs
from utils_core import normalize_symbol
from utils_logging import log


class SymbolPriorityManager:
    def __init__(self):
        # Default values for new symbols - score starts at 1.0 (neutral)
        self.symbol_scores = defaultdict(lambda: {"score": 1.0, "failures": 0, "successes": 0, "last_update": time.time()})
        self.failure_window = 3600  # 1 hour sliding window
        self.event_history = defaultdict(list)

        # Load saved priority data if available
        self.priority_file = "data/symbol_priority.json"
        self.load_priority_data()

    def update_symbol_performance(self, symbol: str, success: bool, reason: str = None):
        """Update symbol performance score based on trading outcome"""
        symbol = normalize_symbol(symbol)
        current_time = time.time()

        # Clean old events
        self._clean_old_events(symbol)

        # Record new event
        event = {"time": current_time, "success": success, "reason": reason}
        self.event_history[symbol].append(event)

        # Calculate new score
        self._recalculate_score(symbol)

        log(f"[Priority] Updated {symbol}: success={success}, reason={reason}, " f"new score={self.symbol_scores[symbol]['score']:.2f}", level="DEBUG")

        # Save after significant updates
        self.save_priority_data()

    def _clean_old_events(self, symbol: str):
        """Remove events older than sliding window"""
        current_time = time.time()
        cutoff_time = current_time - self.failure_window

        old_count = len(self.event_history[symbol])
        self.event_history[symbol] = [e for e in self.event_history[symbol] if e["time"] > cutoff_time]
        new_count = len(self.event_history[symbol])

        if old_count != new_count:
            log(f"[Priority] Cleaned {old_count - new_count} old events for {symbol}", level="DEBUG")

    def _recalculate_score(self, symbol: str):
        """Recalculate symbol score based on recent events"""
        events = self.event_history[symbol]
        if not events:
            self.symbol_scores[symbol]["score"] = 1.0
            return

        success_rate = sum(1 for e in events if e["success"]) / len(events)
        base_score = 0.5 + 0.5 * success_rate
        recency_factor = 1.0  # Reserved for future enhancement

        self.symbol_scores[symbol].update(
            {"score": base_score * recency_factor, "failures": sum(1 for e in events if not e["success"]), "successes": sum(1 for e in events if e["success"]), "last_update": time.time()}
        )

    def get_symbol_priority(self, symbol: str) -> float:
        """Get current priority score for a symbol"""
        return self.symbol_scores[symbol]["score"]

    def get_ranked_symbols(self, symbols: List[str], min_score: float = 0.3) -> List[Tuple[str, float]]:
        """Get symbols ranked by priority score"""
        symbol_priorities = [(symbol, self.get_symbol_priority(symbol)) for symbol in symbols if self.get_symbol_priority(symbol) >= min_score]
        return sorted(symbol_priorities, key=lambda x: x[1], reverse=True)

    def save_priority_data(self):
        """Save priority scores to persistent storage"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.priority_file), exist_ok=True)

            # Convert defaultdict to regular dict for serialization
            serializable_scores = {symbol: score_data.copy() for symbol, score_data in self.symbol_scores.items()}

            with open(self.priority_file, "w") as f:
                json.dump(serializable_scores, f, indent=2)

            log(f"Priority data saved to {self.priority_file}", level="DEBUG")
        except Exception as e:
            log(f"Error saving priority data: {e}", level="ERROR")

    def load_priority_data(self):
        """Load priority scores from persistent storage"""
        try:
            if os.path.exists(self.priority_file):
                with open(self.priority_file, "r") as f:
                    saved_scores = json.load(f)

                # Update the defaultdict with saved data
                for symbol, data in saved_scores.items():
                    self.symbol_scores[symbol].update(data)

                log(f"Priority data loaded for {len(saved_scores)} symbols", level="INFO")
            else:
                log("No saved priority data found, starting with default values", level="INFO")
        except Exception as e:
            log(f"Error loading priority data: {e}", level="ERROR")

    def reset_symbol(self, symbol: str):
        """External method to reset a symbol's priority score to default"""
        if symbol in self.symbol_scores:
            self.symbol_scores[symbol] = {"score": 1.0, "failures": 0, "successes": 0, "last_update": time.time()}
            self.event_history[symbol] = []
            log(f"Priority reset for {symbol}", level="INFO")
            self.save_priority_data()


def determine_strategy_mode(symbol, balance):
    """
    Determine whether to use 'scalp' or 'standard' mode for a given symbol and balance.
    """
    # 1. Global scalping toggle for testing all pairs
    if GLOBAL_SCALPING_TEST:
        return "scalp"

    # 2. Full scalping for very small balances
    if balance < 300:
        return "scalp"

    # 3. Priority pairs use scalping up to moderate balance
    if balance < 500 and symbol in get_priority_small_balance_pairs():
        return "scalp"

    # 4. Manual whitelist for volatile pairs
    if symbol in ["DOGE/USDC", "XRP/USDC", "SUI/USDC", "ARB/USDC"]:
        return "scalp"

    # 5. Default to standard mode
    return "standard"


def dynamic_scalping_mode(symbol, balance, volatility_score=0.0, priority_score=0.0):
    """
    Dynamically determine if scalping (3m) mode should be enabled for this symbol.
    Uses balance, volatility and performance score as criteria.
    """
    if GLOBAL_SCALPING_TEST:
        return True

    # Малые балансы — всегда скальпинг
    if balance < 300:
        return True

    # Средние балансы — только при приоритете или высокой волатильности
    if balance < 600:
        if symbol in get_priority_small_balance_pairs():
            return True
        if volatility_score >= 0.8 or priority_score >= 0.8:
            return True

    # Крупные балансы — только при очень высокой активности
    if balance >= 600:
        return volatility_score >= 0.95 and priority_score >= 0.95

    return False
