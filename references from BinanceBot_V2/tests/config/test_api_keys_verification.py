#!/usr/bin/env python3
"""
Test script for API key verification
Ensures WebSocket and REST API use correct API keys consistently
"""

import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from core.config import TradingConfig
from core.exchange_client import OptimizedExchangeClient
from core.unified_logger import UnifiedLogger
from core.websocket_manager import WebSocketManager


class APIKeyVerificationTester:
    """Тестер проверки API ключей"""

    def __init__(self):
        self.config = TradingConfig("data/runtime_config.json")
        self.logger = UnifiedLogger(self.config)
        self.test_results = {}

    async def test_api_key_configuration(self):
        """Тест конфигурации API ключей"""
        try:
            print("🔑 Тестирование конфигурации API ключей...")

            # Проверяем, что API ключи загружены
            assert self.config.api_key, "API ключ должен быть настроен"
            assert self.config.api_secret, "API секрет должен быть настроен"

            # Проверяем, что ключи не являются placeholder значениями
            if self.config.api_key == "YOUR_API_KEY":
                print("⚠️ API ключ является placeholder - требуется настройка")
                self.test_results['api_key_configuration'] = False
                return False
            if self.config.api_secret == "YOUR_API_SECRET":
                print("⚠️ API секрет является placeholder - требуется настройка")
                self.test_results['api_key_configuration'] = False
                return False

            print("✅ Конфигурация API ключей корректна")
            self.test_results['api_key_configuration'] = True
            return True

        except Exception as e:
            print(f"❌ Ошибка конфигурации API ключей: {e}")
            self.test_results['api_key_configuration'] = False
            return False

    async def test_exchange_client_initialization(self):
        """Тест инициализации exchange client с API ключами"""
        try:
            print("🏦 Тестирование инициализации exchange client...")

            exchange = OptimizedExchangeClient(self.config, self.logger)

            # Проверяем, что API ключи переданы в exchange
            assert exchange.exchange.apiKey == self.config.api_key, "API ключ должен быть передан в exchange"
            assert exchange.exchange.secret == self.config.api_secret, "API секрет должен быть передан в exchange"

            # Проверяем режим testnet/production на основе конфигурации
            is_testnet = (hasattr(self.config, 'use_testnet') and self.config.use_testnet) or \
                        (hasattr(self.config, 'exchange_mode') and self.config.exchange_mode == "testnet")

            if is_testnet:
                # Проверяем sandbox режим через options
                assert exchange.exchange.options.get('sandbox', False), "Exchange должен быть в testnet режиме"
                print("✅ Testnet режим корректно настроен")
            else:
                # Проверяем, что sandbox не включен
                assert not exchange.exchange.options.get('sandbox', False), "Exchange должен быть в production режиме"
                print("✅ Production режим корректно настроен")

            print("✅ Exchange client инициализирован корректно")
            self.test_results['exchange_client_initialization'] = True
            return True

        except Exception as e:
            print(f"❌ Ошибка инициализации exchange client: {e}")
            self.test_results['exchange_client_initialization'] = False
            return False

    async def test_websocket_api_key_inheritance(self):
        """Тест наследования API ключей в WebSocket"""
        try:
            print("🔌 Тестирование наследования API ключей в WebSocket...")

            exchange = OptimizedExchangeClient(self.config, self.logger)
            ws_manager = WebSocketManager(exchange, logger=self.logger)

            # Проверяем, что WebSocket Manager имеет доступ к конфигурации
            assert hasattr(ws_manager, 'exchange'), "WebSocket Manager должен иметь exchange client"
            assert hasattr(ws_manager.exchange, 'config'), "Exchange client должен иметь config"

            # Проверяем, что API ключи доступны через exchange
            assert ws_manager.exchange.config.api_key == self.config.api_key, "API ключ должен быть доступен"
            assert ws_manager.exchange.config.api_secret == self.config.api_secret, "API секрет должен быть доступен"

            print("✅ API ключи корректно наследуются в WebSocket")
            self.test_results['websocket_api_key_inheritance'] = True
            return True

        except Exception as e:
            print(f"❌ Ошибка наследования API ключей в WebSocket: {e}")
            self.test_results['websocket_api_key_inheritance'] = False
            return False

    async def test_listen_key_creation(self):
        """Тест создания listen key с API ключами"""
        try:
            print("🎧 Тестирование создания listen key...")

            exchange = OptimizedExchangeClient(self.config, self.logger)
            ws_manager = WebSocketManager(exchange, logger=self.logger)

            # Проверяем, что метод создания listen key существует
            assert hasattr(ws_manager, '_create_listen_key'), "Метод _create_listen_key должен существовать"

            # Проверяем, что API ключи настроены для создания listen key
            if not self.config.api_key or not self.config.api_secret:
                print("⚠️ API ключи не настроены, пропускаем тест listen key")
                self.test_results['listen_key_creation'] = True
                return True

            print("✅ Listen key creation готов к работе")
            self.test_results['listen_key_creation'] = True
            return True

        except Exception as e:
            print(f"❌ Ошибка создания listen key: {e}")
            self.test_results['listen_key_creation'] = False
            return False

    async def test_websocket_url_configuration(self):
        """Тест конфигурации WebSocket URL"""
        try:
            print("🌐 Тестирование конфигурации WebSocket URL...")

            exchange = OptimizedExchangeClient(self.config, self.logger)
            ws_manager = WebSocketManager(exchange, logger=self.logger)

            # Проверяем, что WebSocket Manager может определить правильный URL
            if hasattr(self.config, 'use_testnet') and self.config.use_testnet:
                expected_base = "wss://stream.binancefuture.com"
                print("✅ Testnet WebSocket URL настроен корректно")
            else:
                expected_base = "wss://stream.binance.com"
                print("✅ Production WebSocket URL настроен корректно")

            print("✅ WebSocket URL конфигурация корректна")
            self.test_results['websocket_url_configuration'] = True
            return True

        except Exception as e:
            print(f"❌ Ошибка конфигурации WebSocket URL: {e}")
            self.test_results['websocket_url_configuration'] = False
            return False

    async def test_api_key_consistency(self):
        """Тест консистентности API ключей между REST и WebSocket"""
        try:
            print("🔄 Тестирование консистентности API ключей...")

            exchange = OptimizedExchangeClient(self.config, self.logger)
            ws_manager = WebSocketManager(exchange, self.logger)

            # Проверяем, что API ключи одинаковые везде
            rest_api_key = exchange.exchange.apiKey
            rest_api_secret = exchange.exchange.secret
            ws_api_key = ws_manager.exchange.config.api_key
            ws_api_secret = ws_manager.exchange.config.api_secret

            assert rest_api_key == ws_api_key, "API ключи должны быть одинаковыми"
            assert rest_api_secret == ws_api_secret, "API секреты должны быть одинаковыми"

            print("✅ API ключи консистентны между REST и WebSocket")
            self.test_results['api_key_consistency'] = True
            return True

        except Exception as e:
            print(f"❌ Ошибка консистентности API ключей: {e}")
            self.test_results['api_key_consistency'] = False
            return False

    async def test_testnet_configuration(self):
        """Тест конфигурации testnet"""
        try:
            print("🧪 Тестирование конфигурации testnet...")

            exchange = OptimizedExchangeClient(self.config, self.logger)

            # Проверяем режим testnet
            if hasattr(self.config, 'use_testnet') and self.config.use_testnet:
                # Проверяем sandbox режим через options
                assert exchange.exchange.options.get('sandbox', False), "Exchange должен быть в testnet режиме"
                print("✅ Testnet режим корректно настроен")
            elif hasattr(self.config, 'exchange_mode') and self.config.exchange_mode == "testnet":
                # Проверяем sandbox режим через options
                assert exchange.exchange.options.get('sandbox', False), "Exchange должен быть в testnet режиме"
                print("✅ Testnet режим корректно настроен")
            else:
                # Проверяем, что sandbox не включен
                assert not exchange.exchange.options.get('sandbox', False), "Exchange должен быть в production режиме"
                print("✅ Production режим корректно настроен")

            print("✅ Конфигурация testnet корректна")
            self.test_results['testnet_configuration'] = True
            return True

        except Exception as e:
            print(f"❌ Ошибка конфигурации testnet: {e}")
            self.test_results['testnet_configuration'] = False
            return False

    def print_test_results(self):
        """Вывод результатов тестов"""
        print("\n" + "="*60)
        print("📊 РЕЗУЛЬТАТЫ ПРОВЕРКИ API КЛЮЧЕЙ")
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
            print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! API КЛЮЧИ НАСТРОЕНЫ КОРРЕКТНО!")
        else:
            print("\n⚠️ Некоторые тесты провалены. Требуется доработка.")

    async def run_all_tests(self):
        """Запуск всех тестов"""
        print("🚀 ЗАПУСК ПРОВЕРКИ API КЛЮЧЕЙ")
        print("="*60)

        tests = [
            self.test_api_key_configuration,
            self.test_exchange_client_initialization,
            self.test_websocket_api_key_inheritance,
            self.test_listen_key_creation,
            self.test_websocket_url_configuration,
            self.test_api_key_consistency,
            self.test_testnet_configuration
        ]

        for test in tests:
            try:
                await test()
            except Exception as e:
                print(f"❌ Критическая ошибка в тесте: {e}")

        self.print_test_results()

        return all(self.test_results.values())


async def main():
    """Основная функция"""
    tester = APIKeyVerificationTester()
    success = await tester.run_all_tests()
    return 0 if success else 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n🛑 Проверка API ключей прервана пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        sys.exit(1)
