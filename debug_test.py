#!/usr/bin/env python3
"""
Simple debug test
"""
import asyncio
import sys

print("🚀 Debug test starting...")
print(f"Python version: {sys.version}")

try:
    print("1. Testing basic imports...")
    import pandas as pd
    import numpy as np
    print("   ✅ Pandas and NumPy imported")
    
    print("2. Testing core imports...")
    from core.config import TradingConfig
    print("   ✅ TradingConfig imported")
    
    print("3. Testing logger...")
    from core.unified_logger import UnifiedLogger
    print("   ✅ UnifiedLogger imported")
    
    print("4. Testing strategy...")
    from strategies.scalping_v1 import ScalpingV1
    print("   ✅ ScalpingV1 imported")
    
    print("5. Testing async...")
    async def test_async():
        print("   ✅ Async function works")
        return "success"
    
    result = asyncio.run(test_async())
    print(f"   ✅ Async test result: {result}")
    
    print("✅ All tests passed!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc() 