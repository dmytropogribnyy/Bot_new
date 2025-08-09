#!/usr/bin/env python3
"""
Environment Manager for BinanceBot v2.1
Automatically manage .env file and transfer keys to configuration
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.config import TradingConfig


class EnvManager:
    """Manager for .env file operations and key transfer"""

    def __init__(self, env_file: str = ".env"):
        self.env_file = Path(env_file)
        self.config = TradingConfig()

    def load_env_file(self) -> dict[str, str]:
        """Load all variables from .env file"""
        env_vars = {}

        if not self.env_file.exists():
            print(f"⚠️ .env file not found: {self.env_file}")
            return env_vars

        try:
            with open(self.env_file, encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()

                    # Skip empty lines and comments
                    if not line or line.startswith("#"):
                        continue

                    # Parse key=value
                    if "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip()

                        # Remove quotes if present
                        if (value.startswith('"') and value.endswith('"')) or (
                            value.startswith("'") and value.endswith("'")
                        ):
                            value = value[1:-1]

                        env_vars[key] = value
                    else:
                        print(f"⚠️ Invalid line {line_num}: {line}")

            print(f"✅ Loaded {len(env_vars)} variables from {self.env_file}")
            return env_vars

        except Exception as e:
            print(f"❌ Error loading .env file: {e}")
            return env_vars

    def save_env_file(self, env_vars: dict[str, str], backup: bool = True):
        """Save variables to .env file"""
        try:
            # Create backup if requested
            if backup and self.env_file.exists():
                backup_file = self.env_file.with_suffix(".env.backup")
                with open(self.env_file, encoding="utf-8") as src:
                    with open(backup_file, "w", encoding="utf-8") as dst:
                        dst.write(src.read())
                print(f"✅ Backup created: {backup_file}")

            # Write new .env file
            with open(self.env_file, "w", encoding="utf-8") as f:
                for key, value in env_vars.items():
                    f.write(f"{key}={value}\n")

            print(f"✅ Saved {len(env_vars)} variables to {self.env_file}")

        except Exception as e:
            print(f"❌ Error saving .env file: {e}")

    def get_api_keys(self) -> tuple[str | None, str | None]:
        """Get Binance API keys from .env"""
        env_vars = self.load_env_file()

        api_key = env_vars.get("BINANCE_API_KEY") or env_vars.get("API_KEY")
        api_secret = env_vars.get("BINANCE_API_SECRET") or env_vars.get("API_SECRET")

        return api_key, api_secret

    def get_telegram_credentials(self) -> tuple[str | None, str | None]:
        """Get Telegram credentials from .env"""
        env_vars = self.load_env_file()

        token = env_vars.get("TELEGRAM_TOKEN")
        chat_id = env_vars.get("TELEGRAM_CHAT_ID")

        return token, chat_id

    def set_api_keys(self, api_key: str, api_secret: str):
        """Set Binance API keys in .env"""
        env_vars = self.load_env_file()

        env_vars["BINANCE_API_KEY"] = api_key
        env_vars["BINANCE_API_SECRET"] = api_secret

        self.save_env_file(env_vars)

    def set_telegram_credentials(self, token: str, chat_id: str):
        """Set Telegram credentials in .env"""
        env_vars = self.load_env_file()

        env_vars["TELEGRAM_TOKEN"] = token
        env_vars["TELEGRAM_CHAT_ID"] = chat_id

        self.save_env_file(env_vars)

    def transfer_keys_to_config(self) -> bool:
        """Transfer keys from .env to configuration"""
        try:
            env_vars = self.load_env_file()

            # Transfer API keys
            api_key = env_vars.get("BINANCE_API_KEY") or env_vars.get("API_KEY")
            api_secret = env_vars.get("BINANCE_API_SECRET") or env_vars.get("API_SECRET")

            if api_key and api_secret:
                self.config.api_key = api_key
                self.config.api_secret = api_secret
                print("✅ Transferred API keys to config")

            # Transfer Telegram credentials
            telegram_token = env_vars.get("TELEGRAM_TOKEN")
            telegram_chat_id = env_vars.get("TELEGRAM_CHAT_ID")

            if telegram_token and telegram_chat_id:
                self.config.telegram_token = telegram_token
                self.config.telegram_chat_id = telegram_chat_id
                print("✅ Transferred Telegram credentials to config")

            # Transfer other settings
            if "BINANCE_TESTNET" in env_vars:
                self.config.testnet = env_vars["BINANCE_TESTNET"].lower() == "true"

            if "DRY_RUN" in env_vars:
                self.config.dry_run = env_vars["DRY_RUN"].lower() == "true"

            if "LOG_LEVEL" in env_vars:
                self.config.log_level = env_vars["LOG_LEVEL"]

            # Save updated config
            self.config.save_to_file("data/config_updated.json")
            print("✅ Configuration updated and saved")

            return True

        except Exception as e:
            print(f"❌ Error transferring keys: {e}")
            return False

    def create_env_template(self):
        """Create .env template with all required variables"""
        template_vars = {
            "BINANCE_API_KEY": "your_api_key_here",
            "BINANCE_API_SECRET": "your_api_secret_here",
            "BINANCE_TESTNET": "true",
            "TELEGRAM_TOKEN": "your_telegram_bot_token",
            "TELEGRAM_CHAT_ID": "your_chat_id",
            "DRY_RUN": "true",
            "LOG_LEVEL": "INFO",
            "MAX_POSITIONS": "3",
            "MIN_POSITION_SIZE_USDT": "10.0",
            "STOP_LOSS_PERCENT": "2.0",
            "TAKE_PROFIT_PERCENT": "1.5",
        }

        self.save_env_file(template_vars, backup=False)
        print(f"✅ Created .env template with {len(template_vars)} variables")

    def validate_env_file(self) -> dict[str, list[str]]:
        """Validate .env file and return issues"""
        issues = {"missing": [], "invalid": [], "warnings": []}

        env_vars = self.load_env_file()

        # Check required variables
        required_vars = {
            "BINANCE_API_KEY": "Binance API Key",
            "BINANCE_API_SECRET": "Binance API Secret",
            "TELEGRAM_TOKEN": "Telegram Bot Token",
            "TELEGRAM_CHAT_ID": "Telegram Chat ID",
        }

        for var, description in required_vars.items():
            if var not in env_vars or not env_vars[var]:
                issues["missing"].append(f"{var} ({description})")
            elif env_vars[var] in [
                "your_api_key_here",
                "your_api_secret_here",
                "your_telegram_bot_token",
                "your_chat_id",
            ]:
                issues["warnings"].append(f"{var} has placeholder value")

        # Check for invalid values
        if "BINANCE_TESTNET" in env_vars:
            testnet_val = env_vars["BINANCE_TESTNET"].lower()
            if testnet_val not in ["true", "false"]:
                issues["invalid"].append("BINANCE_TESTNET should be 'true' or 'false'")

        if "DRY_RUN" in env_vars:
            dry_run_val = env_vars["DRY_RUN"].lower()
            if dry_run_val not in ["true", "false"]:
                issues["invalid"].append("DRY_RUN should be 'true' or 'false'")

        return issues

    def show_env_status(self):
        """Show current .env file status"""
        print("🔍 .env File Status:")
        print("=" * 40)

        if not self.env_file.exists():
            print("❌ .env file not found")
            return

        env_vars = self.load_env_file()
        issues = self.validate_env_file()

        print(f"📁 File: {self.env_file}")
        print(f"📊 Variables: {len(env_vars)}")

        # Show API keys status
        api_key, api_secret = self.get_api_keys()
        if api_key and api_secret:
            print("✅ API Keys: Configured")
        else:
            print("❌ API Keys: Missing")

        # Show Telegram status
        telegram_token, telegram_chat_id = self.get_telegram_credentials()
        if telegram_token and telegram_chat_id:
            print("✅ Telegram: Configured")
        else:
            print("❌ Telegram: Missing")

        # Show issues
        if issues["missing"]:
            print("\n❌ Missing variables:")
            for var in issues["missing"]:
                print(f"   - {var}")

        if issues["invalid"]:
            print("\n⚠️ Invalid values:")
            for var in issues["invalid"]:
                print(f"   - {var}")

        if issues["warnings"]:
            print("\n⚠️ Warnings:")
            for var in issues["warnings"]:
                print(f"   - {var}")

        if not any(issues.values()):
            print("\n✅ .env file is properly configured!")

    def update_config_from_env(self):
        """Update configuration from .env file"""
        print("🔄 Updating configuration from .env...")

        success = self.transfer_keys_to_config()

        if success:
            print("✅ Configuration updated successfully!")
            print("📊 Current config status:")
            print(f"   - API Keys: {'✅' if self.config.api_key else '❌'}")
            print(f"   - Telegram: {'✅' if self.config.is_telegram_enabled() else '❌'}")
            print(f"   - Testnet: {self.config.testnet}")
            print(f"   - Dry Run: {self.config.dry_run}")
        else:
            print("❌ Failed to update configuration")


def main():
    """Main function for testing"""
    print("🚀 Environment Manager Test")
    print("=" * 40)

    manager = EnvManager()

    # Show current status
    manager.show_env_status()

    # Update config from .env
    manager.update_config_from_env()

    print("\n" + "=" * 40)


if __name__ == "__main__":
    main()
