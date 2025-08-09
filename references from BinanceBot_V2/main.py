#!/usr/bin/env python3
"""
Упрощенный OptiFlow HFT Bot - основан на архитектуре старого бота
С асинхронными улучшениями и модульной структурой
"""

import asyncio
import sys

from core.config import TradingConfig
from core.exchange_client import OptimizedExchangeClient
from core.order_manager import OrderManager
from core.profit_tracker import ProfitTracker
from core.strategy_manager import StrategyManager
from core.symbol_manager import SymbolManager
from core.unified_logger import UnifiedLogger


class SimplifiedTradingBot:
    """Упрощенный торговый бот на основе старой архитектуры"""

    def __init__(self):
        self.config = TradingConfig()
        self.logger = UnifiedLogger(self.config)
        self.exchange = OptimizedExchangeClient(self.config, self.logger)
        self.order_manager = OrderManager(self.config, self.exchange, self.logger)
        self.strategy_manager = StrategyManager(self.config, self.logger)
        self.symbol_manager = SymbolManager(self.config, self.logger)
        self.profit_tracker = ProfitTracker(self.config, self.logger)

        # Получаем Telegram credentials
        telegram_token, telegram_chat_id = self.config.get_telegram_credentials()
        # Временно отключаем Telegram Bot для избежания конфликтов
        self.telegram_bot = None  # TelegramBot(telegram_token, telegram_chat_id, self.logger)

        self.running = False
        self.stop_event = asyncio.Event()

    async def initialize(self):
        """Инициализация всех компонентов"""
        try:
            self.logger.log_event("MAIN", "INFO", "🚀 Запуск упрощенного OptiFlow HFT Bot")

            # Инициализация компонентов
            self.logger.log_event("MAIN", "DEBUG", "🔧 Инициализация Exchange...")
            await self.exchange.initialize()
            self.logger.log_event("MAIN", "DEBUG", "✅ Exchange инициализирован")

            self.logger.log_event("MAIN", "DEBUG", "🔧 Инициализация OrderManager...")
            await self.order_manager.initialize()
            self.logger.log_event("MAIN", "DEBUG", "✅ OrderManager инициализирован")

            self.logger.log_event("MAIN", "DEBUG", "🔧 Инициализация StrategyManager...")
            await self.strategy_manager.initialize()
            self.logger.log_event("MAIN", "DEBUG", "✅ StrategyManager инициализирован")

            # Устанавливаем exchange в symbol_manager
            self.logger.log_event("MAIN", "DEBUG", "🔧 Настройка SymbolManager...")
            self.symbol_manager.set_exchange(self.exchange)
            await self.symbol_manager.initialize()
            self.logger.log_event("MAIN", "DEBUG", "✅ SymbolManager инициализирован")

            # Запускаем profit tracker
            self.logger.log_event("MAIN", "DEBUG", "🔧 Запуск ProfitTracker...")
            await self.profit_tracker.start_tracking()
            self.logger.log_event("MAIN", "DEBUG", "✅ ProfitTracker запущен")

            # Инициализируем telegram bot
            self.logger.log_event("MAIN", "DEBUG", "🔧 Инициализация TelegramBot...")
            if self.telegram_bot:
                try:
                    # Запускаем Telegram Bot в отдельной задаче, чтобы не блокировать основной поток
                    asyncio.create_task(self.telegram_bot.run())
                    self.logger.log_event("MAIN", "DEBUG", "✅ TelegramBot запущен в фоне")
                except Exception as e:
                    self.logger.log_event("MAIN", "WARNING", f"⚠️ Ошибка запуска TelegramBot: {e}")
                    self.telegram_bot = None  # Отключаем Telegram Bot при ошибке
            else:
                self.logger.log_event("MAIN", "WARNING", "⚠️ TelegramBot не настроен")

            self.running = True
            self.logger.log_event("MAIN", "INFO", "✅ Все компоненты инициализированы")

        except Exception as e:
            self.logger.log_event("MAIN", "ERROR", f"❌ Ошибка инициализации: {e}")
            import traceback

            self.logger.log_event("MAIN", "ERROR", f"Traceback: {traceback.format_exc()}")
            raise

    async def shutdown(self):
        """Корректное завершение работы"""
        self.logger.log_event("MAIN", "INFO", "🛑 Завершение работы бота...")
        self.running = False
        self.stop_event.set()

        # Закрытие всех компонентов
        await self.exchange.cleanup()
        await self.order_manager.shutdown()

        # Останавливаем profit tracker
        await self.profit_tracker.stop_tracking()

        self.logger.log_event("MAIN", "INFO", "✅ Бот остановлен")

    async def trading_loop(self):
        """Основной торговый цикл (упрощенный)"""
        self.logger.log_event("MAIN", "INFO", "🔄 Запуск торгового цикла")

        while self.running and not self.stop_event.is_set():
            try:
                self.logger.log_event("MAIN", "DEBUG", "🔄 Начало торгового цикла")

                # 1. Получаем активные символы
                self.logger.log_event("MAIN", "DEBUG", "📊 Получение активных символов...")
                symbols = await self.symbol_manager.get_active_symbols()
                self.logger.log_event(
                    "MAIN", "INFO", f"📊 Получено символов: {len(symbols) if symbols else 0}"
                )

                if not symbols:
                    self.logger.log_event("MAIN", "WARNING", "Нет активных символов")
                    await asyncio.sleep(5)
                    continue

                # 2. Проверяем лимиты позиций
                self.logger.log_event("MAIN", "DEBUG", "📈 Проверка лимитов позиций...")
                current_positions = self.order_manager.get_position_count()  # Убираем await
                max_positions = self.config.max_concurrent_positions
                self.logger.log_event(
                    "MAIN", "INFO", f"📈 Позиций: {current_positions}/{max_positions}"
                )

                if current_positions >= max_positions:
                    self.logger.log_event(
                        "MAIN",
                        "INFO",
                        f"Достигнут лимит позиций ({current_positions}/{max_positions})",
                    )
                    await asyncio.sleep(10)
                    continue

                # 3. Анализируем символы и ищем сигналы
                self.logger.log_event("MAIN", "DEBUG", f"🔍 Анализ символов: {symbols[:5]}")
                for symbol in symbols[:5]:  # Ограничиваем количество проверяемых символов
                    if self.stop_event.is_set():
                        break

                    try:
                        self.logger.log_event("MAIN", "DEBUG", f"📊 Анализ {symbol}...")

                        # Получаем данные для анализа
                        ohlcv = await self.exchange.get_ohlcv(symbol, "15m", 100)
                        if not ohlcv:
                            self.logger.log_event(
                                "MAIN", "DEBUG", f"❌ Нет данных OHLCV для {symbol}"
                            )
                            continue

                        # Анализируем сигнал
                        signal = await self.strategy_manager.analyze_symbol(symbol, ohlcv)
                        self.logger.log_event("MAIN", "DEBUG", f"📊 Сигнал для {symbol}: {signal}")

                        if signal and signal.get("should_enter"):
                            self.logger.log_event("MAIN", "INFO", f"🎯 Найден сигнал для {symbol}")

                            # Проверяем, что позиция еще не открыта
                            if not await self.order_manager.has_position(symbol):
                                self.logger.log_event(
                                    "MAIN", "INFO", f"🚀 Открываем позицию {symbol}"
                                )

                                # Открываем позицию
                                result = await self.order_manager.place_position_with_tp_sl(
                                    symbol=symbol,
                                    side=signal.get("side", "BUY"),
                                    quantity=signal.get("quantity", 0.001),
                                    entry_price=signal.get("entry_price", 0),
                                    leverage=5,
                                )

                                if result.get("success"):
                                    self.logger.log_event(
                                        "MAIN", "INFO", f"✅ Позиция открыта: {symbol} | {result}"
                                    )
                                    if self.telegram_bot:
                                        try:
                                            await self.telegram_bot.send_message(
                                                f"🚀 Открыта позиция: {symbol}\n"
                                                f"Сторона: {signal.get('side')}\n"
                                                f"Количество: {signal.get('quantity'):.6f}"
                                            )
                                        except Exception as e:
                                            self.logger.log_event(
                                                "MAIN",
                                                "WARNING",
                                                f"⚠️ Ошибка отправки в Telegram: {e}",
                                            )
                                else:
                                    self.logger.log_event(
                                        "MAIN",
                                        "ERROR",
                                        f"❌ Ошибка открытия позиции {symbol}: {result}",
                                    )
                            else:
                                self.logger.log_event(
                                    "MAIN", "DEBUG", f"⏭️ Позиция уже открыта для {symbol}"
                                )

                    except Exception as e:
                        self.logger.log_event("MAIN", "ERROR", f"Ошибка анализа {symbol}: {e}")
                        continue

                # 4. Мониторинг позиций
                self.logger.log_event("MAIN", "DEBUG", "📊 Мониторинг позиций...")
                await self.order_manager.monitor_positions()

                # 5. Обновление статистики
                self.logger.log_event("MAIN", "DEBUG", "📈 Обновление статистики...")
                await self.profit_tracker.update_stats()

                # Пауза между циклами
                self.logger.log_event("MAIN", "DEBUG", "⏸️ Пауза 5 секунд...")
                await asyncio.sleep(5)

            except Exception as e:
                self.logger.log_event("MAIN", "ERROR", f"Ошибка в торговом цикле: {e}")
                await asyncio.sleep(10)

    async def run(self):
        """Запуск бота"""
        try:
            self.logger.log_event("MAIN", "INFO", "🚀 Начало запуска бота...")
            await self.initialize()
            self.logger.log_event("MAIN", "INFO", "✅ Инициализация завершена")

            # Запускаем торговый цикл
            self.logger.log_event("MAIN", "INFO", "🔄 Запуск торгового цикла...")
            await self.trading_loop()
            self.logger.log_event("MAIN", "INFO", "✅ Торговый цикл завершен")

        except KeyboardInterrupt:
            self.logger.log_event("MAIN", "INFO", "Получен сигнал остановки")
        except Exception as e:
            self.logger.log_event("MAIN", "ERROR", f"Критическая ошибка: {e}")
            import traceback

            self.logger.log_event("MAIN", "ERROR", f"Traceback: {traceback.format_exc()}")
        finally:
            self.logger.log_event("MAIN", "INFO", "🛑 Начало завершения работы...")
            await self.shutdown()


async def main():
    """Точка входа"""
    bot = SimplifiedTradingBot()
    await bot.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен пользователем")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        sys.exit(1)
