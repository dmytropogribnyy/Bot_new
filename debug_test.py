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
    print("   ✅ Pandas and NumPy imported")

    print("2. Testing core imports...")
    print("   ✅ TradingConfig imported")

    print("3. Testing logger...")
    print("   ✅ UnifiedLogger imported")

    print("4. Testing strategy...")
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
