#!/usr/bin/env python3
"""
Key Management Script for BinanceBot v2.1
Quick and easy management of API keys and settings
"""

from pathlib import Path
import sys

from env_manager import EnvManager


def show_help():
    """Show help information"""
    print("🔑 Key Management Script")
    print("=" * 40)
    print("Usage: python manage_keys.py [command] [options]")
    print("\nCommands:")
    print("  status          - Show current .env status")
    print("  update          - Update config from .env")
    print("  set-api         - Set Binance API keys")
    print("  set-telegram    - Set Telegram credentials")
    print("  set-var K V     - Set arbitrary .env variable")
    print("  get-var K       - Get .env variable (sanitized)")
    print("  print           - Print sanitized .env contents")
    print("  switch PROFILE  - Switch .env <- .env.PROFILE (e.g., prod/testnet)")
    print("  template        - Create .env template")
    print("  validate        - Validate .env file")
    print("  help            - Show this help")
    print("\nExamples:")
    print("  python manage_keys.py status")
    print("  python manage_keys.py set-api YOUR_KEY YOUR_SECRET")
    print("  python manage_keys.py set-telegram YOUR_TOKEN YOUR_CHAT_ID")
    print("  python manage_keys.py update")


def set_api_keys():
    """Set Binance API keys"""
    if len(sys.argv) < 4:
        print("❌ Usage: python manage_keys.py set-api <api_key> <api_secret>")
        return

    api_key = sys.argv[2]
    api_secret = sys.argv[3]

    manager = EnvManager()
    manager.set_api_keys(api_key, api_secret)

    print("✅ API keys set successfully!")
    print("🔄 Updating configuration...")
    manager.update_config_from_env()


def set_telegram_credentials():
    """Set Telegram credentials"""
    if len(sys.argv) < 4:
        print("❌ Usage: python manage_keys.py set-telegram <token> <chat_id>")
        return

    token = sys.argv[2]
    chat_id = sys.argv[3]

    manager = EnvManager()
    manager.set_telegram_credentials(token, chat_id)

    print("✅ Telegram credentials set successfully!")
    print("🔄 Updating configuration...")
    manager.update_config_from_env()


def show_status():
    """Show current status"""
    manager = EnvManager()
    manager.show_env_status()


def _sanitize(key: str, value: str) -> str:
    """Redact sensitive values for display."""
    if value is None:
        return ""
    k = key.lower()
    if any(x in k for x in ["secret", "key", "token", "password"]):
        return value[:4] + "…" + value[-4:] if len(value) > 8 else "****"
    return value


def set_var():
    """Set arbitrary .env variable: set-var KEY VALUE"""
    if len(sys.argv) < 4:
        print("❌ Usage: python manage_keys.py set-var <KEY> <VALUE>")
        return
    key, value = sys.argv[2], sys.argv[3]
    manager = EnvManager()
    env_vars = manager.load_env_file()
    env_vars[key] = value
    manager.save_env_file(env_vars)
    print(f"✅ Set {key}={_sanitize(key, value)}")


def get_var():
    """Get .env variable (sanitized): get-var KEY"""
    if len(sys.argv) < 3:
        print("❌ Usage: python manage_keys.py get-var <KEY>")
        return
    key = sys.argv[2]
    manager = EnvManager()
    env_vars = manager.load_env_file()
    if key in env_vars:
        print(f"{key}={_sanitize(key, env_vars[key])}")
    else:
        print(f"❌ {key} not found in .env")


def print_env():
    """Print sanitized .env contents"""
    manager = EnvManager()
    env_vars = manager.load_env_file()
    if not env_vars:
        print("(empty or missing .env)")
        return
    for k in sorted(env_vars.keys()):
        print(f"{k}={_sanitize(k, env_vars[k])}")


def switch_profile():
    """Switch .env from .env.<profile> (e.g., testnet/prod)"""
    if len(sys.argv) < 3:
        print("❌ Usage: python manage_keys.py switch <profile>")
        return
    import shutil

    profile = sys.argv[2].strip()
    src = Path(f".env.{profile}")
    dst = Path(".env")
    if not src.exists():
        print(f"❌ Profile file not found: {src}")
        return
    shutil.copyfile(src, dst)
    print(f"✅ Switched .env <- {src}")
    # Optionally update config
    manager = EnvManager()
    manager.update_config_from_env()


def update_config():
    """Update configuration from .env"""
    manager = EnvManager()
    manager.update_config_from_env()


def create_template():
    """Create .env template"""
    manager = EnvManager()
    manager.create_env_template()


def validate_env():
    """Validate .env file"""
    manager = EnvManager()
    issues = manager.validate_env_file()

    print("🔍 .env File Validation:")
    print("=" * 30)

    if not any(issues.values()):
        print("✅ .env file is valid!")
        return

    if issues["missing"]:
        print("❌ Missing required variables:")
        for var in issues["missing"]:
            print(f"   - {var}")

    if issues["invalid"]:
        print("⚠️ Invalid values:")
        for var in issues["invalid"]:
            print(f"   - {var}")

    if issues["warnings"]:
        print("⚠️ Warnings:")
        for var in issues["warnings"]:
            print(f"   - {var}")


def main():
    """Main function"""
    if len(sys.argv) < 2:
        show_help()
        return

    command = sys.argv[1].lower()

    if command == "help":
        show_help()
    elif command == "status":
        show_status()
    elif command == "update":
        update_config()
    elif command == "set-api":
        set_api_keys()
    elif command == "set-telegram":
        set_telegram_credentials()
    elif command == "template":
        create_template()
    elif command == "validate":
        validate_env()
    else:
        print(f"❌ Unknown command: {command}")
        show_help()


if __name__ == "__main__":
    main()
