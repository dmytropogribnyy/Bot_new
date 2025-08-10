#!/usr/bin/env python3
"""
Configuration system for BinanceBot v2.1
Unified configuration with leverage mapping and simplified loading
"""

import json
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class TradingConfig(BaseModel):
    """Main configuration class for the trading bot"""

    # API Configuration
    api_key: str = Field(default="", description="Binance API Key")
    api_secret: str = Field(default="", description="Binance API Secret")
    testnet: bool = Field(default=True, description="Use testnet for testing")

    # Trading Parameters
    max_positions: int = Field(default=3, description="Maximum concurrent positions")
    min_position_size_usdt: float = Field(default=10.0, description="Minimum position size in USDT")
    max_position_size_usdt: float = Field(default=100.0, description="Maximum position size in USDT")
    default_leverage: int = Field(default=5, description="Default leverage for positions")

    # Risk Management
    stop_loss_percent: float = Field(default=2.0, description="Default stop loss percentage")
    take_profit_percent: float = Field(default=1.5, description="Default take profit percentage")
    max_daily_loss: float = Field(default=50.0, description="Maximum daily loss in USDT")
    max_drawdown_percent: float = Field(default=10.0, description="Maximum drawdown percentage")

    # Strategy Settings
    strategy_name: str = Field(default="scalping_v1", description="Active strategy name")
    signal_threshold: float = Field(default=0.6, description="Minimum signal strength")
    volume_threshold: float = Field(default=1000000, description="Minimum 24h volume in USDT")

    # Logging Configuration
    log_level: str = Field(default="DEBUG", description="Logging level")
    log_to_file: bool = Field(default=True, description="Log to file")
    log_to_console: bool = Field(default=True, description="Log to console")
    log_to_telegram: bool = Field(default=True, description="Log to Telegram")
    max_log_size_mb: int = Field(default=100, description="Maximum log file size in MB")
    log_retention_days: int = Field(default=30, description="Log retention in days")

    # Telegram Configuration
    telegram_token: str = Field(default="", description="Telegram bot token")
    telegram_chat_id: str = Field(default="", description="Telegram chat ID")
    telegram_enabled: bool = Field(default=True, description="Enable Telegram notifications")

    # Database Configuration
    db_path: str = Field(default="data/trading_bot.db", description="SQLite database path")

    # WebSocket Configuration
    ws_reconnect_interval: int = Field(default=5, description="WebSocket reconnect interval in seconds")
    ws_heartbeat_interval: int = Field(default=30, description="WebSocket heartbeat interval in seconds")

    # Performance Settings
    update_interval: float = Field(default=1.0, description="Main loop update interval in seconds")
    symbol_rotation_interval: int = Field(default=300, description="Symbol rotation interval in seconds")

    # Emergency Settings
    emergency_stop_enabled: bool = Field(default=True, description="Enable emergency stop")
    emergency_stop_loss: float = Field(default=5.0, description="Emergency stop loss percentage")

    # Dry Run Mode
    dry_run: bool = Field(default=True, description="Enable dry run mode (no real trades)")

    # Leverage Configuration
    leverage_map: dict[str, int] = Field(
        default_factory=lambda: {
            "BTCUSDT": 5,
            "ETHUSDT": 5,
            "BTCUSDC": 5,
            "ETHUSDC": 5,
            "DOGEUSDC": 12,
            "XRPUSDC": 12,
            "ADAUSDC": 10,
            "SOLUSDC": 6,
            "BNBUSDC": 5,
            "LINKUSDC": 8,
            "ARBUSDC": 6,
            "SUIUSDC": 6,
            "MATICUSDC": 10,
            "DOTUSDC": 8,
        },
        description="Leverage mapping for symbols",
    )

    # Trading Symbols
    usdt_symbols: list = Field(default=["BTC/USDT"], description="USDT trading pairs")
    usdc_symbols: list = Field(
        default=[
            "BTC/USDC",
            "ETH/USDC",
            "XRP/USDC",
            "ADA/USDC",
            "SOL/USDC",
            "BNB/USDC",
            "LINK/USDC",
            "ARB/USDC",
            "DOGE/USDC",
            "SUI/USDC",
        ],
        description="USDC trading pairs",
    )

    # Advanced Trading Settings
    max_concurrent_positions: int = Field(default=3, description="Maximum concurrent positions")
    risk_multiplier: float = Field(default=1.5, description="Risk multiplier")
    base_risk_pct: float = Field(default=0.06, description="Base risk percentage")
    min_risk_factor: float = Field(default=0.8, description="Minimum risk factor")
    atr_threshold_percent: float = Field(default=0.0006, description="ATR threshold")
    volume_threshold_usdc: float = Field(default=20000, description="Volume threshold in USDC")
    rel_volume_threshold: float = Field(default=0.15, description="Relative volume threshold")
    rsi_threshold: int = Field(default=20, description="RSI threshold")
    min_macd_strength: float = Field(default=0.00025, description="Minimum MACD strength")
    min_rsi_strength: float = Field(default=2.5, description="Minimum RSI strength")
    macd_strength_override: float = Field(default=0.5, description="MACD strength override")
    rsi_strength_override: float = Field(default=4.0, description="RSI strength override")

    # TP/SL Settings
    step_tp_levels: list = Field(default=[0.004, 0.008, 0.012], description="Step TP levels")
    step_tp_sizes: list = Field(default=[0.5, 0.3, 0.2], description="Step TP sizes")
    min_sl_gap_percent: float = Field(default=0.005, description="Minimum SL gap")
    sl_percent: float = Field(default=0.012, description="Stop loss percentage")
    force_sl_always: bool = Field(default=True, description="Force SL always")
    sl_retry_limit: int = Field(default=3, description="SL retry limit")

    # Auto Profit Settings
    auto_profit_enabled: bool = Field(default=True, description="Auto profit enabled")
    auto_profit_threshold: float = Field(default=0.5, description="Auto profit threshold")
    bonus_profit_threshold: float = Field(default=2.0, description="Bonus profit threshold")
    max_hold_minutes: int = Field(default=10, description="Maximum hold time")
    min_profit_threshold: float = Field(default=0.06, description="Minimum profit threshold")
    entry_cooldown_seconds: int = Field(default=300, description="Cooldown between entries on same symbol")

    # Order Settings
    min_notional_open: float = Field(default=15.0, description="Minimum notional for opening")
    min_notional_order: float = Field(default=5.0, description="Minimum notional for orders")
    min_trade_qty: float = Field(default=0.001, description="Minimum trade quantity")
    min_total_qty_for_tp_full: float = Field(default=0.002, description="Minimum total quantity for TP")

    # Limits and Safety
    max_hourly_trade_limit: int = Field(default=15, description="Maximum hourly trades")
    max_capital_utilization_pct: float = Field(default=0.8, description="Maximum capital utilization")
    max_margin_percent: float = Field(default=0.4, description="Maximum margin percentage")
    max_slippage_pct: float = Field(default=0.02, description="Maximum slippage")

    # Signal Settings
    min_primary_score: int = Field(default=1, description="Minimum primary score")
    min_secondary_score: int = Field(default=1, description="Minimum secondary score")
    enable_strong_signal_override: bool = Field(default=True, description="Enable strong signal override")
    require_closed_candle_for_entry: bool = Field(default=False, description="Require closed candle for entry")

    # Monitoring Hours (UTC)
    monitoring_hours_utc: list = Field(default=list(range(24)), description="Monitoring hours UTC")

    # === Stage D additions (add at the end) ===
    working_type: Literal["MARK_PRICE", "CONTRACT_PRICE"] = "MARK_PRICE"
    tp_order_style: Literal["limit", "market"] = "limit"

    # === Stage F additions (global daily guard) ===
    max_sl_streak: int = Field(default=3, description="Maximum consecutive stop-losses per day before blocking entries")
    daily_drawdown_pct: float = Field(default=3.0, description="Daily loss percent threshold to block new entries")
    enable_stage_f_guard: bool = Field(default=True, description="Enable Stage F global daily guard")
    stage_f_state_path: str = Field(
        default="data/runtime/stage_f_state.json", description="Path to persist Stage F state"
    )

    # === Stage B: Unified Config - from_env loader ===
    @classmethod
    def from_env(cls) -> "TradingConfig":
        """Load configuration from environment variables (unified mapping).

        Note: This is additive and does not remove existing file/env loaders.
        """

        def env_bool(key: str, default: bool) -> bool:
            val = os.getenv(key)
            if val is None:
                return default
            return str(val).strip().lower() in ("true", "1", "yes", "on")

        def _clean_str(v: str) -> str:
            v = v.split("#", 1)[0]
            v = v.split(";", 1)[0]
            return v.strip()

        def env_int(key: str, default: int) -> int:
            val = os.getenv(key)
            if val is None:
                return default
            try:
                return int(_clean_str(val))
            except Exception:
                return default

        def env_float(key: str, default: float) -> float:
            val = os.getenv(key)
            if val is None:
                return default
            try:
                return float(_clean_str(val))
            except Exception:
                return default

        def env_str(key: str, default: str) -> str:
            val = os.getenv(key)
            return _clean_str(val) if val is not None else default

        def env_list_float(key: str, default: list[float]) -> list[float]:
            val = os.getenv(key)
            if not val:
                return default
            try:
                cleaned = _clean_str(val)
                return [float(x.strip()) for x in cleaned.split(",") if x.strip()]
            except Exception:
                return default

        return cls(
            # API
            api_key=env_str("API_KEY", os.getenv("BINANCE_API_KEY", "") or ""),
            api_secret=env_str("API_SECRET", os.getenv("BINANCE_API_SECRET", "") or ""),
            testnet=env_bool("TESTNET", str(os.getenv("BINANCE_TESTNET", "true")).lower() == "true"),
            dry_run=env_bool("DRY_RUN", False),
            # Stage D
            working_type=os.getenv("WORKING_TYPE", getattr(cls, "working_type", "MARK_PRICE")),
            tp_order_style=os.getenv("TP_ORDER_STYLE", getattr(cls, "tp_order_style", "limit")),
            # Stage F
            max_sl_streak=env_int("MAX_SL_STREAK", getattr(cls, "max_sl_streak", 3)),
            daily_drawdown_pct=env_float("DAILY_DRAWDOWN_PCT", getattr(cls, "daily_drawdown_pct", 3.0)),
            enable_stage_f_guard=env_bool("ENABLE_STAGE_F_GUARD", True),
            stage_f_state_path=env_str("STAGE_F_STATE_PATH", "data/runtime/stage_f_state.json"),
            # Trading
            default_leverage=env_int("LEVERAGE_DEFAULT", getattr(cls, "default_leverage", 5)),
            min_position_size_usdt=env_float("MIN_POSITION_SIZE_USDT", getattr(cls, "min_position_size_usdt", 10.0)),
            max_position_size_usdt=env_float("MAX_POSITION_SIZE_USDT", getattr(cls, "max_position_size_usdt", 100.0)),
            max_concurrent_positions=env_int("MAX_CONCURRENT_POSITIONS", getattr(cls, "max_concurrent_positions", 3)),
            # Risk
            max_capital_utilization_pct=env_float(
                "MAX_CAPITAL_UTILIZATION_PCT", getattr(cls, "max_capital_utilization_pct", 0.8)
            ),
            max_margin_percent=env_float("MAX_MARGIN_PERCENT", getattr(cls, "max_margin_percent", 0.4)),
            max_slippage_pct=env_float("MAX_SLIPPAGE_PCT", getattr(cls, "max_slippage_pct", 0.02)),
            risk_multiplier=env_float("RISK_MULTIPLIER", getattr(cls, "risk_multiplier", 1.0)),
            # TP/SL
            take_profit_percent=env_float("TAKE_PROFIT_PERCENT", getattr(cls, "take_profit_percent", 1.5)),
            stop_loss_percent=env_float("STOP_LOSS_PERCENT", getattr(cls, "stop_loss_percent", 2.0)),
            step_tp_levels=env_list_float("STEP_TP_LEVELS", getattr(cls, "step_tp_levels", [0.004, 0.008, 0.012])),
            step_tp_sizes=env_list_float("STEP_TP_SIZES", getattr(cls, "step_tp_sizes", [0.5, 0.3, 0.2])),
            # Telegram
            telegram_enabled=env_bool("TELEGRAM_ENABLED", getattr(cls, "telegram_enabled", False)),
            telegram_token=env_str("TELEGRAM_BOT_TOKEN", os.getenv("TELEGRAM_TOKEN", "") or ""),
            telegram_chat_id=env_str("TELEGRAM_CHAT_ID", ""),
            # Logging
            log_level=env_str("LOG_LEVEL", getattr(cls, "log_level", "INFO")),
            log_to_file=env_bool("LOG_TO_FILE", getattr(cls, "log_to_file", True)),
            log_to_console=env_bool("LOG_TO_CONSOLE", getattr(cls, "log_to_console", True)),
            # WebSocket
            ws_reconnect_interval=env_int("WS_RECONNECT_INTERVAL", getattr(cls, "ws_reconnect_interval", 5)),
            ws_heartbeat_interval=env_int("WS_HEARTBEAT_INTERVAL", getattr(cls, "ws_heartbeat_interval", 30)),
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def __init__(self, **data):
        # Load .env file manually
        self._load_env_manually()

        super().__init__(**data)
        self._load_from_file()
        self._load_from_env()

    def _load_env_manually(self):
        """Manually load .env file if python-dotenv is not available"""
        try:
            # Try to use SimpleEnvManager if available
            try:
                from simple_env_manager import SimpleEnvManager

                manager = SimpleEnvManager()
                env_vars = manager.load_env_file()

                # Set environment variables
                for key, value in env_vars.items():
                    os.environ[key] = value

                print(f"✅ Loaded {len(env_vars)} variables using SimpleEnvManager")

            except ImportError:
                # Fallback to manual loading
                env_file = Path(".env")
                if env_file.exists():
                    with open(env_file, encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#") and "=" in line:
                                key, value = line.split("=", 1)
                                os.environ[key.strip()] = value.strip()
                    print("✅ Loaded .env file manually")

        except Exception as e:
            print(f"Warning: Could not load .env file: {e}")

    def _load_from_file(self):
        """Load configuration from file"""
        config_files = ["data/runtime_config.json", "data/config.json", "config.json"]

        for config_file in config_files:
            if Path(config_file).exists():
                try:
                    with open(config_file, encoding="utf-8") as f:
                        file_config = json.load(f)

                    # Update only non-empty values
                    for key, value in file_config.items():
                        if value and hasattr(self, key):
                            setattr(self, key, value)

                    print(f"Loaded configuration from {config_file}")
                    break
                except Exception as e:
                    print(f"Failed to load config from {config_file}: {e}")

    def _load_from_env(self):
        """Load configuration from environment variables"""
        env_mapping = {
            "BINANCE_API_KEY": "api_key",
            "BINANCE_API_SECRET": "api_secret",
            "BINANCE_TESTNET": "testnet",
            "TELEGRAM_TOKEN": "telegram_token",
            "TELEGRAM_CHAT_ID": "telegram_chat_id",
            "LOG_LEVEL": "log_level",
            "DRY_RUN": "dry_run",
        }

        for env_var, config_key in env_mapping.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                if config_key == "testnet":
                    setattr(self, config_key, env_value.lower() == "true")
                elif config_key == "dry_run":
                    setattr(self, config_key, env_value.lower() == "true")
                else:
                    setattr(self, config_key, env_value)

    def get_telegram_credentials(self) -> tuple[str, str]:
        """Get Telegram credentials"""
        return self.telegram_token, self.telegram_chat_id

    def is_telegram_enabled(self) -> bool:
        """Check if Telegram is enabled and configured"""
        return self.telegram_enabled and self.telegram_token and self.telegram_chat_id

    def get_leverage_for_symbol(self, symbol: str) -> int:
        """Get leverage for a specific symbol"""
        symbol_key = symbol.replace("/", "").replace(":", "").upper()
        return self.leverage_map.get(symbol_key, self.default_leverage)

    def get_active_symbols(self) -> list:
        """Get active trading symbols"""
        if self.testnet:
            return self.usdt_symbols
        else:
            return self.usdc_symbols

    def save_to_file(self, filepath: str = "data/runtime_config.json"):
        """Save current configuration to file"""
        try:
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self.dict(), f, indent=2, default=str)
            print(f"Configuration saved to {filepath}")
        except Exception as e:
            print(f"Failed to save configuration: {e}")

    def validate(self) -> bool:
        """Validate configuration"""
        errors = []

        if not self.api_key or not self.api_secret:
            errors.append("API credentials are required")

        if self.telegram_enabled and (not self.telegram_token or not self.telegram_chat_id):
            errors.append("Telegram credentials required when Telegram is enabled")

        if self.max_positions <= 0:
            errors.append("max_positions must be positive")

        if self.stop_loss_percent <= 0 or self.take_profit_percent <= 0:
            errors.append("Stop loss and take profit must be positive")

        if errors:
            print("Configuration validation errors:")
            for error in errors:
                print(f"  - {error}")
            return False

        return True

    def get_summary(self) -> dict[str, Any]:
        """Get configuration summary for logging"""
        return {
            "testnet": self.testnet,
            "dry_run": self.dry_run,
            "max_positions": self.max_positions,
            "strategy": self.strategy_name,
            "telegram_enabled": self.is_telegram_enabled(),
            "log_level": self.log_level,
        }


# Global configuration instance
config = TradingConfig()


def get_config() -> TradingConfig:
    """Get global configuration instance"""
    return config


def reload_config() -> TradingConfig:
    """Reload configuration from files"""
    global config
    config = TradingConfig()
    return config
