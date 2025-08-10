#!/usr/bin/env python3
"""
Simple Environment Manager for BinanceBot v2.1
No dependencies, just manage .env file
"""

from pathlib import Path


class SimpleEnvManager:
    """Simple manager for .env file operations"""

    def __init__(self, env_file: str = ".env"):
        self.env_file = Path(env_file)

    def load_env_file(self) -> dict[str, str]:
        """Load all variables from .env file"""
        env_vars = {}

        if not self.env_file.exists():
            print(f"⚠️ .env file not found: {self.env_file}")
            return env_vars

        try:
            with open(self.env_file, encoding="utf-8") as f:
                for _line_num, line in enumerate(f, 1):
                    line = line.strip()

                    # Skip empty lines and comments
                    if not line or line.startswith("#"):
                        continue

                    # Parse key=value
                    if "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip()

                        # Strip inline comments
                        if "#" in value:
                            value = value.split("#")[0].strip()

                        # Remove quotes if present
                        if (value.startswith('"') and value.endswith('"')) or (
                            value.startswith("'") and value.endswith("'")
                        ):
                            value = value[1:-1]

                        env_vars[key] = value

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

    def show_env_status(self):
        """Show current .env file status"""
        print("🔍 .env File Status:")
        print("=" * 40)

        if not self.env_file.exists():
            print("❌ .env file not found")
            return

        env_vars = self.load_env_file()

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

        # Show all variables
        print("\n📋 All variables:")
        for key, value in env_vars.items():
            if "KEY" in key or "SECRET" in key or "TOKEN" in key:
                print(f"   {key}: {'*' * len(value)}")
            else:
                print(f"   {key}: {value}")


def main():
    """Main function for testing"""
    print("🚀 Simple Environment Manager Test")
    print("=" * 40)

    manager = SimpleEnvManager()
    manager.show_env_status()


if __name__ == "__main__":
    main()
