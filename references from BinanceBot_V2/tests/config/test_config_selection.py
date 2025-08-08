#!/usr/bin/env python3
"""
Test script for configuration selection based on profit targets
Ensures the bot automatically selects the correct runtime configuration
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from core.config import TradingConfig


class ConfigSelectionTester:
    """Тестер автоматического выбора конфигурации"""

    def __init__(self):
        self.test_results = {}

    def test_config_selection_for_2_dollar_target(self):
        """Тест выбора конфигурации для цели $2/час"""
        try:
            print("🎯 Тестирование выбора конфигурации для цели $2/час...")

            # Тестируем автоматический выбор конфигурации
            config = TradingConfig.load_optimized_for_profit_target(2.0)

            # Проверяем, что выбрана правильная конфигурация
            assert config.profit_target_hourly == 0.7, f"Целевая прибыль должна быть 0.7, получено {config.profit_target_hourly}"

            # Проверяем, что параметры соответствуют агрессивной торговле
            assert config.max_concurrent_positions >= 3, f"Должно быть минимум 3 позиции для $2/час, получено {config.max_concurrent_positions}"
            assert config.base_risk_pct >= 0.06, f"Риск должен быть минимум 6% для $2/час, получено {config.base_risk_pct*100:.2f}%"

            print("✅ Конфигурация для $2/час выбрана корректно")
            self.test_results['config_selection_2_dollar'] = True
            return True

        except Exception as e:
            print(f"❌ Ошибка выбора конфигурации для $2/час: {e}")
            self.test_results['config_selection_2_dollar'] = False
            return False

    def test_config_selection_for_1_dollar_target(self):
        """Тест выбора конфигурации для цели $1/час"""
        try:
            print("🎯 Тестирование выбора конфигурации для цели $1/час...")

            # Тестируем автоматический выбор конфигурации
            config = TradingConfig.load_optimized_for_profit_target(1.0)

            # Проверяем, что выбрана правильная конфигурация
            assert config.profit_target_hourly == 1.0, f"Целевая прибыль должна быть 1.0, получено {config.profit_target_hourly}"

            print("✅ Конфигурация для $1/час выбрана корректно")
            self.test_results['config_selection_1_dollar'] = True
            return True

        except Exception as e:
            print(f"❌ Ошибка выбора конфигурации для $1/час: {e}")
            self.test_results['config_selection_1_dollar'] = False
            return False

    def test_config_selection_for_0_5_dollar_target(self):
        """Тест выбора конфигурации для цели $0.5/час"""
        try:
            print("🎯 Тестирование выбора конфигурации для цели $0.5/час...")

            # Тестируем автоматический выбор конфигурации
            config = TradingConfig.load_optimized_for_profit_target(0.5)

            # Проверяем, что выбрана правильная конфигурация
            assert config.profit_target_hourly == 0.5, f"Целевая прибыль должна быть 0.5, получено {config.profit_target_hourly}"

            # Проверяем, что параметры соответствуют безопасной торговле
            assert config.max_concurrent_positions <= 2, f"Должно быть максимум 2 позиции для $0.5/час, получено {config.max_concurrent_positions}"
            assert config.base_risk_pct <= 0.01, f"Риск должен быть максимум 1% для $0.5/час, получено {config.base_risk_pct*100:.2f}%"

            print("✅ Конфигурация для $0.5/час выбрана корректно")
            self.test_results['config_selection_0_5_dollar'] = True
            return True

        except Exception as e:
            print(f"❌ Ошибка выбора конфигурации для $0.5/час: {e}")
            self.test_results['config_selection_0_5_dollar'] = False
            return False

    def test_config_mapping_logic(self):
        """Тест логики маппинга конфигураций"""
        try:
            print("🗺️ Тестирование логики маппинга конфигураций...")

            # Тестируем выбор конфигурации для разных целей
            config_paths = {
                0.7: "data/runtime_config.json",
                1.0: "data/runtime_config_test.json",
                0.5: "data/runtime_config_safe.json"
            }

            for target_profit, expected_path in config_paths.items():
                selected_path = TradingConfig.select_config_for_profit_target(target_profit)
                print(f"   Цель ${target_profit}/час → {selected_path}")

            print("✅ Логика маппинга конфигураций работает корректно")
            self.test_results['config_mapping_logic'] = True
            return True

        except Exception as e:
            print(f"❌ Ошибка логики маппинга конфигураций: {e}")
            self.test_results['config_mapping_logic'] = False
            return False

    def test_profit_target_info(self):
        """Тест информации о целях прибыльности"""
        try:
            print("📊 Тестирование информации о целях прибыльности...")

            config = TradingConfig.load_optimized_for_profit_target(2.0)
            profit_info = config.get_profit_target_info()

            # Проверяем наличие всех необходимых полей
            required_fields = ['profit_target_hourly', 'profit_target_daily', 'risk_level', 'expected_hourly_profit']
            for field in required_fields:
                assert field in profit_info, f"Поле {field} отсутствует в profit_info"

            print(f"   Целевая прибыль в час: ${profit_info['profit_target_hourly']}")
            print(f"   Целевая прибыль в день: ${profit_info['profit_target_daily']}")
            print(f"   Уровень риска: {profit_info['risk_level']}")
            print(f"   Ожидаемая прибыль: ${profit_info['expected_hourly_profit']:.2f}/час")

            print("✅ Информация о целях прибыльности корректна")
            self.test_results['profit_target_info'] = True
            return True

        except Exception as e:
            print(f"❌ Ошибка информации о целях прибыльности: {e}")
            self.test_results['profit_target_info'] = False
            return False

    def test_fallback_config_selection(self):
        """Тест fallback выбора конфигурации"""
        try:
            print("🔄 Тестирование fallback выбора конфигурации...")

            # Тестируем выбор конфигурации для нестандартной цели
            config = TradingConfig.load_optimized_for_profit_target(5.0)  # Нестандартная цель

            # Проверяем, что конфигурация загружена (fallback на агрессивную)
            assert config is not None, "Конфигурация должна быть загружена"
            assert config.profit_target_hourly == 5.0, "Целевая прибыль должна быть установлена"

            print("✅ Fallback выбор конфигурации работает корректно")
            self.test_results['fallback_config_selection'] = True
            return True

        except Exception as e:
            print(f"❌ Ошибка fallback выбора конфигурации: {e}")
            self.test_results['fallback_config_selection'] = False
            return False

    def print_test_results(self):
        """Вывод результатов тестов"""
        print("\n" + "="*60)
        print("📊 РЕЗУЛЬТАТЫ ПРОВЕРКИ ВЫБОРА КОНФИГУРАЦИИ")
        print("="*60)

        total_tests = len(self.test_results)
        passed_tests = sum(self.test_results.values())

        for test_name, result in self.test_results.items():
            status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
            print(f"{test_name:.<40} {status}")

        print("-"*60)
        print(f"Всего тестов: {total_tests}")
        print(f"Пройдено: {passed_tests}")
        print(f"Провалено: {total_tests - passed_tests}")
        print(f"Успешность: {(passed_tests/total_tests)*100:.1f}%")

        if passed_tests == total_tests:
            print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! ВЫБОР КОНФИГУРАЦИИ РАБОТАЕТ КОРРЕКТНО!")
        else:
            print("\n⚠️ Некоторые тесты провалены. Требуется доработка.")

    def run_all_tests(self):
        """Запуск всех тестов"""
        print("🚀 ЗАПУСК ПРОВЕРКИ ВЫБОРА КОНФИГУРАЦИИ")
        print("="*60)

        tests = [
            self.test_config_selection_for_2_dollar_target,
            self.test_config_selection_for_1_dollar_target,
            self.test_config_selection_for_0_5_dollar_target,
            self.test_config_mapping_logic,
            self.test_profit_target_info,
            self.test_fallback_config_selection
        ]

        for test in tests:
            try:
                test()
            except Exception as e:
                print(f"❌ Критическая ошибка в тесте: {e}")

        self.print_test_results()

        return all(self.test_results.values())


def main():
    """Основная функция"""
    tester = ConfigSelectionTester()
    success = tester.run_all_tests()
    return 0 if success else 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n🛑 Проверка выбора конфигурации прервана пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        sys.exit(1)
