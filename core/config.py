#!/usr/bin/env python3
"""
Configuration system for BinanceBot v2.3
Unified configuration with leverage mapping and simplified loading
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# === Module-level env helpers (Stage B centralization) ===
def _clean_str(value: str) -> str:
    value = value.split("#", 1)[0]
    value = value.split(";", 1)[0]
    return value.strip()


def env_str(key: str, default: str) -> str:
    val = os.getenv(key)
    return _clean_str(val) if val is not None else default


def env_bool(key: str, default: bool) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return str(val).strip().lower() in ("true", "1", "yes", "on")


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

    trading_deposit: float = Field(default=400.0, description="Base trading deposit in quote currency")

    use_dynamic_balance: bool = Field(default=False, description="Use real futures balance instead of fixed deposit")
    balance_percentage: float = Field(default=0.95, description="Fraction of available quote balance to use")

    # Risk Management
    stop_loss_percent: float = Field(default=1.2, description="Default stop loss percentage")
    take_profit_percent: float = Field(default=1.8, description="Default take profit percentage")
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

    # Trading Symbols (leave empty by default; fallback is dynamic)
    usdt_symbols: list = Field(default_factory=list, description="USDT trading pairs (used on testnet)")
    usdc_symbols: list = Field(default_factory=list, description="USDC trading pairs")

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

    # TP/SL Settings (legacy keys retained for backward-compat but deprecated)
    step_tp_levels: list = Field(default=[0.004, 0.008, 0.012], description="[DEPRECATED] Step TP levels")
    step_tp_sizes: list = Field(default=[0.5, 0.3, 0.2], description="[DEPRECATED] Step TP sizes")
    min_sl_gap_percent: float = Field(default=0.005, description="Minimum SL gap")
    sl_percent: float = Field(default=0.012, description="[DEPRECATED] Stop loss percentage; use stop_loss_percent")
    force_sl_always: bool = Field(default=True, description="Force SL always")
    sl_retry_limit: int = Field(default=3, description="SL retry limit")

    # Auto Profit Settings
    auto_profit_enabled: bool = Field(default=True, description="Auto profit enabled")
    auto_profit_threshold: float = Field(default=0.5, description="Auto profit threshold")
    bonus_profit_threshold: float = Field(default=2.0, description="Bonus profit threshold")
    max_hold_minutes: int = Field(default=10, description="Maximum hold time")
    min_profit_threshold: float = Field(default=0.06, description="Minimum profit threshold")
    entry_cooldown_seconds: int = Field(default=0, description="Cooldown between entries on same symbol")

    # Spread filter configuration
    max_spread_pct: float = Field(default=0.20, description="Maximum allowed bid-ask spread percent")
    disable_spread_filter_testnet: bool = Field(
        default=True, description="Disable spread filter on testnet (unless explicitly turned off)"
    )

    # Multi-TP levels (optional)
    tp1_percent: float | None = Field(default=None)
    tp1_size_fraction: float = Field(default=0.6)
    tp2_percent: float | None = Field(default=None)
    tp2_size_fraction: float = Field(default=0.4)

    # Trailing stop (disabled by default)
    trailing_enabled: bool = Field(default=False)
    trailing_be_pct: float = Field(default=1.0)
    trailing_step_pct: float = Field(default=0.5)

    # WebSocket Settings (disabled by default)
    enable_websocket: bool = Field(default=False, description="Enable WebSocket streams")

    # ATR-based TP/SL (disabled by default)
    use_atr_based_tp_sl: bool = Field(default=False)
    atr_multiplier_sl: float = Field(default=1.0)
    atr_multiplier_tp: float = Field(default=2.0)

    # Order Settings
    min_notional_open: float = Field(default=15.0, description="Minimum notional for opening")
    min_notional_order: float = Field(default=5.0, description="Minimum notional for orders")
    min_trade_qty: float = Field(default=0.001, description="Minimum trade quantity")
    min_total_qty_for_tp_full: float = Field(default=0.002, description="Minimum total quantity for TP")

    # Limits and Safety
    max_hourly_trade_limit: int = Field(default=0, description="Maximum hourly trades")
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
    tp_order_style: Literal["limit", "market"] = "limit"  # [DEPRECATED] prefer tp_order_type
    mandatory_sl: bool = True

    # Protective order defaults (configurable via env)
    sl_order_type: str = Field(default="STOP_MARKET", env="SL_ORDER_TYPE")
    tp_order_type: str = Field(default="TAKE_PROFIT_MARKET", env="TP_ORDER_TYPE")
    time_in_force: str = Field(default="GTC", env="TIME_IN_FORCE")
    reduce_only: bool = Field(default=True, env="REDUCE_ONLY")

    # Multiple TP and trailing stop controls (Stage: multiple-tp-trailing)
    enable_multiple_tp: bool = Field(default=True, env="ENABLE_MULTIPLE_TP")
    # Raw TP levels from env/file. Use property tp_levels to consume.
    tp_levels_raw: list[dict] | str = Field(default=[], env="TP_LEVELS")
    enable_trailing_stop: bool = Field(default=False, env="ENABLE_TRAILING_STOP")
    trailing_stop_percent: float = Field(default=0.5, env="TRAILING_STOP_PERCENT")
    trailing_activation_after_tp: int = Field(default=1, env="TRAILING_ACTIVATION_AFTER_TP")

    # Position sizing / minQty handling (auto-increase for BTC/ETH)
    base_position_size_usdt: float = Field(default=20.0, env="BASE_POSITION_SIZE_USDT")
    allow_auto_increase_for_min: bool = Field(default=True, env="ALLOW_AUTO_INCREASE_FOR_MIN")
    max_auto_increase_usdt: float = Field(default=150.0, env="MAX_AUTO_INCREASE_USDT")

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

        cfg = cls(
            # API
            api_key=env_str("API_KEY", os.getenv("BINANCE_API_KEY", "") or ""),
            api_secret=env_str("API_SECRET", os.getenv("BINANCE_API_SECRET", "") or ""),
            testnet=env_bool("TESTNET", str(os.getenv("BINANCE_TESTNET", "true")).lower() == "true"),
            dry_run=env_bool("DRY_RUN", False),
            # Stage D
            working_type=env_str("WORKING_TYPE", "MARK_PRICE"),
            tp_order_style=env_str("TP_ORDER_STYLE", "limit"),
            # Protective order types
            sl_order_type=env_str("SL_ORDER_TYPE", "STOP_MARKET"),
            tp_order_type=env_str("TP_ORDER_TYPE", "TAKE_PROFIT_MARKET"),
            time_in_force=env_str("TIME_IN_FORCE", "GTC"),
            reduce_only=env_bool("REDUCE_ONLY", True),
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
            # Dynamic balance & deposit
            use_dynamic_balance=env_bool("USE_DYNAMIC_BALANCE", getattr(cls, "use_dynamic_balance", False)),
            balance_percentage=env_float("BALANCE_PERCENTAGE", getattr(cls, "balance_percentage", 0.95)),
            trading_deposit=env_float("TRADING_DEPOSIT", getattr(cls, "trading_deposit", 400.0)),
            # Spread filter
            max_spread_pct=env_float("MAX_SPREAD_PCT", getattr(cls, "max_spread_pct", 0.20)),
            disable_spread_filter_testnet=env_bool(
                "DISABLE_SPREAD_FILTER_TESTNET", getattr(cls, "disable_spread_filter_testnet", True)
            ),
            # TP/SL (only stop_loss_percent and take_profit_percent are used)
            take_profit_percent=env_float("TAKE_PROFIT_PERCENT", getattr(cls, "take_profit_percent", 1.8)),
            stop_loss_percent=env_float("STOP_LOSS_PERCENT", getattr(cls, "stop_loss_percent", 1.2)),
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
            enable_websocket=env_bool("ENABLE_WEBSOCKET", getattr(cls, "enable_websocket", False)),
            ws_reconnect_interval=env_int("WS_RECONNECT_INTERVAL", getattr(cls, "ws_reconnect_interval", 5)),
            ws_heartbeat_interval=env_int("WS_HEARTBEAT_INTERVAL", getattr(cls, "ws_heartbeat_interval", 30)),
            # Entry controls
            entry_cooldown_seconds=env_int("ENTRY_COOLDOWN_SECONDS", getattr(cls, "entry_cooldown_seconds", 0)),
            max_hourly_trade_limit=env_int("MAX_HOURLY_TRADE_LIMIT", getattr(cls, "max_hourly_trade_limit", 0)),
        )

        # Optional QUOTE_COIN override: {USDT, USDC}; default auto-resolve (testnet→USDT, prod→USDC)
        try:
            qc = env_str("QUOTE_COIN", cfg.resolved_quote_coin).upper()
            if qc in ("USDT", "USDC"):
                # Monkey-patch resolved property via attribute for downstream usage
                object.__setattr__(cfg, "_quote_coin_override", qc)
        except Exception:
            pass

        return cfg

    model_config = ConfigDict()

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

                    # Update values present in file (allow 0/False), only known attributes
                    for key, value in file_config.items():
                        if hasattr(self, key) and value is not None:
                            setattr(self, key, value)

                    print(f"Loaded configuration from {config_file}")
                    break
                except Exception as e:
                    print(f"Failed to load config from {config_file}: {e}")

    def _load_from_env(self):
        """Load configuration from environment variables"""
        # Map .env keys to model fields (names must match attributes)
        env_mapping = {
            # API
            "BINANCE_API_KEY": "api_key",
            "BINANCE_API_SECRET": "api_secret",
            "BINANCE_TESTNET": "testnet",
            "DRY_RUN": "dry_run",
            # Logging
            "LOG_LEVEL": "log_level",
            "LOG_TO_FILE": "log_to_file",
            "LOG_TO_CONSOLE": "log_to_console",
            # Telegram
            "TELEGRAM_TOKEN": "telegram_token",
            "TELEGRAM_CHAT_ID": "telegram_chat_id",
            "TELEGRAM_ENABLED": "telegram_enabled",
            # WebSocket
            "ENABLE_WEBSOCKET": "enable_websocket",
            "WS_RECONNECT_INTERVAL": "ws_reconnect_interval",
            "WS_HEARTBEAT_INTERVAL": "ws_heartbeat_interval",
            # Execution
            "WORKING_TYPE": "working_type",
            "TP_ORDER_STYLE": "tp_order_style",
            "SL_ORDER_TYPE": "sl_order_type",
            "TP_ORDER_TYPE": "tp_order_type",
            "TIME_IN_FORCE": "time_in_force",
            "REDUCE_ONLY": "reduce_only",
            # Multiple TP & Trailing
            "ENABLE_MULTIPLE_TP": "enable_multiple_tp",
            "TP_LEVELS": "tp_levels_raw",
            "ENABLE_TRAILING_STOP": "enable_trailing_stop",
            "TRAILING_STOP_PERCENT": "trailing_stop_percent",
            "TRAILING_ACTIVATION_AFTER_TP": "trailing_activation_after_tp",
            # Positions / Risk
            "MAX_POSITIONS": "max_positions",
            "MIN_POSITION_SIZE_USDT": "min_position_size_usdt",
            "MAX_POSITION_SIZE_USDT": "max_position_size_usdt",
            "LEVERAGE_DEFAULT": "default_leverage",
            "STOP_LOSS_PERCENT": "stop_loss_percent",
            "TAKE_PROFIT_PERCENT": "take_profit_percent",
            "MAX_SLIPPAGE_PCT": "max_slippage_pct",
            "MAX_CAPITAL_UTILIZATION_PCT": "max_capital_utilization_pct",
            "MAX_MARGIN_PERCENT": "max_margin_percent",
            "MAX_CONCURRENT_POSITIONS": "max_concurrent_positions",
            "RISK_MULTIPLIER": "risk_multiplier",
            # Multi-TP (optional parsing; lists may still come from runtime_config.json)
            "STEP_TP_LEVELS": "step_tp_levels",
            "STEP_TP_SIZES": "step_tp_sizes",
            # Dynamic balance & deposit
            "USE_DYNAMIC_BALANCE": "use_dynamic_balance",
            "BALANCE_PERCENTAGE": "balance_percentage",
            "TRADING_DEPOSIT": "trading_deposit",
            # Entry controls
            "ENTRY_COOLDOWN_SECONDS": "entry_cooldown_seconds",
            "MAX_HOURLY_TRADE_LIMIT": "max_hourly_trade_limit",
            # Spread filter
            "MAX_SPREAD_PCT": "max_spread_pct",
            "DISABLE_SPREAD_FILTER_TESTNET": "disable_spread_filter_testnet",
        }

        for env_var, config_key in env_mapping.items():
            raw = os.getenv(env_var)
            if raw is None:
                continue
            val = raw.strip()
            # booleans
            if config_key in (
                "testnet",
                "dry_run",
                "enable_websocket",
                "telegram_enabled",
                "log_to_file",
                "log_to_console",
                "use_dynamic_balance",
                "disable_spread_filter_testnet",
                "enable_multiple_tp",
                "enable_trailing_stop",
            ):
                setattr(self, config_key, val.lower() in ("true", "1", "yes", "on"))
                continue
            # ints
            if config_key in (
                "ws_reconnect_interval",
                "ws_heartbeat_interval",
                "max_positions",
                "default_leverage",
                "max_concurrent_positions",
                "entry_cooldown_seconds",
                "max_hourly_trade_limit",
                "trailing_activation_after_tp",
            ):
                try:
                    setattr(self, config_key, int(val))
                except Exception:
                    pass
                continue
            # floats
            if config_key in (
                "min_position_size_usdt",
                "max_position_size_usdt",
                "stop_loss_percent",
                "take_profit_percent",
                "max_slippage_pct",
                "max_capital_utilization_pct",
                "max_margin_percent",
                "risk_multiplier",
                "balance_percentage",
                "trading_deposit",
                "max_spread_pct",
                "trailing_stop_percent",
                "base_position_size_usdt",
                "max_auto_increase_usdt",
            ):
                try:
                    setattr(self, config_key, float(val))
                except Exception:
                    pass
                continue
            # additional booleans
            if config_key in ("allow_auto_increase_for_min",):
                setattr(self, config_key, val.lower() in ("true", "1", "yes", "on"))
                continue
            # strings (working_type, tp_order_style, tokens, etc.)
            setattr(self, config_key, val)

        # Optional QUOTE_COIN override (USDT/USDC) in normal ctor
        try:
            qc = os.getenv("QUOTE_COIN")
            if qc and qc.strip().upper() in ("USDT", "USDC"):
                object.__setattr__(self, "_quote_coin_override", qc.strip().upper())
        except Exception:
            pass

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
        """Get active trading symbols.

        Returns configured symbols if provided, otherwise dynamic defaults based on resolved quote coin.
        """
        try:
            from core.symbol_utils import default_symbols  # local import to avoid circular
        except Exception:

            def default_symbols(q):
                return []  # type: ignore

        if self.testnet:
            return self.usdt_symbols or default_symbols(self.resolved_quote_coin)
        else:
            return self.usdc_symbols or default_symbols(self.resolved_quote_coin)

    @property
    def resolved_quote_coin(self) -> str:
        """Auto-resolve quote coin with optional QUOTE_COIN override.

        Default: USDT on testnet, USDC on prod. Explicit QUOTE_COIN env of USDT/USDC overrides.
        """
        qc = getattr(self, "_quote_coin_override", None)
        if qc in ("USDT", "USDC"):
            return qc
        return "USDT" if self.testnet else "USDC"

    def save_to_file(self, filepath: str = "data/runtime_config.json"):
        """Save current configuration to file"""
        try:
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self.model_dump(), f, indent=2, default=str)
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

    @property
    def tp_levels(self) -> list[dict]:
        """
        Возвращает список уровней TP: [{percent: float, size: 0..1}, ...].
        Источники:
        - TP_LEVELS (JSON-строка или список) — percent в долях (0.012 → 1.2%).
        - step_tp_levels + step_tp_sizes — уровни/доли из конфигурации (уровни в долях).
        Если multiple TP выключен — fallback на один уровень по take_profit_percent.
        """
        if not getattr(self, "enable_multiple_tp", False):
            return [{"percent": float(self.take_profit_percent), "size": 1.0}]

        # 1) Try explicit TP_LEVELS first (env/file). Accept JSON string or list.
        raw_levels: list[dict] | list | str = getattr(self, "tp_levels_raw", [])
        levels_from_env: list[dict] = []
        if isinstance(raw_levels, str):
            try:
                raw_levels = json.loads(raw_levels)
            except Exception as e:
                logging.warning(f"Invalid TP_LEVELS format: {e}")
                raw_levels = []
        if isinstance(raw_levels, list):
            for item in raw_levels:
                try:
                    if isinstance(item, dict):
                        pct = float(item.get("percent", 0))
                        size = float(item.get("size", 0))
                    else:
                        # tolerate list of numbers (levels) without sizes
                        pct = float(item)
                        size = 0.0
                    # Convert fraction→percent if value looks fractional
                    pct_percent = pct * 100.0 if pct <= 1.0 else pct
                    if pct_percent > 0 and 0 < size <= 1:
                        levels_from_env.append({"percent": pct_percent, "size": size})
                except Exception:
                    continue

        # 2) Fallback to step arrays
        levels_from_steps: list[dict] = []
        try:
            steps = getattr(self, "step_tp_levels", []) or []
            sizes = getattr(self, "step_tp_sizes", []) or []
            for pct_raw, sz in zip(steps, sizes, strict=False):
                try:
                    pct_percent = (float(pct_raw) * 100.0) if float(pct_raw) <= 1.0 else float(pct_raw)
                    sz_f = float(sz)
                    if pct_percent > 0 and 0 < sz_f <= 1:
                        levels_from_steps.append({"percent": pct_percent, "size": sz_f})
                except Exception:
                    continue
        except Exception:
            levels_from_steps = []

        parsed = levels_from_env or levels_from_steps
        return parsed or [{"percent": float(self.take_profit_percent), "size": 1.0}]

    # Backward-compatible helper
    def get_tp_levels(self) -> list[dict]:
        return self.tp_levels


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
