#!/usr/bin/env python3
"""
Скрипт для переключения между конфигурациями
"""

import json
import os
import shutil
import sys
import time


def switch_config(config_type):
    """Переключает конфигурацию"""

    config_files = {
        "safe": "data/runtime_config_safe.json",
        "test": "data/runtime_config_test.json",
        "aggressive": "data/runtime_config.json",
        "default": "data/runtime_config.json",
    }

    if config_type not in config_files:
        print(f"❌ Неизвестный тип конфигурации: {config_type}")
        print(f"Доступные типы: {', '.join(config_files.keys())}")
        return False

    source_file = config_files[config_type]
    target_file = "data/runtime_config.json"

    if not os.path.exists(source_file):
        print(f"❌ Файл конфигурации не найден: {source_file}")
        return False

    try:
        # Создаем резервную копию текущей конфигурации
        if os.path.exists(target_file):
            backup_file = f"data/runtime_config_backup_{int(time.time())}.json"
            shutil.copy2(target_file, backup_file)
            print(f"✅ Создана резервная копия: {backup_file}")

        # Копируем новую конфигурацию
        shutil.copy2(source_file, target_file)
        print(f"✅ Конфигурация переключена на: {config_type}")

        # Показываем основные параметры
        with open(target_file) as f:
            config = json.load(f)

        print(f"\n📊 Основные параметры ({config_type}):")
        print(f"   • Макс. позиций: {config['max_concurrent_positions']}")
        print(f"   • Риск: {config['base_risk_pct'] * 100:.2f}%")
        print(f"   • Stop Loss: {config['sl_percent'] * 100:.2f}%")
        print(f"   • Макс. время удержания: {config['max_hold_minutes']} мин")
        print(f"   • Макс. размер позиции: {config['max_position_size_usdc']} USDC")

        return True

    except Exception as e:
        print(f"❌ Ошибка переключения конфигурации: {e}")
        return False


def show_available_configs():
    """Показывает доступные конфигурации"""

    configs = {
        "safe": {
            "description": "Безопасная торговля - низкий риск, стабильная прибыль",
            "risk": "0.5%",
            "positions": "1",
            "hold_time": "15 мин",
        },
        "test": {
            "description": "Быстрые тесты - короткие позиции, быстрые результаты",
            "risk": "1.0%",
            "positions": "1",
            "hold_time": "2 мин",
        },
        "aggressive": {
            "description": "Агрессивная торговля - высокий риск, высокая прибыль",
            "risk": "2.0%",
            "positions": "3",
            "hold_time": "8 мин",
        },
        "default": {
            "description": "Текущая конфигурация (тестовая)",
            "risk": "1.0%",
            "positions": "1",
            "hold_time": "2 мин",
        },
    }

    print("📋 ДОСТУПНЫЕ КОНФИГУРАЦИИ:")
    print("=" * 50)

    for name, info in configs.items():
        print(f"\n🔧 {name.upper()}:")
        print(f"   📝 {info['description']}")
        print(f"   ⚠️  Риск: {info['risk']}")
        print(f"   📊 Позиций: {info['positions']}")
        print(f"   ⏱️  Время удержания: {info['hold_time']}")


if __name__ == "__main__":
    import time

    if len(sys.argv) < 2:
        print("🔧 ПЕРЕКЛЮЧЕНИЕ КОНФИГУРАЦИЙ")
        print("=" * 40)
        show_available_configs()
        print("\n💡 Использование: python scripts/switch_config.py <тип>")
        print("   Примеры:")
        print("   • python scripts/switch_config.py safe")
        print("   • python scripts/switch_config.py test")
        print("   • python scripts/switch_config.py aggressive")
        sys.exit(0)

    config_type = sys.argv[1].lower()

    if switch_config(config_type):
        print(f"\n✅ Конфигурация успешно переключена на: {config_type}")
        print("🚀 Теперь можно запускать бота с новой конфигурацией!")
    else:
        print("\n❌ Не удалось переключить конфигурацию")
        sys.exit(1)
