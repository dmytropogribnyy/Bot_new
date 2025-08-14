#!/usr/bin/env python3
"""
Переключение между testnet и production конфигурациями
"""

import shutil
import sys
from pathlib import Path


def switch_to_testnet():
    """Переключить на testnet"""
    # Копируем .env файлы
    shutil.copy(".env.testnet", ".env")
    shutil.copy("runtime_config.testnet.json", "data/runtime_config.json")
    print("✅ Switched to TESTNET")
    print("   .env.testnet → .env")
    print("   runtime_config.testnet.json → data/runtime_config.json")


def switch_to_production():
    """Переключить на production"""
    # Копируем .env файлы
    shutil.copy(".env.production", ".env")
    shutil.copy("runtime_config.prod.json", "data/runtime_config.json")
    print("✅ Switched to PRODUCTION")
    print("   .env.production → .env")
    print("   runtime_config.prod.json → data/runtime_config.json")


def check_current_mode():
    """Проверить текущий режим"""
    env_file = Path(".env")
    if not env_file.exists():
        print("❌ .env file not found!")
        return

    with open(env_file) as f:
        content = f.read()

    if "BINANCE_TESTNET=true" in content:
        mode = "TESTNET"
    elif "BINANCE_TESTNET=false" in content:
        mode = "PRODUCTION"
    else:
        mode = "UNKNOWN"

    print(f"📊 Current mode: {mode}")


def main():
    if len(sys.argv) != 2:
        print("Usage:")
        print("  python switch_env.py testnet    - Switch to testnet")
        print("  python switch_env.py production - Switch to production")
        print("  python switch_env.py check      - Check current mode")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "testnet":
        switch_to_testnet()
    elif command in ["production", "prod"]:
        switch_to_production()
    elif command == "check":
        check_current_mode()
    else:
        print(f"❌ Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
