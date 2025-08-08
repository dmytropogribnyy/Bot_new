#!/usr/bin/env python3
"""
Test Windows Compatibility
"""

import core.windows_compatibility
from core.memory_optimizer import MemoryOptimizer
from core.post_run_analyzer import PostRunAnalyzer
from core.exchange_client import ExchangeClient
from core.config import TradingConfig
from core.unified_logger import UnifiedLogger

def test_windows_compatibility():
    """Test that all components work without Windows compatibility errors"""
    print("🔧 Testing Windows compatibility...")

    # Test Windows compatibility module
    assert core.windows_compatibility.IS_WINDOWS == True
    assert core.windows_compatibility.is_windows_compatibility_error("module 'sys' has no attribute 'builtin_module_names'") == True
    assert core.windows_compatibility.is_windows_compatibility_error("normal error") == False

    print("✅ Windows compatibility module works")

    # Test memory optimizer
    try:
        config = TradingConfig()
        logger = UnifiedLogger(config)
        memory_optimizer = MemoryOptimizer(config, logger)
        print("✅ Memory optimizer initialized")
    except Exception as e:
        print(f"❌ Memory optimizer error: {e}")
        return False

    # Test post run analyzer
    try:
        analyzer = PostRunAnalyzer(logger, config)
        print("✅ Post run analyzer initialized")
    except Exception as e:
        print(f"❌ Post run analyzer error: {e}")
        return False

    # Test exchange client (without API keys)
    try:
        exchange_client = ExchangeClient(config, logger)
        print("✅ Exchange client initialized")
    except Exception as e:
        print(f"❌ Exchange client error: {e}")
        return False

    print("🎉 All components work without Windows compatibility errors!")
    return True

if __name__ == "__main__":
    test_windows_compatibility()
