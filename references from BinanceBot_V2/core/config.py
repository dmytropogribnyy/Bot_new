# core/config.py

import dataclasses
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import orjson

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass
class TradingConfig:
    """
    Единый типизированный класс конфигурации для BinanceBot v2.
    Оптимизирован для USDC-M Futures.
    """

    # --- API Credentials ---
    api_key: str = ""
    api_secret: str = ""

    # --- Environment-specific API credentials ---
    testnet_api_key: str = ""
    testnet_api_secret: str = ""
    production_api_key: str = ""
    production_api_secret: str = ""

    # --- Exchange Settings ---
    exchange_mode: str = "testnet"  # production/testnet
    dry_run: bool = False
    testnet_url: str = "https://testnet.binancefuture.com"

    # --- Telegram ---
    telegram_token: str = ""
    telegram_chat_id: str = ""
    telegram_enabled: bool = True
    telegram_error_notifications: bool = True
    telegram_trade_notifications: bool = True
    telegram_startup_message: bool = True
    telegram_admin_users: list[int] = field(default_factory=list)
    telegram_notification_levels: dict[str, bool] = field(
        default_factory=lambda: {
            "trades": True,
            "errors": True,
            "warnings": True,
            "info": False,
            "debug": False,
            "tp_sl": True,
            "balance": True,
            "config": True,
            "performance": True,
        }
    )

    # --- Trading Parameters ---
    max_concurrent_positions: int = 3
    base_risk_pct: float = 0.06  # Снижен с 0.08 до 0.06 для лучшего риск-менеджмента
    risk_multiplier: float = 1.0

    leverage_default: int = 5
    leverage_map_file: str = "data/leverage_map.json"

    # --- Exit Strategy ---
    sl_percent: float = 0.01  # Снижен с 0.012 до 0.01 для более быстрого выхода
    force_sl_always: bool = True
    min_sl_gap_percent: float = 0.005

    # Step TP levels (оптимизированы для лучшей прибыльности)
    step_tp_levels: list[float] = field(default_factory=lambda: [0.005, 0.01, 0.015])  # Увеличены уровни
    step_tp_sizes: list[float] = field(default_factory=lambda: [0.5, 0.3, 0.2])

    # Auto profit (оптимизировано)
    auto_profit_threshold: float = 0.5  # Снижен с 0.7 до 0.5 для более быстрого фиксирования прибыли
    max_hold_minutes: int = 25  # Снижен с 30 до 25 минут
    soft_exit_minutes: int = 12  # Снижен с 15 до 12 минут

    # --- Time-based Exit Strategy ---
    weak_position_minutes: int = 35  # Снижен с 45 до 35 минут
    risky_loss_threshold: float = -1.2  # Улучшен с -1.5 до -1.2
    emergency_stop_threshold: float = -1.8  # Улучшен с -2.0 до -1.8
    trailing_stop_drawdown: float = 0.25  # Улучшен с 0.3 до 0.25

    # --- Position Management ---
    max_position_duration: int = 1800  # Снижен с 3600 до 1800 (30 минут)
    position_sync_interval: int = 20  # Улучшен с 30 до 20 секунд
    order_timeout: int = 180  # Снижен с 300 до 180 секунд

    # --- Order Management ---
    min_trade_qty: float = 0.001
    min_notional_open: float = 15.0  # Увеличен с 10.0 до 15.0 для лучшего качества сделок
    max_position_size_usdc: float = 150.0  # Снижен с 200.0 до 150.0 для лучшего риск-менеджмента
    max_capital_utilization_pct: float = 0.7  # Снижен с 0.8 до 0.7 для лучшей диверсификации

    # --- Risk Management ---
    max_sl_streak: int = 5
    sl_streak_pause_minutes: int = 30
    sl_streak_reduction_factor: int = 2

    # --- Rate Limiting ---
    weight_limit_per_minute: int = 1200
    order_rate_limit_per_second: int = 10
    rate_limit_buffer_pct: float = 0.1

    # --- Logging ---
    db_path: str = "data/trading_log.db"
    max_log_size_mb: int = 100
    log_retention_days: int = 30

    # --- Grid Strategy ---
    grid_levels: int = 7  # Увеличен с 5 до 7 для лучшего покрытия
    grid_spacing: float = 0.003  # Увеличен с 0.002 до 0.003 для более частых сделок
    grid_range: float = 0.015  # Увеличен с 0.01 до 0.015 для лучшего диапазона
    min_order_size: float = 0.001

    # --- Performance Monitoring ---
    performance_check_interval: int = 60  # секунды
    profit_target_daily: float = 16.8  # Целевая прибыль в день (0.7 * 24)
    max_drawdown_daily: float = 30.0  # Максимальная просадка в день

    # --- Profitability Optimization ---
    profit_target_hourly: float = 0.7  # Целевая прибыль в час
    min_win_rate: float = 0.65  # Минимальный винрейт
    max_daily_loss: float = 20.0  # Максимальные дневные потери
    volatility_multiplier_max: float = 3.0  # Максимальный множитель волатильности
    trend_strength_threshold: float = 0.7  # Порог силы тренда
    high_volatility_threshold: float = 0.8  # Порог высокой волатильности
    low_volatility_threshold: float = 0.3  # Порог низкой волатильности

    # --- Strategy Selection ---
    strategy_switch_threshold: float = 0.1  # Порог для смены стратегии
    market_regime_detection: bool = True
    hybrid_signal_enabled: bool = True

    # --- Symbol Selection ---
    symbol_rotation_minutes: int = 15
    max_symbols_to_trade: int = 15
    min_volume_24h_usdc: float = 5000000.0
    min_price_filter: float = 0.01
    min_atr_percent: float = 0.4
    blacklisted_symbols: list[str] = field(default_factory=lambda: ["USDCUSDC"])
    symbol_score_weights: dict[str, int] = field(default_factory=lambda: {
        "volume": 30,
        "volatility": 25,
        "trend": 20,
        "win_rate": 15,
        "avg_pnl": 10
    })

    # --- WebSocket Settings ---
    websocket_enabled: bool = True
    websocket_reconnect_delay: int = 5
    websocket_max_reconnect_attempts: int = 10

    # --- Monitoring ---
    health_check_interval: int = 30
    balance_check_interval: int = 60
    position_monitor_interval: int = 10

    # --- Emergency Settings ---
    emergency_stop_enabled: bool = True
    graceful_shutdown_timeout: int = 300  # 5 минут для graceful shutdown

    # --- Validation ---
    validate_orders_before_placement: bool = True
    validate_position_sizes: bool = True
    validate_leverage_settings: bool = True

    # --- Advanced Features ---
    dynamic_leverage_enabled: bool = True
    position_sizing_optimization: bool = True
    risk_adjustment_enabled: bool = True

    # --- File Paths ---
    runtime_config_path: str = "data/runtime_config.json"
    leverage_map_path: str = "data/leverage_map.json"
    performance_log_path: str = "logs/performance.log"

    # --- Fee Configuration ---
    use_dynamic_fees: bool = True
    default_maker_fee: float = 0.0002  # 0.02%
    default_taker_fee: float = 0.0004  # 0.04%
    bnb_discount_enabled: bool = True
    vip_level: int = 0
    fee_update_interval: int = 3600  # Обновление комиссий каждый час

    # --- Development ---
    debug_mode: bool = False
    verbose_logging: bool = False
    mock_trading: bool = False

    def __init__(self, config_file: str = "data/runtime_config.json"):
        """Инициализация конфигурации с загрузкой из файла"""
        # Сначала создаем с дефолтными значениями
        self.api_key = ""
        self.api_secret = ""
        self.exchange_mode = "testnet"
        self.dry_run = False
        self.testnet_url = "https://testnet.binancefuture.com"
        self.telegram_token = ""
        self.telegram_chat_id = ""
        self.telegram_enabled = True
        self.telegram_error_notifications = True
        self.telegram_trade_notifications = True
        self.telegram_startup_message = True
        self.telegram_admin_users = []
        self.telegram_notification_levels = {
            "trades": True,
            "errors": True,
            "warnings": True,
            "info": False,
            "debug": False,
            "tp_sl": True,
            "balance": True,
            "config": True,
            "performance": True,
        }
        self.max_concurrent_positions = 3
        self.base_risk_pct = 0.06
        self.risk_multiplier = 1.0
        self.leverage_default = 5
        self.leverage_map_file = "data/leverage_map.json"
        self.sl_percent = 0.01
        self.force_sl_always = True
        self.min_sl_gap_percent = 0.005
        self.step_tp_levels = [0.005, 0.01, 0.015]
        self.step_tp_sizes = [0.5, 0.3, 0.2]
        self.auto_profit_threshold = 0.5
        self.max_hold_minutes = 25
        self.soft_exit_minutes = 12
        self.weak_position_minutes = 35
        self.risky_loss_threshold = -1.2
        self.emergency_stop_threshold = -1.8
        self.trailing_stop_drawdown = 0.25
        self.max_position_duration = 1800
        self.position_sync_interval = 20
        self.order_timeout = 180
        self.min_trade_qty = 0.001
        self.min_notional_open = 15.0
        self.max_position_size_usdc = 150.0
        self.max_capital_utilization_pct = 0.7
        self.max_sl_streak = 5
        self.sl_streak_pause_minutes = 30
        self.sl_streak_reduction_factor = 2
        self.weight_limit_per_minute = 1200
        self.order_rate_limit_per_second = 10
        self.rate_limit_buffer_pct = 0.1
        self.db_path = "data/trading_log.db"
        self.max_log_size_mb = 100
        self.log_retention_days = 30
        self.grid_levels = 7
        self.grid_spacing = 0.003
        self.grid_range = 0.015
        self.min_order_size = 0.001
        self.performance_check_interval = 60
        self.profit_target_daily = 16.8
        self.max_drawdown_daily = 30.0
        self.profit_target_hourly = 0.7
        self.min_win_rate = 0.65
        self.max_daily_loss = 20.0
        self.volatility_multiplier_max = 3.0
        self.trend_strength_threshold = 0.7
        self.high_volatility_threshold = 0.8
        self.low_volatility_threshold = 0.3
        self.strategy_switch_threshold = 0.1
        self.market_regime_detection = True
        self.hybrid_signal_enabled = True
        self.symbol_rotation_minutes = 15
        self.max_symbols_to_trade = 15
        self.min_volume_24h_usdc = 5000000.0
        self.min_price_filter = 0.01
        self.min_atr_percent = 0.4
        self.blacklisted_symbols = ["USDCUSDC"]
        self.symbol_score_weights = {
            "volume": 30,
            "volatility": 25,
            "trend": 20,
            "win_rate": 15,
            "avg_pnl": 10
        }
        self.websocket_enabled = True
        self.websocket_reconnect_delay = 5
        self.websocket_max_reconnect_attempts = 10
        self.health_check_interval = 30
        self.balance_check_interval = 60
        self.position_monitor_interval = 10
        self.emergency_stop_enabled = True
        self.graceful_shutdown_timeout = 300
        self.validate_orders_before_placement = True
        self.validate_position_sizes = True
        self.validate_leverage_settings = True
        self.dynamic_leverage_enabled = True
        self.position_sizing_optimization = True
        self.risk_adjustment_enabled = True
        self.runtime_config_path = "data/runtime_config.json"
        self.leverage_map_path = "data/leverage_map.json"
        self.performance_log_path = "logs/performance.log"
        self.use_dynamic_fees = True
        self.default_maker_fee = 0.0002
        self.default_taker_fee = 0.0004
        self.bnb_discount_enabled = True
        self.vip_level = 0
        self.fee_update_interval = 3600
        self.debug_mode = False
        self.verbose_logging = False
        self.mock_trading = False

        # Затем загружаем из файла, если он существует
        try:
            if Path(config_file).exists():
                with open(config_file, "rb") as f:
                    import json
                    data = json.load(f)

                # Обновляем только те поля, которые есть в файле
                for field_name, value in data.items():
                    if hasattr(self, field_name):
                        setattr(self, field_name, value)
        except Exception as e:
            print(f"Warning: Could not load config from {config_file}: {e}")
            print("Using default configuration")

    def __post_init__(self):
        """Валидация конфигурации после инициализации"""
        if self.base_risk_pct <= 0 or self.base_risk_pct > 1:
            raise ValueError("base_risk_pct must be between 0 and 1")

        if self.sl_percent <= 0 or self.sl_percent > 0.1:
            raise ValueError("sl_percent must be between 0 and 0.1")

        if len(self.step_tp_levels) != len(self.step_tp_sizes):
            raise ValueError("step_tp_levels and step_tp_sizes must have same length")

        if sum(self.step_tp_sizes) != 1.0:
            raise ValueError("step_tp_sizes must sum to 1.0")

    @classmethod
    def from_file(cls, file_path: str) -> "TradingConfig":
        """Загрузка конфигурации из файла"""
        try:
            with open(file_path, "rb") as f:
                data = orjson.loads(f.read())

            # Создаем экземпляр с дефолтными значениями
            config = cls()

            # Обновляем только те поля, которые есть в файле
            for field_name, value in data.items():
                if hasattr(config, field_name):
                    setattr(config, field_name, value)

            return config

        except Exception as e:
            raise ValueError(f"Failed to load config from {file_path}: {e}") from e

    def to_file(self, file_path: str):
        """Сохранение конфигурации в файл"""
        try:
            # Создаем словарь с текущими значениями
            data = {}
            for field in dataclasses.fields(self):
                value = getattr(self, field.name)
                data[field.name] = value

            # Сохраняем в файл
            with open(file_path, "wb") as f:
                f.write(orjson.dumps(data, option=orjson.OPT_INDENT_2))

        except Exception as e:
            raise ValueError(f"Failed to save config to {file_path}: {e}") from e

    def validate(self) -> list[str]:
        """Валидация конфигурации, возвращает список ошибок"""
        errors = []

        # Проверка API ключей (из переменных окружения или конфига)
        api_key, api_secret = self.get_api_credentials()
        if not api_key:
            errors.append("BINANCE_API_KEY is required (set in .env or config)")
        if not api_secret:
            errors.append("BINANCE_API_SECRET is required (set in .env or config)")

        # Проверка Telegram ключей
        telegram_token, telegram_chat_id = self.get_telegram_credentials()
        if not telegram_token:
            errors.append("TELEGRAM_TOKEN is required (set in .env or config)")
        if not telegram_chat_id:
            errors.append("TELEGRAM_CHAT_ID is required (set in .env or config)")

        # Проверка торговых параметров
        if self.max_concurrent_positions <= 0:
            errors.append("max_concurrent_positions must be positive")
        if self.base_risk_pct <= 0 or self.base_risk_pct > 1:
            errors.append("base_risk_pct must be between 0 and 1")
        if self.sl_percent <= 0 or self.sl_percent > 0.1:
            errors.append("sl_percent must be between 0 and 0.1")

        # Проверка TP уровней
        if len(self.step_tp_levels) != len(self.step_tp_sizes):
            errors.append("step_tp_levels and step_tp_sizes must have same length")
        if sum(self.step_tp_sizes) != 1.0:
            errors.append("step_tp_sizes must sum to 1.0")

        return errors

    def get_summary(self) -> dict[str, Any]:
        """Получение краткого описания конфигурации"""
        return {
            "exchange_mode": self.exchange_mode,
            "max_positions": self.max_concurrent_positions,
            "base_risk_pct": self.base_risk_pct,
            "sl_percent": self.sl_percent,
            "tp_levels": len(self.step_tp_levels),
            "telegram_enabled": self.telegram_enabled,
            "websocket_enabled": self.websocket_enabled,
            "dry_run": self.dry_run,
        }

    def get_api_credentials(self) -> tuple[str, str]:
        """
        Получение правильных API ключей в зависимости от режима.
        Приоритет: переменные окружения > специфичные ключи > общие ключи
        """
        is_testnet = self.is_testnet_mode()

        # Проверяем переменные окружения в первую очередь
        if is_testnet:
            env_api_key = os.environ.get('BINANCE_API_KEY') or os.environ.get('BINANCE_TESTNET_API_KEY')
            env_api_secret = os.environ.get('BINANCE_API_SECRET') or os.environ.get('BINANCE_TESTNET_API_SECRET')
            if env_api_key and env_api_secret:
                return env_api_key, env_api_secret
        else:
            env_api_key = os.environ.get('BINANCE_API_KEY') or os.environ.get('BINANCE_PRODUCTION_API_KEY')
            env_api_secret = os.environ.get('BINANCE_API_SECRET') or os.environ.get('BINANCE_PRODUCTION_API_SECRET')
            if env_api_key and env_api_secret:
                return env_api_key, env_api_secret

        # Проверяем специфичные ключи для режима
        if is_testnet:
            if self.testnet_api_key and self.testnet_api_secret:
                return self.testnet_api_key, self.testnet_api_secret
        else:
            if self.production_api_key and self.production_api_secret:
                return self.production_api_key, self.production_api_secret

        # Используем общие ключи как fallback
        return self.api_key, self.api_secret

    def get_telegram_credentials(self) -> tuple[str, str]:
        """
        Получение Telegram ключей из переменных окружения
        """
        telegram_token = os.environ.get('TELEGRAM_TOKEN', self.telegram_token)
        telegram_chat_id = os.environ.get('TELEGRAM_CHAT_ID', self.telegram_chat_id)
        return telegram_token, telegram_chat_id

    def get_logging_config(self) -> dict:
        """
        Получение настроек логирования из переменных окружения
        """
        return {
            'log_level': os.environ.get('LOG_LEVEL', self.log_level),
            'log_verbosity': os.environ.get('LOG_VERBOSITY', 'CLEAN')
        }

    def is_testnet_mode(self) -> bool:
        """Проверка, находится ли бот в testnet режиме"""
        return (self.exchange_mode == "testnet" or
                hasattr(self, 'use_testnet') and self.use_testnet)

    def is_production_mode(self) -> bool:
        """Проверка, находится ли бот в production режиме"""
        return self.exchange_mode == "production" and not self.is_testnet_mode()

    def validate_api_credentials(self) -> list[str]:
        """Валидация API ключей для текущего режима"""
        errors = []

        api_key, api_secret = self.get_api_credentials()

        if not api_key:
            mode = "testnet" if self.is_testnet_mode() else "production"
            errors.append(f"BINANCE_API_KEY is required for {mode} mode (set in .env or config)")
        if not api_secret:
            mode = "testnet" if self.is_testnet_mode() else "production"
            errors.append(f"BINANCE_API_SECRET is required for {mode} mode (set in .env or config)")

        return errors

    def get_environment_info(self) -> dict[str, Any]:
        """Получение информации о текущем окружении"""
        api_key, api_secret = self.get_api_credentials()
        telegram_token, telegram_chat_id = self.get_telegram_credentials()

        return {
            "mode": "testnet" if self.is_testnet_mode() else "production",
            "exchange_mode": self.exchange_mode,
            "use_testnet": hasattr(self, 'use_testnet') and self.use_testnet,
            "has_api_key": bool(api_key),
            "has_api_secret": bool(api_secret),
            "has_telegram_token": bool(telegram_token),
            "has_telegram_chat_id": bool(telegram_chat_id),
            "api_key_source": self._get_api_key_source(),
            "environment_variables": {
                "BINANCE_API_KEY": bool(os.environ.get('BINANCE_API_KEY')),
                "BINANCE_API_SECRET": bool(os.environ.get('BINANCE_API_SECRET')),
                "BINANCE_TESTNET_API_KEY": bool(os.environ.get('BINANCE_TESTNET_API_KEY')),
                "BINANCE_TESTNET_API_SECRET": bool(os.environ.get('BINANCE_TESTNET_API_SECRET')),
                "BINANCE_PRODUCTION_API_KEY": bool(os.environ.get('BINANCE_PRODUCTION_API_KEY')),
                "BINANCE_PRODUCTION_API_SECRET": bool(os.environ.get('BINANCE_PRODUCTION_API_SECRET')),
                "TELEGRAM_TOKEN": bool(os.environ.get('TELEGRAM_TOKEN')),
                "TELEGRAM_CHAT_ID": bool(os.environ.get('TELEGRAM_CHAT_ID')),
                "LOG_LEVEL": bool(os.environ.get('LOG_LEVEL')),
                "LOG_VERBOSITY": bool(os.environ.get('LOG_VERBOSITY')),
            }
        }

    def _get_api_key_source(self) -> str:
        """Определение источника API ключей"""
        is_testnet = self.is_testnet_mode()

        if is_testnet:
            if os.environ.get('BINANCE_API_KEY') or os.environ.get('BINANCE_TESTNET_API_KEY'):
                return "environment_variable"
            elif self.testnet_api_key:
                return "config_file_specific"
            elif self.api_key:
                return "config_file_general"
        else:
            if os.environ.get('BINANCE_API_KEY') or os.environ.get('BINANCE_PRODUCTION_API_KEY'):
                return "environment_variable"
            elif self.production_api_key:
                return "config_file_specific"
            elif self.api_key:
                return "config_file_general"

        return "none"

    @classmethod
    def select_config_for_profit_target(cls, target_hourly_profit: float = 2.0) -> str:
        """
        Автоматический выбор конфигурации на основе целевой прибыли в час

        Args:
            target_hourly_profit: Целевая прибыль в час в долларах

        Returns:
            str: Путь к оптимальной конфигурации
        """
        config_mapping = {
            "data/runtime_config.json": {
                "profit_target_hourly": 0.7,
                "description": "Агрессивная торговля для высокой прибыльности",
                "risk_level": "high",
                "max_positions": 5,
                "base_risk_pct": 0.15
            },
            "data/runtime_config_safe.json": {
                "profit_target_hourly": 0.5,
                "description": "Безопасная торговля для стабильной прибыли",
                "risk_level": "low",
                "max_positions": 1,
                "base_risk_pct": 0.005
            },
            "data/runtime_config_test.json": {
                "profit_target_hourly": 1.0,
                "description": "Тестовая конфигурация для быстрых сделок",
                "risk_level": "medium",
                "max_positions": 1,
                "base_risk_pct": 0.01
            }
        }

        # Находим конфигурацию, которая лучше всего соответствует цели
        best_config = None
        best_match_score = 0

        for config_path, config_info in config_mapping.items():
            if not Path(config_path).exists():
                continue

            config_profit_target = config_info.get("profit_target_hourly", 0)

            # Вычисляем соответствие цели
            if config_profit_target == target_hourly_profit:
                match_score = 100  # Идеальное соответствие
            else:
                # Вычисляем близость к цели
                difference = abs(config_profit_target - target_hourly_profit)
                match_score = max(0, 100 - (difference * 20))  # Штраф за разницу

            if match_score > best_match_score:
                best_match_score = match_score
                best_config = config_path

        # Если не найдена подходящая конфигурация, используем основную
        if not best_config:
            best_config = "data/runtime_config.json"

        return best_config

    @classmethod
    def load_optimized_for_profit_target(cls, target_hourly_profit: float = 2.0) -> "TradingConfig":
        """
        Загружает конфигурацию, оптимизированную для достижения целевой прибыли

        Args:
            target_hourly_profit: Целевая прибыль в час в долларах

        Returns:
            TradingConfig: Оптимизированная конфигурация
        """
        config_path = cls.select_config_for_profit_target(target_hourly_profit)

        if not Path(config_path).exists():
            print(f"⚠️ Конфигурация {config_path} не найдена, используем дефолтную")
            return cls()

        try:
            config = cls(config_path)
            config.profit_target_hourly = target_hourly_profit  # Устанавливаем целевую прибыль

            print(f"[OK] Загружена конфигурация для цели ${target_hourly_profit}/час: {config_path}")
            print("Основные параметры:")
            print(f"   • Целевая прибыль в час: ${config.profit_target_hourly}")
            print(f"   • Макс. позиций: {config.max_concurrent_positions}")
            print(f"   • Базовый риск: {config.base_risk_pct*100:.2f}%")
            print(f"   • Stop Loss: {config.sl_percent*100:.2f}%")

            return config

        except Exception as e:
            print(f"[ERROR] Ошибка загрузки конфигурации {config_path}: {e}")
            print("Используем дефолтную конфигурацию")
            return cls()

    def get_profit_target_info(self) -> dict[str, Any]:
        """Получение информации о целях прибыльности"""
        return {
            "profit_target_hourly": self.profit_target_hourly,
            "profit_target_daily": self.profit_target_daily,
            "current_config_optimized_for": self.profit_target_hourly,
            "config_file": getattr(self, '_config_file', 'default'),
            "risk_level": self._get_risk_level(),
            "expected_hourly_profit": self._calculate_expected_hourly_profit()
        }

    def _get_risk_level(self) -> str:
        """Определение уровня риска конфигурации"""
        if self.base_risk_pct <= 0.01:
            return "low"
        elif self.base_risk_pct <= 0.05:
            return "medium"
        else:
            return "high"

    def _calculate_expected_hourly_profit(self) -> float:
        """Расчет ожидаемой прибыли в час на основе параметров"""
        # Упрощенный расчет на основе параметров
        base_profit = self.max_concurrent_positions * self.base_risk_pct * 100
        time_factor = 60 / max(self.max_hold_minutes, 1)  # Фактор времени
        return base_profit * time_factor * 0.1  # Коэффициент успешности

    def get(self, key: str, default=None):
        """Совместимость с dict-like интерфейсом для компонентов, ожидающих словарь"""
        return getattr(self, key, default)

    def __hash__(self):
        """Позволяет использовать TradingConfig как ключ в словаре"""
        return hash(id(self))
