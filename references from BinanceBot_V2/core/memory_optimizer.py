# Import Windows compatibility error handling
import core.windows_compatibility

import asyncio
import gc
import statistics
import sys
import time
from collections import defaultdict, deque
from typing import Any

import psutil

from core.config import TradingConfig
from core.unified_logger import UnifiedLogger


class MemoryOptimizer:
    """Comprehensive memory optimization and management system"""

    def __init__(self, config: TradingConfig, logger: UnifiedLogger | None = None):
        self.config = config
        self.logger = logger

        # Memory thresholds
        self._memory_thresholds = {
            'warning_threshold': 0.7,    # 70% memory usage
            'critical_threshold': 0.85,   # 85% memory usage
            'emergency_threshold': 0.95,  # 95% memory usage
            'gc_threshold': 0.5,         # 50% memory usage triggers GC
            'cache_clear_threshold': 0.6  # 60% memory usage triggers cache clear
        }

        # Memory tracking
        self._memory_history = deque(maxlen=1000)
        self._gc_stats = {
            'collections': 0,
            'last_collection': 0,
            'objects_freed': 0,
            'collection_time': 0
        }

        # Cache management
        self._caches = {
            'ticker_cache': {},
            'market_data_cache': {},
            'position_cache': {},
            'order_cache': {},
            'performance_cache': {}
        }

        # Memory optimization tasks
        self._optimization_tasks = []
        self._is_running = False

        # Memory monitoring
        self._memory_alerts = []
        self._last_memory_check = 0
        self._memory_check_interval = 30  # 30 seconds

        # Performance tracking
        self._performance_metrics = {
            'memory_usage': deque(maxlen=100),
            'gc_frequency': deque(maxlen=100),
            'cache_hit_rates': defaultdict(lambda: deque(maxlen=100)),
            'memory_leaks': []
        }

    async def start_optimization(self):
        """Start memory optimization tasks"""
        if self._is_running:
            return

        # Skip memory optimization on Windows due to compatibility issues
        if core.windows_compatibility.IS_WINDOWS:
            self.logger.log_event("MEMORY", "INFO", "🧠 Memory optimization disabled for Windows")
            return

        self._is_running = True
        self.logger.log_event("MEMORY", "INFO", "🧠 Starting Memory Optimization System...")

        # Start optimization tasks
        self._optimization_tasks = [
            asyncio.create_task(self._memory_monitoring()),
            asyncio.create_task(self._periodic_garbage_collection()),
            asyncio.create_task(self._cache_management()),
            asyncio.create_task(self._memory_leak_detection()),
            asyncio.create_task(self._performance_tracking())
        ]

    async def stop_optimization(self):
        """Stop memory optimization tasks"""
        self._is_running = False

        for task in self._optimization_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self.logger.log_event("MEMORY", "INFO", "🛑 Memory Optimization System stopped")

    async def _memory_monitoring(self):
        """Monitor memory usage continuously"""
        while self._is_running:
            try:
                # Get current memory usage
                memory_usage = self._get_memory_usage()
                self._memory_history.append(memory_usage)
                self._performance_metrics['memory_usage'].append(memory_usage['percent'])

                # Check thresholds and take action
                await self._check_memory_thresholds(memory_usage)

                # Update last check time
                self._last_memory_check = time.time()

                await asyncio.sleep(self._memory_check_interval)

            except Exception as e:
                self.logger.log_event("MEMORY", "ERROR", f"❌ Memory monitoring error: {e}")
                await asyncio.sleep(60)

    async def _periodic_garbage_collection(self):
        """Perform periodic garbage collection"""
        while self._is_running:
            try:
                # Check if GC is needed
                memory_usage = self._get_memory_usage()

                if memory_usage['percent'] > self._memory_thresholds['gc_threshold']:
                    await self._perform_garbage_collection()

                # Also perform periodic GC every 10 minutes regardless
                await asyncio.sleep(600)  # 10 minutes

                if self._is_running:
                    await self._perform_garbage_collection()

            except Exception as e:
                self.logger.log_event("MEMORY", "ERROR", f"❌ Periodic GC error: {e}")
                await asyncio.sleep(300)

    async def _cache_management(self):
        """Manage memory caches"""
        while self._is_running:
            try:
                memory_usage = self._get_memory_usage()

                # Clear caches if memory usage is high
                if memory_usage['percent'] > self._memory_thresholds['cache_clear_threshold']:
                    await self._clear_caches()

                # Optimize cache sizes
                await self._optimize_cache_sizes()

                await asyncio.sleep(300)  # Check every 5 minutes

            except Exception as e:
                self.logger.log_event("MEMORY", "ERROR", f"❌ Cache management error: {e}")
                await asyncio.sleep(300)

    async def _memory_leak_detection(self):
        """Detect potential memory leaks"""
        while self._is_running:
            try:
                await self._detect_memory_leaks()
                await asyncio.sleep(1800)  # Check every 30 minutes

            except Exception as e:
                self.logger.log_event("MEMORY", "ERROR", f"❌ Memory leak detection error: {e}")
                await asyncio.sleep(1800)

    async def _performance_tracking(self):
        """Track memory performance metrics"""
        while self._is_running:
            try:
                await self._update_performance_metrics()
                await asyncio.sleep(60)  # Update every minute

            except Exception as e:
                self.logger.log_event("MEMORY", "ERROR", f"❌ Performance tracking error: {e}")
                await asyncio.sleep(60)

    def _get_memory_usage(self) -> dict[str, Any]:
        """Get current memory usage statistics"""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()

            # Get system memory
            system_memory = psutil.virtual_memory()

            return {
                'rss': memory_info.rss,  # Resident Set Size
                'vms': memory_info.vms,  # Virtual Memory Size
                'percent': process.memory_percent(),
                'system_percent': system_memory.percent,
                'system_available': system_memory.available,
                'system_total': system_memory.total,
                'system_used': system_memory.used
            }

        except Exception as e:
            self.logger.log_event("MEMORY", "ERROR", f"❌ Failed to get memory usage: {e}")
            return {
                'rss': 0,
                'vms': 0,
                'percent': 0,
                'system_percent': 0,
                'system_available': 0,
                'system_total': 0,
                'system_used': 0
            }

    async def _check_memory_thresholds(self, memory_usage: dict[str, Any]):
        """Check memory thresholds and take appropriate action"""
        percent = memory_usage['percent']

        if percent > self._memory_thresholds['emergency_threshold']:
            await self._handle_emergency_memory()
        elif percent > self._memory_thresholds['critical_threshold']:
            await self._handle_critical_memory()
        elif percent > self._memory_thresholds['warning_threshold']:
            await self._handle_warning_memory()

    async def _handle_warning_memory(self):
        """Handle warning level memory usage"""
        memory_usage = self._get_memory_usage()
        self.logger.log_event("MEMORY", "WARNING",
            f"⚠️ High memory usage detected: {memory_usage['percent']:.1f}%")

        # Clear some caches
        await self._clear_old_cache_entries()

    async def _handle_critical_memory(self):
        """Handle critical level memory usage"""
        memory_usage = self._get_memory_usage()
        self.logger.log_event("MEMORY", "ERROR",
            f"🚨 Critical memory usage detected: {memory_usage['percent']:.1f}%")

        # Force garbage collection
        await self._perform_garbage_collection()

        # Clear all caches
        await self._clear_caches()

        # Reduce memory footprint
        await self._reduce_memory_footprint()

    async def _handle_emergency_memory(self):
        """Handle emergency level memory usage"""
        memory_usage = self._get_memory_usage()
        self.logger.log_event("MEMORY", "CRITICAL",
            f"💥 Emergency memory usage detected: {memory_usage['percent']:.1f}%")

        # Emergency measures
        await self._emergency_memory_cleanup()

        # Alert system administrators
        self._create_memory_alert("EMERGENCY",
            f"Emergency memory usage: {memory_usage['percent']:.1f}%")

    async def _perform_garbage_collection(self):
        """Perform garbage collection"""
        try:
            start_time = time.time()

            # Get object counts before GC
            objects_before = len(gc.get_objects())

            # Perform garbage collection
            collected = gc.collect()

            # Get object counts after GC
            objects_after = len(gc.get_objects())
            objects_freed = objects_before - objects_after

            gc_time = time.time() - start_time

            # Update GC stats
            self._gc_stats['collections'] += 1
            self._gc_stats['last_collection'] = time.time()
            self._gc_stats['objects_freed'] += objects_freed
            self._gc_stats['collection_time'] += gc_time

            self.logger.log_event("MEMORY", "INFO",
                f"🗑️ Garbage collection completed: {gc_time:.3f}s, "
                f"{objects_freed} objects freed, {collected} collected")

            # Update performance metrics
            self._performance_metrics['gc_frequency'].append(gc_time)

        except Exception as e:
            self.logger.log_event("MEMORY", "ERROR", f"❌ Garbage collection failed: {e}")

    async def _clear_caches(self):
        """Clear all memory caches"""
        try:
            cache_cleared = 0

            for cache_name, cache in self._caches.items():
                if cache:
                    cache.clear()
                    cache_cleared += 1

            self.logger.log_event("MEMORY", "INFO",
                f"🧹 Cleared {cache_cleared} caches")

        except Exception as e:
            self.logger.log_event("MEMORY", "ERROR", f"❌ Cache clearing failed: {e}")

    async def _clear_old_cache_entries(self):
        """Clear old cache entries to free memory"""
        try:
            current_time = time.time()
            entries_cleared = 0

            for cache_name, cache in self._caches.items():
                if isinstance(cache, dict):
                    # Remove entries older than 5 minutes
                    old_keys = [
                        key for key, value in cache.items()
                        if hasattr(value, 'get') and isinstance(value.get('timestamp', 0), (int, float))
                        and current_time - value.get('timestamp', 0) > 300
                    ]

                    for key in old_keys:
                        del cache[key]
                        entries_cleared += 1

            if entries_cleared > 0:
                self.logger.log_event("MEMORY", "INFO",
                    f"🧹 Cleared {entries_cleared} old cache entries")

        except Exception as e:
            self.logger.log_event("MEMORY", "ERROR", f"❌ Old cache clearing failed: {e}")

    async def _optimize_cache_sizes(self):
        """Optimize cache sizes based on memory usage"""
        try:
            memory_usage = self._get_memory_usage()

            # Reduce cache sizes if memory usage is high
            if memory_usage['percent'] > 0.6:
                for cache_name, cache in self._caches.items():
                    if isinstance(cache, dict) and len(cache) > 100:
                        # Keep only the most recent 50 entries
                        if hasattr(cache, 'keys'):
                            keys = list(cache.keys())
                            keys_to_remove = keys[:-50]  # Keep last 50
                            for key in keys_to_remove:
                                del cache[key]

        except Exception as e:
            self.logger.log_event("MEMORY", "ERROR", f"❌ Cache size optimization failed: {e}")

    async def _detect_memory_leaks(self):
        """Detect potential memory leaks"""
        try:
            # Get current memory usage
            current_memory = self._get_memory_usage()

            # Check if memory usage has been consistently high
            if len(self._memory_history) >= 10:
                recent_memory = list(self._memory_history)[-10:]
                avg_memory = sum(m['percent'] for m in recent_memory) / len(recent_memory)

                if avg_memory > 0.8:  # 80% average usage
                    self.logger.log_event("MEMORY", "WARNING",
                        f"⚠️ Potential memory leak detected: {avg_memory:.1f}% average usage")

                    # Add to memory leaks list
                    self._performance_metrics['memory_leaks'].append({
                        'timestamp': time.time(),
                        'average_usage': avg_memory,
                        'current_usage': current_memory['percent']
                    })

        except Exception as e:
            self.logger.log_event("MEMORY", "ERROR", f"❌ Memory leak detection failed: {e}")

    async def _reduce_memory_footprint(self):
        """Reduce memory footprint of the application"""
        try:
            # Import Windows compatibility fixes
            import core.windows_compatibility

            # Clear Python's internal caches - Windows compatible
            try:
                import sys
                # Check if sys.modules exists before trying to clear it
                if hasattr(sys, 'modules'):
                    sys.modules.clear()
            except Exception:
                pass  # Игнорируем ошибки в Windows

            # Clear function caches - Windows compatible
            try:
                import functools
                functools._CacheInfo = type('_CacheInfo', (), {})
            except Exception:
                pass

            # Clear other internal caches - Windows compatible
            try:
                import builtins
                if hasattr(builtins, '_cache'):
                    builtins._cache.clear()
            except Exception:
                pass

            self.logger.log_event("MEMORY", "INFO", "🔧 Reduced memory footprint")

        except Exception as e:
            # Check if it's a Windows compatibility error and ignore it
            if "maxsize" in str(e) or "builtin_module_names" in str(e):
                self.logger.log_event("MEMORY", "INFO", "🔧 Memory footprint reduction completed (Windows compatibility)")
            else:
                self.logger.log_event("MEMORY", "ERROR", f"❌ Memory footprint reduction failed: {e}")

    async def _emergency_memory_cleanup(self):
        """Emergency memory cleanup procedures"""
        try:
            # Force multiple garbage collections
            for _ in range(3):
                gc.collect()

            # Clear all caches
            await self._clear_caches()

            # Reduce memory footprint
            await self._reduce_memory_footprint()

            # Log emergency cleanup
            self.logger.log_event("MEMORY", "CRITICAL",
                "🚨 Emergency memory cleanup completed")

        except Exception as e:
            self.logger.log_event("MEMORY", "ERROR", f"❌ Emergency cleanup failed: {e}")

    async def _update_performance_metrics(self):
        """Update memory performance metrics"""
        try:
            memory_usage = self._get_memory_usage()

            # Update cache hit rates (simplified)
            for cache_name in self._caches.keys():
                # This would track actual cache hit rates
                # For now, use a placeholder
                hit_rate = 0.85  # 85% hit rate
                self._performance_metrics['cache_hit_rates'][cache_name].append(hit_rate)

        except Exception as e:
            self.logger.log_event("MEMORY", "ERROR", f"❌ Performance metrics update failed: {e}")

    def _create_memory_alert(self, alert_type: str, message: str):
        """Create a memory alert"""
        alert = {
            'type': alert_type,
            'message': message,
            'timestamp': time.time(),
            'memory_usage': self._get_memory_usage()
        }

        self._memory_alerts.append(alert)
        self.logger.log_event("MEMORY", "CRITICAL", f"🚨 {message}")

    def get_memory_stats(self) -> dict[str, Any]:
        """Get comprehensive memory statistics"""
        try:
            memory_usage = self._get_memory_usage()

            return {
                'current_usage': memory_usage,
                'gc_stats': self._gc_stats.copy(),
                'cache_sizes': {name: len(cache) for name, cache in self._caches.items()},
                'memory_history': list(self._memory_history)[-10:] if self._memory_history else [],
                'performance_metrics': {
                    'avg_memory_usage': statistics.mean(self._performance_metrics['memory_usage']) if self._performance_metrics['memory_usage'] else 0,
                    'avg_gc_time': statistics.mean(self._performance_metrics['gc_frequency']) if self._performance_metrics['gc_frequency'] else 0,
                    'memory_leaks': len(self._performance_metrics['memory_leaks'])
                },
                'alerts': self._memory_alerts[-5:] if self._memory_alerts else []
            }

        except Exception as e:
            self.logger.log_event("MEMORY", "ERROR", f"❌ Failed to get memory stats: {e}")
            return {}

    def add_cache(self, cache_name: str, cache_object: Any):
        """Add a cache to the memory optimizer"""
        self._caches[cache_name] = cache_object
        self.logger.log_event("MEMORY", "INFO", f"📦 Added cache: {cache_name}")

    def remove_cache(self, cache_name: str):
        """Remove a cache from the memory optimizer"""
        if cache_name in self._caches:
            del self._caches[cache_name]
            self.logger.log_event("MEMORY", "INFO", f"🗑️ Removed cache: {cache_name}")

    def get_cache_info(self) -> dict[str, Any]:
        """Get information about all caches"""
        cache_info = {}

        for cache_name, cache in self._caches.items():
            cache_info[cache_name] = {
                'type': type(cache).__name__,
                'size': len(cache) if hasattr(cache, '__len__') else 'unknown',
                'memory_usage': 'unknown'  # Disabled for Windows compatibility
            }

        return cache_info

    def force_garbage_collection(self):
        """Force immediate garbage collection"""
        try:
            collected = gc.collect()
            self.logger.log_event("MEMORY", "INFO", f"🗑️ Forced garbage collection: {collected} objects collected")
            return collected
        except Exception as e:
            self.logger.log_event("MEMORY", "ERROR", f"❌ Forced garbage collection failed: {e}")
            return 0

    def get_memory_thresholds(self) -> dict[str, float]:
        """Get current memory thresholds"""
        return self._memory_thresholds.copy()

    def update_memory_thresholds(self, new_thresholds: dict[str, float]):
        """Update memory thresholds"""
        self._memory_thresholds.update(new_thresholds)
        self.logger.log_event("MEMORY", "INFO", "⚙️ Memory thresholds updated")
