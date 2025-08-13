#!/usr/bin/env python3
"""Test .env synchronization with .env.example"""

import sys
from pathlib import Path

import pytest

try:
    from dotenv import dotenv_values
except Exception as e:
    print(f"❌ python-dotenv not installed: {e}")
    dotenv_values = None


def test_env_sync():
    """Check .env has all keys from .env.example"""

    root = Path(__file__).parent.parent
    env_path = root / ".env"
    example_path = root / ".env.example"

    if dotenv_values is None:
        pytest.skip("python-dotenv not installed")

    # Check files exist
    if not example_path.exists():
        pytest.skip(".env.example not found")

    if not env_path.exists():
        pytest.skip(".env not found")

    # Load both files
    env_vars = dotenv_values(str(env_path))
    example_vars = dotenv_values(str(example_path))

    # Check for missing keys
    missing: list[str] = []
    for key in example_vars:
        if key not in env_vars:
            missing.append(key)

    # Check for extra keys
    extra: list[str] = []
    for key in env_vars:
        if key not in example_vars:
            extra.append(key)

    # Report results
    if missing:
        print(f"❌ Missing in .env: {', '.join(missing)}")
        print(
            "   Add these to .env or run: python -c 'from core.env_editor import EnvEditor; EnvEditor().sync_from_example()'"
        )

    if extra:
        print(f"⚠️  Extra in .env (not in .env.example): {', '.join(extra)}")
        print("   Consider adding to .env.example if needed")

    assert not missing, "Missing keys in .env"
    print("✅ All required env vars present")


def test_env_loading():
    """Test that config can load from env"""
    try:
        from core.config import TradingConfig

        config = TradingConfig.from_env()
        print(f"✅ Config loaded: {len(config.model_dump())} fields")
        assert isinstance(config, TradingConfig)
        assert len(config.model_dump()) > 0
    except Exception as e:
        print(f"❌ Config loading failed: {e}")
        pytest.fail(f"Config loading failed: {e}")


if __name__ == "__main__":
    print("Testing .env synchronization...")
    print("=" * 50)

    sync_ok = test_env_sync()
    load_ok = test_env_loading()

    if sync_ok and load_ok:
        print("\n✅ All env tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed")
        sys.exit(1)
