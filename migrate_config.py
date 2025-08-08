#!/usr/bin/env python3
"""
Configuration Migration Script
Migrate old configuration files to new unified system
"""

import json
import os
from pathlib import Path
from typing import Dict, Any

from core.config import TradingConfig


def migrate_runtime_config():
    """Migrate runtime_config.json to new format"""
    try:
        old_config_path = Path("data/runtime_config.json")
        if not old_config_path.exists():
            print("⚠️ No runtime_config.json found to migrate")
            return

        with open(old_config_path, 'r', encoding='utf-8') as f:
            old_config = json.load(f)

        print(f"📋 Found {len(old_config)} settings in runtime_config.json")

        # Create new config with old values
        new_config = TradingConfig()

        # Map old keys to new config
        key_mapping = {
            'max_concurrent_positions': 'max_concurrent_positions',
            'risk_multiplier': 'risk_multiplier',
            'base_risk_pct': 'base_risk_pct',
            'min_risk_factor': 'min_risk_factor',
            'atr_threshold_percent': 'atr_threshold_percent',
            'volume_threshold_usdc': 'volume_threshold_usdc',
            'rel_volume_threshold': 'rel_volume_threshold',
            'rsi_threshold': 'rsi_threshold',
            'min_macd_strength': 'min_macd_strength',
            'min_rsi_strength': 'min_rsi_strength',
            'macd_strength_override': 'macd_strength_override',
            'rsi_strength_override': 'rsi_strength_override',
            'step_tp_levels': 'step_tp_levels',
            'step_tp_sizes': 'step_tp_sizes',
            'min_sl_gap_percent': 'min_sl_gap_percent',
            'SL_PERCENT': 'sl_percent',
            'FORCE_SL_ALWAYS': 'force_sl_always',
            'sl_retry_limit': 'sl_retry_limit',
            'auto_profit_enabled': 'auto_profit_enabled',
            'auto_profit_threshold': 'auto_profit_threshold',
            'bonus_profit_threshold': 'bonus_profit_threshold',
            'max_hold_minutes': 'max_hold_minutes',
            'min_profit_threshold': 'min_profit_threshold',
            'MIN_NOTIONAL_OPEN': 'min_notional_open',
            'MIN_NOTIONAL_ORDER': 'min_notional_order',
            'min_trade_qty': 'min_trade_qty',
            'min_total_qty_for_tp_full': 'min_total_qty_for_tp_full',
            'max_hourly_trade_limit': 'max_hourly_trade_limit',
            'max_capital_utilization_pct': 'max_capital_utilization_pct',
            'max_margin_percent': 'max_margin_percent',
            'max_slippage_pct': 'max_slippage_pct',
            'min_primary_score': 'min_primary_score',
            'min_secondary_score': 'min_secondary_score',
            'enable_strong_signal_override': 'enable_strong_signal_override',
            'require_closed_candle_for_entry': 'require_closed_candle_for_entry',
            'monitoring_hours_utc': 'monitoring_hours_utc'
        }

        migrated_count = 0
        for old_key, new_key in key_mapping.items():
            if old_key in old_config and hasattr(new_config, new_key):
                old_value = old_config[old_key]
                setattr(new_config, new_key, old_value)
                migrated_count += 1
                print(f"✅ Migrated: {old_key} -> {new_key} = {old_value}")

        # Save migrated config
        new_config.save_to_file("data/runtime_config_migrated.json")
        print(f"🎉 Successfully migrated {migrated_count} settings")

        return new_config

    except Exception as e:
        print(f"❌ Error migrating runtime_config.json: {e}")
        return None


def migrate_config_json():
    """Migrate config.json to new format"""
    try:
        old_config_path = Path("data/config.json")
        if not old_config_path.exists():
            print("⚠️ No config.json found to migrate")
            return

        with open(old_config_path, 'r', encoding='utf-8') as f:
            old_config = json.load(f)

        print(f"📋 Found {len(old_config)} settings in config.json")

        # Create new config with old values
        new_config = TradingConfig()

        # Map old keys to new config
        key_mapping = {
            'api_key': 'api_key',
            'api_secret': 'api_secret',
            'testnet': 'testnet',
            'dry_run': 'dry_run',
            'telegram_enabled': 'telegram_enabled',
            'telegram_token': 'telegram_token',
            'telegram_chat_id': 'telegram_chat_id',
            'max_positions': 'max_positions',
            'position_size_usdc': 'min_position_size_usdt',
            'target_profit_percent': 'take_profit_percent',
            'stop_loss_percent': 'stop_loss_percent',
            'max_hold_minutes': 'max_hold_minutes',
            'log_level': 'log_level',
            'db_path': 'db_path',
            'volume_threshold': 'volume_threshold',
            'min_signal_strength': 'signal_threshold',
            'macd_strength_override': 'macd_strength_override',
            'rsi_strength_override': 'rsi_strength_override'
        }

        migrated_count = 0
        for old_key, new_key in key_mapping.items():
            if old_key in old_config and hasattr(new_config, new_key):
                old_value = old_config[old_key]
                setattr(new_config, new_key, old_value)
                migrated_count += 1
                print(f"✅ Migrated: {old_key} -> {new_key} = {old_value}")

        # Save migrated config
        new_config.save_to_file("data/config_migrated.json")
        print(f"🎉 Successfully migrated {migrated_count} settings")

        return new_config

    except Exception as e:
        print(f"❌ Error migrating config.json: {e}")
        return None


def migrate_leverage_config():
    """Migrate leverage configuration"""
    try:
        # Import old leverage config
        try:
            from common.leverage_config import LEVERAGE_MAP
            print(f"📋 Found {len(LEVERAGE_MAP)} leverage settings")

            # Create new config
            new_config = TradingConfig()
            new_config.leverage_map = LEVERAGE_MAP.copy()

            # Save migrated config
            new_config.save_to_file("data/leverage_migrated.json")
            print(f"🎉 Successfully migrated {len(LEVERAGE_MAP)} leverage settings")

            return new_config

        except ImportError:
            print("⚠️ No leverage_config.py found to migrate")
            return None

    except Exception as e:
        print(f"❌ Error migrating leverage config: {e}")
        return None


def create_unified_config():
    """Create unified configuration from all sources"""
    try:
        print("🔄 Creating unified configuration...")

        # Start with default config
        unified_config = TradingConfig()

        # Migrate from all sources
        runtime_config = migrate_runtime_config()
        config_json = migrate_config_json()
        leverage_config = migrate_leverage_config()

        # Merge configurations (runtime_config has highest priority)
        if runtime_config:
            for key, value in runtime_config.model_dump().items():
                if hasattr(unified_config, key):
                    setattr(unified_config, key, value)

        if config_json:
            for key, value in config_json.model_dump().items():
                if hasattr(unified_config, key):
                    setattr(unified_config, key, value)

        if leverage_config:
            unified_config.leverage_map = leverage_config.leverage_map

        # Save unified config
        unified_config.save_to_file("data/unified_config.json")
        print("✅ Unified configuration created successfully")

        return unified_config

    except Exception as e:
        print(f"❌ Error creating unified config: {e}")
        return None


def backup_old_configs():
    """Backup old configuration files"""
    try:
        backup_dir = Path("data/backup")
        backup_dir.mkdir(exist_ok=True)

        files_to_backup = [
            "data/runtime_config.json",
            "data/config.json",
            "common/config_loader.py",
            "common/leverage_config.py"
        ]

        for file_path in files_to_backup:
            if Path(file_path).exists():
                backup_path = backup_dir / Path(file_path).name
                with open(file_path, 'r', encoding='utf-8') as src:
                    with open(backup_path, 'w', encoding='utf-8') as dst:
                        dst.write(src.read())
                print(f"✅ Backed up: {file_path}")

        print("🎉 All old configs backed up successfully")

    except Exception as e:
        print(f"❌ Error backing up configs: {e}")


def main():
    """Main migration function"""
    print("🚀 Starting Configuration Migration...")
    print("=" * 50)

    # Backup old configs
    backup_old_configs()

    # Create unified config
    unified_config = create_unified_config()

    if unified_config:
        print("\n📊 Migration Summary:")
        print(f"✅ Telegram enabled: {unified_config.is_telegram_enabled()}")
        print(f"✅ Testnet mode: {unified_config.testnet}")
        print(f"✅ Dry run mode: {unified_config.dry_run}")
        print(f"✅ Max positions: {unified_config.max_positions}")
        print(f"✅ Leverage symbols: {len(unified_config.leverage_map)}")
        print(f"✅ USDC symbols: {len(unified_config.usdc_symbols)}")
        print(f"✅ USDT symbols: {len(unified_config.usdt_symbols)}")

        print("\n🎉 Migration completed successfully!")
        print("📁 Check data/unified_config.json for the new configuration")
    else:
        print("\n❌ Migration failed!")

    print("=" * 50)


if __name__ == "__main__":
    main()
