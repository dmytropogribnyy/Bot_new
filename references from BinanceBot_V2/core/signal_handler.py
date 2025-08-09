#!/usr/bin/env python3
"""
Signal Handler для BinanceBot_V2
Обработка Ctrl-C и graceful shutdown
"""

import asyncio
import signal
import sys
from collections.abc import Callable
from typing import Any

from core.unified_logger import UnifiedLogger


class SignalHandler:
    """Обработчик сигналов для graceful shutdown"""

    def __init__(self, logger: UnifiedLogger):
        self.logger = logger
        self.shutdown_callback: Callable | None = None
        self.emergency_callback: Callable | None = None

        # Флаги состояния
        self.shutdown_requested = False
        self.emergency_requested = False

        # Регистрируем обработчики сигналов
        signal.signal(signal.SIGINT, self._handle_sigint)
        signal.signal(signal.SIGTERM, self._handle_sigterm)

        # Для Windows
        if hasattr(signal, "SIGBREAK"):
            signal.signal(signal.SIGBREAK, self._handle_sigbreak)

    def set_callbacks(self, shutdown_callback: Callable, emergency_callback: Callable):
        """Установка callback функций"""
        self.shutdown_callback = shutdown_callback
        self.emergency_callback = emergency_callback

    def _handle_sigint(self, signum, frame):
        """Обработка Ctrl-C (SIGINT)"""
        if self.shutdown_requested:
            # Второй Ctrl-C - экстренная остановка
            self.logger.log_event(
                "SIGNAL_HANDLER", "CRITICAL", "Second Ctrl-C detected - Emergency shutdown!"
            )
            self.emergency_requested = True
            if self.emergency_callback:
                asyncio.create_task(self.emergency_callback())
            sys.exit(1)
        else:
            # Первый Ctrl-C - graceful shutdown
            self.logger.log_event(
                "SIGNAL_HANDLER", "WARNING", "Ctrl-C detected - Graceful shutdown requested"
            )
            self.shutdown_requested = True
            if self.shutdown_callback:
                asyncio.create_task(self.shutdown_callback())

    def _handle_sigterm(self, signum, frame):
        """Обработка SIGTERM"""
        self.logger.log_event("SIGNAL_HANDLER", "WARNING", "SIGTERM received - Graceful shutdown")
        self.shutdown_requested = True
        if self.shutdown_callback:
            asyncio.create_task(self.shutdown_callback())

    def _handle_sigbreak(self, signum, frame):
        """Обработка SIGBREAK (Windows)"""
        self.logger.log_event("SIGNAL_HANDLER", "WARNING", "SIGBREAK received - Graceful shutdown")
        self.shutdown_requested = True
        if self.shutdown_callback:
            asyncio.create_task(self.shutdown_callback())

    def is_shutdown_requested(self) -> bool:
        """Проверка запроса на shutdown"""
        return self.shutdown_requested

    def is_emergency_requested(self) -> bool:
        """Проверка запроса на emergency shutdown"""
        return self.emergency_requested

    def reset(self):
        """Сброс флагов (для тестирования)"""
        self.shutdown_requested = False
        self.emergency_requested = False


class GracefulShutdown:
    """Система graceful shutdown для бота"""

    def __init__(self, logger: UnifiedLogger, order_manager, trading_engine, telegram_bot=None):
        self.logger = logger
        self.order_manager = order_manager
        self.trading_engine = trading_engine
        self.telegram_bot = telegram_bot

        self.signal_handler = SignalHandler(logger)
        self.signal_handler.set_callbacks(self.graceful_shutdown, self.emergency_shutdown)

        self.shutdown_in_progress = False

    async def graceful_shutdown(self):
        """Graceful shutdown - ждем завершения позиций"""
        if self.shutdown_in_progress:
            return

        self.shutdown_in_progress = True
        self.logger.log_event("SHUTDOWN", "WARNING", "Graceful shutdown initiated")

        try:
            # 1. Приостанавливаем торговлю
            self.trading_engine.pause_trading()

            # 2. Получаем активные позиции
            active_positions = self.order_manager.get_active_positions()

            if not active_positions:
                self.logger.log_event("SHUTDOWN", "INFO", "No active positions, shutdown complete")
                await self._finalize_shutdown()
                return

            # 3. Уведомляем через Telegram
            if self.telegram_bot:
                await self.telegram_bot.send_message(
                    f"🔄 Graceful shutdown initiated. Waiting for {len(active_positions)} positions to close..."
                )

            # 4. Ждем закрытия позиций (максимум 5 минут)
            timeout = 300  # 5 минут
            start_time = asyncio.get_event_loop().time()

            while active_positions and (asyncio.get_event_loop().time() - start_time) < timeout:
                await asyncio.sleep(10)  # Проверяем каждые 10 секунд
                active_positions = self.order_manager.get_active_positions()

                if active_positions:
                    self.logger.log_event(
                        "SHUTDOWN",
                        "INFO",
                        f"Waiting for {len(active_positions)} positions to close...",
                    )

            # 5. Проверяем результат
            remaining_positions = self.order_manager.get_active_positions()

            if remaining_positions:
                self.logger.log_event(
                    "SHUTDOWN",
                    "WARNING",
                    f"Timeout reached, {len(remaining_positions)} positions still active",
                )

                if self.telegram_bot:
                    await self.telegram_bot.send_message(
                        f"⚠️ Timeout reached, {len(remaining_positions)} positions still active. "
                        "Use /shutdown for emergency close."
                    )

                # Переходим к emergency shutdown
                await self.emergency_shutdown()
            else:
                self.logger.log_event("SHUTDOWN", "INFO", "All positions closed successfully")

                if self.telegram_bot:
                    await self.telegram_bot.send_message("✅ Graceful shutdown completed")

                await self._finalize_shutdown()

        except Exception as e:
            self.logger.log_event("SHUTDOWN", "ERROR", f"Graceful shutdown failed: {e}")
            await self.emergency_shutdown()

    async def emergency_shutdown(self):
        """Emergency shutdown - принудительное закрытие всех позиций"""
        if self.shutdown_in_progress:
            return

        self.shutdown_in_progress = True
        self.logger.log_event("SHUTDOWN", "CRITICAL", "Emergency shutdown initiated")

        try:
            # 1. Уведомляем через Telegram
            if self.telegram_bot:
                await self.telegram_bot.send_message("🚨 Emergency shutdown initiated!")

            # 2. Приостанавливаем торговлю
            self.trading_engine.pause_trading()

            # 3. Принудительно закрываем все позиции
            active_positions = self.order_manager.get_active_positions()
            closed_count = 0

            for position in active_positions:
                try:
                    result = await self.order_manager.close_position_emergency(position["symbol"])
                    if result["success"]:
                        closed_count += 1
                        self.logger.log_event(
                            "SHUTDOWN", "INFO", f"Emergency closed position: {position['symbol']}"
                        )
                    else:
                        self.logger.log_event(
                            "SHUTDOWN",
                            "ERROR",
                            f"Failed to close position {position['symbol']}: {result.get('error')}",
                        )
                except Exception as e:
                    self.logger.log_event(
                        "SHUTDOWN", "ERROR", f"Error closing position {position['symbol']}: {e}"
                    )

            # 4. Отчет о результатах
            total_positions = len(active_positions)
            self.logger.log_event(
                "SHUTDOWN",
                "INFO",
                f"Emergency shutdown completed: {closed_count}/{total_positions} positions closed",
            )

            if self.telegram_bot:
                await self.telegram_bot.send_message(
                    f"🚨 Emergency shutdown completed: {closed_count}/{total_positions} positions closed"
                )

            await self._finalize_shutdown()

        except Exception as e:
            self.logger.log_event("SHUTDOWN", "ERROR", f"Emergency shutdown failed: {e}")
            await self._finalize_shutdown()

    async def _finalize_shutdown(self):
        """Финальные действия при shutdown"""
        try:
            # 1. Останавливаем OrderManager
            await self.order_manager.shutdown(
                emergency=self.signal_handler.is_emergency_requested()
            )

            # 2. Останавливаем TradingEngine
            self.trading_engine.stop_trading()

            # 3. Останавливаем Telegram бота
            if self.telegram_bot:
                await self.telegram_bot.stop()

            # 4. Финальное сообщение
            self.logger.log_event("SHUTDOWN", "INFO", "Bot shutdown completed")

            # 5. Завершаем программу
            sys.exit(0)

        except Exception as e:
            self.logger.log_event("SHUTDOWN", "ERROR", f"Finalization failed: {e}")
            sys.exit(1)

    def get_status(self) -> dict[str, Any]:
        """Получение статуса shutdown"""
        return {
            "shutdown_in_progress": self.shutdown_in_progress,
            "shutdown_requested": self.signal_handler.is_shutdown_requested(),
            "emergency_requested": self.signal_handler.is_emergency_requested(),
            "active_positions": len(self.order_manager.get_active_positions()),
        }
