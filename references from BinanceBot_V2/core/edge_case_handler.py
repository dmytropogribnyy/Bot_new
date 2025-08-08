import statistics
import time
from collections import defaultdict, deque
from collections.abc import Callable
from typing import Any

from core.config import TradingConfig
from core.unified_logger import UnifiedLogger


class EdgeCaseHandler:
    """Comprehensive edge case handler for exceptional market conditions"""

    def __init__(self, config: TradingConfig, logger: UnifiedLogger | None = None):
        self.config = config
        self.logger = logger

        # Edge case detection thresholds
        self._volatility_thresholds = {
            'high_volatility': 0.05,      # 5% price change in 1 minute
            'extreme_volatility': 0.10,    # 10% price change in 1 minute
            'crash_threshold': 0.20,       # 20% price change in 1 minute
            'flash_crash': 0.30            # 30% price change in 1 minute
        }

        # Network and connectivity thresholds
        self._network_thresholds = {
            'high_latency': 2000,          # 2 seconds
            'timeout_threshold': 10000,     # 10 seconds
            'error_rate_threshold': 0.15,   # 15% error rate
            'consecutive_failures': 5       # 5 consecutive failures
        }

        # Market condition tracking
        self._market_conditions = {
            'volatility_history': defaultdict(lambda: deque(maxlen=100)),
            'price_changes': defaultdict(lambda: deque(maxlen=60)),
            'volume_spikes': defaultdict(lambda: deque(maxlen=100)),
            'spread_widening': defaultdict(lambda: deque(maxlen=100))
        }

        # Edge case state
        self._edge_case_state = {
            'high_volatility_mode': False,
            'extreme_volatility_mode': False,
            'network_issues': False,
            'market_crash_detected': False,
            'emergency_mode': False,
            'recovery_mode': False
        }

        # Adaptive measures
        self._adaptive_measures = {
            'position_size_reduction': 1.0,
            'risk_multiplier': 1.0,
            'trading_frequency_reduction': 1.0,
            'leverage_reduction': 1.0
        }

        # Recovery tracking
        self._recovery_metrics = {
            'last_volatility_peak': 0,
            'last_network_issue': 0,
            'recovery_start_time': 0,
            'stability_duration': 0
        }

        # Callbacks for different edge cases
        self._edge_case_callbacks = {
            'high_volatility': [],
            'extreme_volatility': [],
            'network_issues': [],
            'market_crash': [],
            'recovery': []
        }

        # Statistics tracking
        self._edge_case_stats = {
            'volatility_events': 0,
            'network_events': 0,
            'crash_events': 0,
            'recovery_events': 0,
            'total_downtime': 0
        }

    async def analyze_market_conditions(self, symbol: str, ticker_data: dict[str, Any]) -> dict[str, Any]:
        """Analyze current market conditions for edge cases"""
        try:
            current_price = ticker_data.get('last', 0)
            current_volume = ticker_data.get('volume', 0)
            current_bid = ticker_data.get('bid', 0)
            current_ask = ticker_data.get('ask', 0)

            if not all([current_price, current_bid, current_ask]):
                return {'status': 'insufficient_data'}

            # Calculate price change
            price_changes = self._market_conditions['price_changes'][symbol]
            if price_changes:
                last_price = price_changes[-1] if price_changes else current_price
                price_change_pct = abs(current_price - last_price) / last_price if last_price > 0 else 0
                price_changes.append(current_price)
            else:
                price_change_pct = 0
                price_changes.append(current_price)

            # Calculate volatility
            volatility = self._calculate_volatility(symbol)

            # Calculate spread
            spread_pct = (current_ask - current_bid) / current_price if current_price > 0 else 0

            # Detect edge cases
            edge_cases = []

            # High volatility detection
            if price_change_pct > self._volatility_thresholds['high_volatility']:
                edge_cases.append('high_volatility')
                await self._handle_high_volatility(symbol, price_change_pct)

            # Extreme volatility detection
            if price_change_pct > self._volatility_thresholds['extreme_volatility']:
                edge_cases.append('extreme_volatility')
                await self._handle_extreme_volatility(symbol, price_change_pct)

            # Market crash detection
            if price_change_pct > self._volatility_thresholds['crash_threshold']:
                edge_cases.append('market_crash')
                await self._handle_market_crash(symbol, price_change_pct)

            # Flash crash detection
            if price_change_pct > self._volatility_thresholds['flash_crash']:
                edge_cases.append('flash_crash')
                await self._handle_flash_crash(symbol, price_change_pct)

            # Spread widening detection
            if spread_pct > 0.01:  # 1% spread
                edge_cases.append('spread_widening')
                await self._handle_spread_widening(symbol, spread_pct)

            # Update volatility history
            self._market_conditions['volatility_history'][symbol].append(volatility)

            return {
                'status': 'analyzed',
                'edge_cases': edge_cases,
                'volatility': volatility,
                'price_change_pct': price_change_pct,
                'spread_pct': spread_pct,
                'current_price': current_price,
                'current_volume': current_volume
            }

        except Exception as e:
            self.logger.log_event("EDGE_CASE", "ERROR", f"❌ Market condition analysis error: {e}")
            return {'status': 'error', 'error': str(e)}

    def _calculate_volatility(self, symbol: str) -> float:
        """Calculate current volatility based on price history"""
        try:
            price_changes = self._market_conditions['price_changes'][symbol]
            if len(price_changes) < 2:
                return 0.0

            # Calculate rolling volatility (standard deviation of price changes)
            changes = []
            for i in range(1, len(price_changes)):
                if price_changes[i-1] > 0:
                    change = (price_changes[i] - price_changes[i-1]) / price_changes[i-1]
                    changes.append(abs(change))

            if len(changes) < 5:
                return 0.0

            return statistics.mean(changes)

        except Exception:
            return 0.0

    async def _handle_high_volatility(self, symbol: str, price_change_pct: float):
        """Handle high volatility conditions"""
        if not self._edge_case_state['high_volatility_mode']:
            self._edge_case_state['high_volatility_mode'] = True
            self._adaptive_measures['position_size_reduction'] = 0.7
            self._adaptive_measures['risk_multiplier'] = 0.8
            self._adaptive_measures['trading_frequency_reduction'] = 0.8

            self.logger.log_event("EDGE_CASE", "WARNING",
                f"⚠️ High volatility detected for {symbol}: {price_change_pct:.2%}")

            # Trigger callbacks
            for callback in self._edge_case_callbacks['high_volatility']:
                try:
                    await callback(symbol, price_change_pct, self._adaptive_measures)
                except Exception as e:
                    self.logger.log_event("EDGE_CASE", "ERROR", f"❌ High volatility callback error: {e}")

            self._edge_case_stats['volatility_events'] += 1

    async def _handle_extreme_volatility(self, symbol: str, price_change_pct: float):
        """Handle extreme volatility conditions"""
        if not self._edge_case_state['extreme_volatility_mode']:
            self._edge_case_state['extreme_volatility_mode'] = True
            self._adaptive_measures['position_size_reduction'] = 0.5
            self._adaptive_measures['risk_multiplier'] = 0.5
            self._adaptive_measures['trading_frequency_reduction'] = 0.5
            self._adaptive_measures['leverage_reduction'] = 0.8

            self.logger.log_event("EDGE_CASE", "WARNING",
                f"🚨 Extreme volatility detected for {symbol}: {price_change_pct:.2%}")

            # Trigger callbacks
            for callback in self._edge_case_callbacks['extreme_volatility']:
                try:
                    await callback(symbol, price_change_pct, self._adaptive_measures)
                except Exception as e:
                    self.logger.log_event("EDGE_CASE", "ERROR", f"❌ Extreme volatility callback error: {e}")

    async def _handle_market_crash(self, symbol: str, price_change_pct: float):
        """Handle market crash conditions"""
        if not self._edge_case_state['market_crash_detected']:
            self._edge_case_state['market_crash_detected'] = True
            self._adaptive_measures['position_size_reduction'] = 0.2
            self._adaptive_measures['risk_multiplier'] = 0.2
            self._adaptive_measures['trading_frequency_reduction'] = 0.1
            self._adaptive_measures['leverage_reduction'] = 0.5

            self.logger.log_event("EDGE_CASE", "ERROR",
                f"💥 Market crash detected for {symbol}: {price_change_pct:.2%}")

            # Trigger callbacks
            for callback in self._edge_case_callbacks['market_crash']:
                try:
                    await callback(symbol, price_change_pct, self._adaptive_measures)
                except Exception as e:
                    self.logger.log_event("EDGE_CASE", "ERROR", f"❌ Market crash callback error: {e}")

            self._edge_case_stats['crash_events'] += 1

    async def _handle_flash_crash(self, symbol: str, price_change_pct: float):
        """Handle flash crash conditions"""
        self._edge_case_state['emergency_mode'] = True
        self._adaptive_measures['position_size_reduction'] = 0.0  # Stop trading
        self._adaptive_measures['risk_multiplier'] = 0.0
        self._adaptive_measures['trading_frequency_reduction'] = 0.0
        self._adaptive_measures['leverage_reduction'] = 0.0

        self.logger.log_event("EDGE_CASE", "CRITICAL",
            f"⚡ Flash crash detected for {symbol}: {price_change_pct:.2%} - EMERGENCY MODE ACTIVATED")

        # Trigger emergency callbacks
        for callback in self._edge_case_callbacks['market_crash']:
            try:
                await callback(symbol, price_change_pct, self._adaptive_measures)
            except Exception as e:
                self.logger.log_event("EDGE_CASE", "ERROR", f"❌ Flash crash callback error: {e}")

    async def _handle_spread_widening(self, symbol: str, spread_pct: float):
        """Handle spread widening conditions"""
        self.logger.log_event("EDGE_CASE", "WARNING",
            f"📈 Spread widening detected for {symbol}: {spread_pct:.2%}")

        # Reduce position sizes when spreads are wide
        if spread_pct > 0.02:  # 2% spread
            self._adaptive_measures['position_size_reduction'] *= 0.8

    async def analyze_network_conditions(self, response_time: float, success: bool, error_type: str | None = None) -> dict[str, Any]:
        """Analyze network conditions for edge cases"""
        try:
            network_issues = []

            # High latency detection
            if response_time > self._network_thresholds['high_latency']:
                network_issues.append('high_latency')
                await self._handle_network_latency(response_time)

            # Timeout detection
            if response_time > self._network_thresholds['timeout_threshold']:
                network_issues.append('timeout')
                await self._handle_network_timeout(response_time)

            # Error rate tracking
            if not success:
                await self._track_network_error(error_type)

            # Check for consecutive failures
            if await self._check_consecutive_failures():
                network_issues.append('consecutive_failures')
                await self._handle_consecutive_failures()

            return {
                'status': 'analyzed',
                'network_issues': network_issues,
                'response_time': response_time,
                'success': success,
                'error_type': error_type
            }

        except Exception as e:
            self.logger.log_event("EDGE_CASE", "ERROR", f"❌ Network condition analysis error: {e}")
            return {'status': 'error', 'error': str(e)}

    async def _handle_network_latency(self, response_time: float):
        """Handle high network latency"""
        if not self._edge_case_state['network_issues']:
            self._edge_case_state['network_issues'] = True
            self._adaptive_measures['trading_frequency_reduction'] *= 0.8

            self.logger.log_event("EDGE_CASE", "WARNING",
                f"🌐 High network latency detected: {response_time:.0f}ms")

            self._edge_case_stats['network_events'] += 1

    async def _handle_network_timeout(self, response_time: float):
        """Handle network timeout"""
        self.logger.log_event("EDGE_CASE", "ERROR",
            f"⏰ Network timeout detected: {response_time:.0f}ms")

        # Reduce trading frequency significantly
        self._adaptive_measures['trading_frequency_reduction'] *= 0.5

    async def _track_network_error(self, error_type: str | None):
        """Track network errors for pattern detection"""
        # This would track error patterns over time
        # For now, just log the error
        if error_type:
            self.logger.log_event("EDGE_CASE", "WARNING", f"🌐 Network error: {error_type}")

    async def _check_consecutive_failures(self) -> bool:
        """Check for consecutive network failures"""
        # This would implement logic to track consecutive failures
        # For now, return False
        return False

    async def _handle_consecutive_failures(self):
        """Handle consecutive network failures"""
        self.logger.log_event("EDGE_CASE", "ERROR", "🌐 Consecutive network failures detected")
        self._adaptive_measures['trading_frequency_reduction'] *= 0.3

    async def check_recovery_conditions(self) -> bool:
        """Check if conditions have improved for recovery"""
        try:
            # Check if volatility has decreased
            volatility_improved = True
            for symbol, volatility_history in self._market_conditions['volatility_history'].items():
                if len(volatility_history) >= 10:
                    recent_volatility = statistics.mean(list(volatility_history)[-10:])
                    if recent_volatility > self._volatility_thresholds['high_volatility']:
                        volatility_improved = False
                        break

            # Check if network issues have resolved
            network_improved = not self._edge_case_state['network_issues']

            # Check stability duration
            current_time = time.time()
            if self._recovery_metrics['recovery_start_time'] == 0:
                self._recovery_metrics['recovery_start_time'] = current_time

            stability_duration = current_time - self._recovery_metrics['recovery_start_time']
            self._recovery_metrics['stability_duration'] = stability_duration

            # Require 5 minutes of stability for recovery
            if volatility_improved and network_improved and stability_duration > 300:
                return True

            return False

        except Exception as e:
            self.logger.log_event("EDGE_CASE", "ERROR", f"❌ Recovery condition check error: {e}")
            return False

    async def initiate_recovery(self):
        """Initiate recovery procedures"""
        try:
            self.logger.log_event("EDGE_CASE", "INFO", "🔄 Initiating recovery procedures...")

            # Gradually restore normal trading parameters
            self._adaptive_measures['position_size_reduction'] = min(1.0, self._adaptive_measures['position_size_reduction'] * 1.2)
            self._adaptive_measures['risk_multiplier'] = min(1.0, self._adaptive_measures['risk_multiplier'] * 1.2)
            self._adaptive_measures['trading_frequency_reduction'] = min(1.0, self._adaptive_measures['trading_frequency_reduction'] * 1.2)
            self._adaptive_measures['leverage_reduction'] = min(1.0, self._adaptive_measures['leverage_reduction'] * 1.1)

            # Reset edge case states
            self._edge_case_state['high_volatility_mode'] = False
            self._edge_case_state['extreme_volatility_mode'] = False
            self._edge_case_state['network_issues'] = False
            self._edge_case_state['market_crash_detected'] = False
            self._edge_case_state['emergency_mode'] = False
            self._edge_case_state['recovery_mode'] = True

            # Trigger recovery callbacks
            for callback in self._edge_case_callbacks['recovery']:
                try:
                    await callback(self._adaptive_measures)
                except Exception as e:
                    self.logger.log_event("EDGE_CASE", "ERROR", f"❌ Recovery callback error: {e}")

            self._edge_case_stats['recovery_events'] += 1

            self.logger.log_event("EDGE_CASE", "INFO", "✅ Recovery procedures completed")

        except Exception as e:
            self.logger.log_event("EDGE_CASE", "ERROR", f"❌ Recovery initiation error: {e}")

    def get_adaptive_measures(self) -> dict[str, float]:
        """Get current adaptive measures"""
        return self._adaptive_measures.copy()

    def get_edge_case_state(self) -> dict[str, bool]:
        """Get current edge case state"""
        return self._edge_case_state.copy()

    def get_edge_case_stats(self) -> dict[str, int]:
        """Get edge case statistics"""
        return self._edge_case_stats.copy()

    def add_edge_case_callback(self, edge_case_type: str, callback: Callable):
        """Add callback for specific edge case type"""
        if edge_case_type in self._edge_case_callbacks:
            self._edge_case_callbacks[edge_case_type].append(callback)

    def reset_edge_case_state(self):
        """Reset all edge case states and measures"""
        self._edge_case_state = {
            'high_volatility_mode': False,
            'extreme_volatility_mode': False,
            'network_issues': False,
            'market_crash_detected': False,
            'emergency_mode': False,
            'recovery_mode': False
        }

        self._adaptive_measures = {
            'position_size_reduction': 1.0,
            'risk_multiplier': 1.0,
            'trading_frequency_reduction': 1.0,
            'leverage_reduction': 1.0
        }

        self.logger.log_event("EDGE_CASE", "INFO", "🔄 Edge case state reset to normal")
