#!/usr/bin/env python3
"""
Скрипт для настройки логирования под разные среды развертывания
Поддерживает: local, vps, cloud, production
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

# Добавляем корневую папку в путь
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class LoggingSetup:
    """Настройка логирования для разных сред"""

    def __init__(self):
        self.config_path = Path("data/logging_config.json")
        self.logging_config = self._load_logging_config()

    def _load_logging_config(self) -> dict[str, Any]:
        """Загружает конфигурацию логирования"""
        if not self.config_path.exists():
            print(f"❌ Конфигурационный файл не найден: {self.config_path}")
            return {}

        try:
            with open(self.config_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Ошибка загрузки конфигурации: {e}")
            return {}

    def setup_environment(self, environment: str):
        """Настраивает логирование для указанной среды"""
        if environment not in self.logging_config.get("environments", {}):
            print(f"❌ Неизвестная среда: {environment}")
            print(f"Доступные среды: {list(self.logging_config.get('environments', {}).keys())}")
            return False

        env_config = self.logging_config["environments"][environment]
        print(f"🔧 Настройка логирования для среды: {environment}")
        print(f"📋 Описание: {env_config.get('description', 'N/A')}")

        # Настройка переменных окружения
        self._setup_environment_variables(environment, env_config)

        # Создание директорий
        self._create_directories(env_config)

        # Настройка файлов конфигурации
        self._setup_config_files(environment, env_config)

        print(f"✅ Настройка завершена для среды: {environment}")
        return True

    def _setup_environment_variables(self, environment: str, config: dict[str, Any]):
        """Настраивает переменные окружения"""
        print("🔧 Настройка переменных окружения...")

        # Основные настройки
        os.environ["LOGGING_ENVIRONMENT"] = environment
        os.environ["LOG_LEVEL"] = config.get("file_logging", {}).get("log_level", "INFO")

        # Внешние сервисы
        external_services = config.get("external_services", {})
        if external_services.get("enabled", False):
            # AWS CloudWatch
            if external_services.get("aws_cloudwatch", {}).get("enabled", False):
                os.environ["AWS_CLOUDWATCH_ENABLED"] = "true"
                os.environ["AWS_CLOUDWATCH_LOG_GROUP"] = external_services["aws_cloudwatch"].get(
                    "log_group", "binance-bot"
                )
                os.environ["AWS_DEFAULT_REGION"] = external_services["aws_cloudwatch"].get(
                    "region", "us-east-1"
                )

            # GCP StackDriver
            if external_services.get("gcp_stackdriver", {}).get("enabled", False):
                os.environ["GCP_STACKDRIVER_ENABLED"] = "true"
                os.environ["GCP_STACKDRIVER_LOG_NAME"] = "binance-bot"
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/path/to/service-account.json"

            # Azure Monitor
            if external_services.get("azure_monitor", {}).get("enabled", False):
                os.environ["AZURE_MONITOR_ENABLED"] = "true"
                os.environ["AZURE_MONITOR_CONNECTION_STRING"] = external_services[
                    "azure_monitor"
                ].get("connection_string", "")

        print("✅ Переменные окружения настроены")

    def _create_directories(self, config: dict[str, Any]):
        """Создает необходимые директории"""
        print("📁 Создание директорий...")

        # Директория для логов
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        print(f"✅ Создана директория: {log_dir}")

        # Директория для данных
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        print(f"✅ Создана директория: {data_dir}")

        # Для VPS/Cloud/Production - создаем системные директории
        if config.get("database", {}).get("path", "").startswith("/var/log"):
            try:
                system_log_dir = Path("/var/log/binance-bot")
                system_log_dir.mkdir(parents=True, exist_ok=True)
                print(f"✅ Создана системная директория: {system_log_dir}")
            except PermissionError:
                print("⚠️ Недостаточно прав для создания системной директории")

        print("✅ Все директории созданы")

    def _setup_config_files(self, environment: str, config: dict[str, Any]):
        """Настраивает файлы конфигурации"""
        print("⚙️ Настройка файлов конфигурации...")

        # Обновляем runtime_config.json
        runtime_config_path = Path("data/runtime_config.json")
        if runtime_config_path.exists():
            try:
                with open(runtime_config_path, encoding="utf-8") as f:
                    runtime_config = json.load(f)

                # Обновляем настройки логирования
                runtime_config.update(
                    {
                        "max_log_size_mb": config.get("file_logging", {}).get("max_size_mb", 100),
                        "log_retention_days": config.get("file_logging", {}).get(
                            "retention_days", 30
                        ),
                        "db_path": config.get("database", {}).get("path", "data/trading_log.db"),
                        "telegram_enabled": config.get("telegram", {}).get("enabled", True),
                    }
                )

                with open(runtime_config_path, "w", encoding="utf-8") as f:
                    json.dump(runtime_config, f, indent=2, ensure_ascii=False)

                print(f"✅ Обновлен файл конфигурации: {runtime_config_path}")

            except Exception as e:
                print(f"⚠️ Ошибка обновления конфигурации: {e}")

        # Создаем .env файл для переменных окружения
        env_file = Path(".env")
        env_content = f"""# Logging Environment Configuration
LOGGING_ENVIRONMENT={environment}
LOG_LEVEL={config.get("file_logging", {}).get("log_level", "INFO")}

# Database Configuration
DB_PATH={config.get("database", {}).get("path", "data/trading_log.db")}

# Telegram Configuration
TELEGRAM_ENABLED={str(config.get("telegram", {}).get("enabled", True)).lower()}

# External Services
AWS_CLOUDWATCH_ENABLED={str(config.get("external_services", {}).get("enabled", False)).lower()}
GCP_STACKDRIVER_ENABLED={str(config.get("external_services", {}).get("enabled", False)).lower()}
AZURE_MONITOR_ENABLED={str(config.get("external_services", {}).get("enabled", False)).lower()}
"""

        with open(env_file, "w", encoding="utf-8") as f:
            f.write(env_content)

        print(f"✅ Создан файл переменных окружения: {env_file}")

    def show_environment_info(self, environment: str):
        """Показывает информацию о настройках среды"""
        if environment not in self.logging_config.get("environments", {}):
            print(f"❌ Неизвестная среда: {environment}")
            return

        env_config = self.logging_config["environments"][environment]
        print(f"\n📊 Информация о среде: {environment}")
        print(f"📋 Описание: {env_config.get('description', 'N/A')}")

        # Файловое логирование
        file_logging = env_config.get("file_logging", {})
        print("\n📁 Файловое логирование:")
        print(f"   • Включено: {file_logging.get('enabled', True)}")
        print(f"   • Уровень: {file_logging.get('log_level', 'INFO')}")
        print(f"   • Макс. размер: {file_logging.get('max_size_mb', 100)} MB")
        print(f"   • Хранение: {file_logging.get('retention_days', 30)} дней")

        # Консольное логирование
        console_logging = env_config.get("console_logging", {})
        print("\n🖥️ Консольное логирование:")
        print(f"   • Включено: {console_logging.get('enabled', True)}")
        print(f"   • Цвета: {console_logging.get('colors', True)}")
        print(f"   • Эмодзи: {console_logging.get('emojis', True)}")

        # Telegram
        telegram = env_config.get("telegram", {})
        print("\n📱 Telegram:")
        print(f"   • Включено: {telegram.get('enabled', True)}")
        print(f"   • Уведомления: {telegram.get('notifications', [])}")

        # Внешние сервисы
        external_services = env_config.get("external_services", {})
        print("\n☁️ Внешние сервисы:")
        print(f"   • Включено: {external_services.get('enabled', False)}")
        if external_services.get("enabled", False):
            if external_services.get("aws_cloudwatch", {}).get("enabled", False):
                print("   • AWS CloudWatch: ✅")
            if external_services.get("gcp_stackdriver", {}).get("enabled", False):
                print("   • GCP StackDriver: ✅")
            if external_services.get("azure_monitor", {}).get("enabled", False):
                print("   • Azure Monitor: ✅")

        # База данных
        database = env_config.get("database", {})
        print("\n🗄️ База данных:")
        print(f"   • Путь: {database.get('path', 'data/trading_log.db')}")
        print(f"   • Резервное копирование: {database.get('backup_enabled', True)}")


def main():
    """Главная функция"""
    if len(sys.argv) < 2:
        print("🚀 Скрипт настройки логирования")
        print("=" * 50)
        print("Использование:")
        print("  python scripts/setup_logging.py <environment>")
        print("  python scripts/setup_logging.py info <environment>")
        print("\nДоступные среды:")
        print("  local      - Локальная разработка в VS Code")
        print("  vps        - VPS сервер")
        print("  cloud      - Облачные сервисы (AWS/GCP/Azure)")
        print("  production - Продакшен среда")
        print("\nПримеры:")
        print("  python scripts/setup_logging.py local")
        print("  python scripts/setup_logging.py info cloud")
        return

    setup = LoggingSetup()

    if sys.argv[1] == "info":
        if len(sys.argv) < 3:
            print("❌ Укажите среду для просмотра информации")
            return
        setup.show_environment_info(sys.argv[2])
    else:
        setup.setup_environment(sys.argv[1])


if __name__ == "__main__":
    main()
