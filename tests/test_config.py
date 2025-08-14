# test_config.py - запустите это первым!
from core.config import TradingConfig

config = TradingConfig.from_env()
print("=" * 50)
print(f"🌐 TESTNET: {config.testnet}")
print(f"💰 DRY_RUN: {config.dry_run}")
print(f"📡 WEBSOCKET: {config.enable_websocket}")
print(f"📊 MAX_POSITIONS: {config.max_positions}")
print(f"📊 MAX_CONCURRENT: {config.max_concurrent_positions}")
print(f"💵 DEPOSIT: {config.trading_deposit}")
print(f"💹 DYNAMIC_BALANCE: {config.use_dynamic_balance}")
print(f"📉 STOP_LOSS: {config.stop_loss_percent}%")
print(f"📈 TAKE_PROFIT: {config.take_profit_percent}%")
print(f"⏱️ COOLDOWN: {config.entry_cooldown_seconds}s")
print(f"🔢 HOURLY_LIMIT: {config.max_hourly_trade_limit}")
print("=" * 50)

# Должно показать:
# TESTNET: True
# DRY_RUN: False
# WEBSOCKET: True
# DYNAMIC_BALANCE: False
