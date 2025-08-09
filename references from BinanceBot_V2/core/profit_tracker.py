#!/usr/bin/env python3
"""
Profit Tracker для BinanceBot_V2
Мониторинг прибыльности в реальном времени и автоматическая корректировка параметров
"""

import asyncio
import time
from collections import deque
from datetime import datetime
from typing import Any

from core.unified_logger import UnifiedLogger


class ProfitTracker:
    """🚀 Система отслеживания прибыльности для $2/час цели"""

    def __init__(self, config, logger: UnifiedLogger | None = None):
        self.config = config
        self.logger = logger

        # Цели прибыльности
        self.profit_target_hourly = getattr(config, "profit_target_hourly", 0.7)
        self.profit_target_daily = getattr(config, "profit_target_daily", 16.8)
        self.min_win_rate = getattr(config, "min_win_rate", 0.65)
        self.max_daily_loss = getattr(config, "max_daily_loss", 20.0)

        # Трекинг сделок
        self.trades_history = deque(maxlen=1000)
        self.hourly_profits = deque(maxlen=24)
        self.daily_profits = deque(maxlen=30)

        # Статистика
        self.current_hour_profit = 0.0
        self.current_day_profit = 0.0
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0

        # Адаптивные параметры
        self.aggression_level = 1.0  # 1.0 = нормальный, 1.5 = агрессивный, 0.7 = консервативный
        self.position_size_multiplier = 1.0
        self.tp_target_multiplier = 1.0

        # Мониторинг
        self.last_hour_check = time.time()
        self.last_day_check = time.time()
        self.is_running = False

        # Callbacks для автоматической корректировки
        self.adjustment_callbacks = []

    async def start_tracking(self):
        """Запуск отслеживания прибыльности"""
        self.is_running = True
        self.logger.log_event(
            "PROFIT_TRACKER",
            "INFO",
            f"🚀 Запуск отслеживания прибыльности. Цель: ${self.profit_target_hourly}/час",
        )

        # Запускаем мониторинг
        asyncio.create_task(self._profit_monitoring_loop())

    async def stop_tracking(self):
        """Остановка отслеживания"""
        self.is_running = False
        self.logger.log_event("PROFIT_TRACKER", "INFO", "🛑 Остановка отслеживания прибыльности")

    async def _profit_monitoring_loop(self):
        """Основной цикл мониторинга прибыльности"""
        while self.is_running:
            try:
                current_time = time.time()

                # Проверка каждый час
                if current_time - self.last_hour_check >= 3600:
                    await self._check_hourly_performance()
                    self.last_hour_check = current_time

                # Проверка каждый день
                if current_time - self.last_day_check >= 86400:
                    await self._check_daily_performance()
                    self.last_day_check = current_time

                await asyncio.sleep(60)  # Проверка каждую минуту

            except Exception as e:
                self.logger.log_event("PROFIT_TRACKER", "ERROR", f"Ошибка мониторинга: {e}")
                await asyncio.sleep(60)

    async def record_trade(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        exit_price: float,
        quantity: float,
        pnl: float,
        duration_seconds: float,
    ):
        """Запись новой сделки"""
        trade_data = {
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "quantity": quantity,
            "pnl": pnl,
            "duration_seconds": duration_seconds,
            "hour": datetime.now().hour,
            "day": datetime.now().date().isoformat(),
        }

        self.trades_history.append(trade_data)
        self.total_trades += 1

        if pnl > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1

        # Обновляем текущую прибыль
        self.current_hour_profit += pnl
        self.current_day_profit += pnl

        # Логируем сделку
        win_rate = self.winning_trades / max(self.total_trades, 1)
        self.logger.log_event(
            "PROFIT_TRACKER",
            "INFO",
            f"💰 Сделка {symbol}: {pnl:.2f} USDC | Винрейт: {win_rate:.1%} | "
            f"Час: ${self.current_hour_profit:.2f} | День: ${self.current_day_profit:.2f}",
        )

        # Проверяем необходимость корректировки
        await self._check_performance_and_adjust()

    async def _check_hourly_performance(self):
        """Проверка часовой производительности"""
        target_hourly = self.profit_target_hourly
        current_hourly = self.current_hour_profit

        self.hourly_profits.append(current_hourly)

        # Анализируем производительность
        if current_hourly < target_hourly * 0.5:  # Меньше 50% от цели
            await self._increase_aggression()
        elif current_hourly > target_hourly * 1.5:  # Больше 150% от цели
            await self._reduce_risk()
        elif current_hourly >= target_hourly:
            self.logger.log_event(
                "PROFIT_TRACKER",
                "SUCCESS",
                f"🎯 Цель достигнута! ${current_hourly:.2f}/час (цель: ${target_hourly})",
            )

        # Сбрасываем счетчик часа
        self.current_hour_profit = 0.0

    async def _check_daily_performance(self):
        """Проверка дневной производительности"""
        target_daily = self.profit_target_daily
        current_daily = self.current_day_profit

        self.daily_profits.append(current_daily)

        if current_daily < target_daily * 0.3:  # Меньше 30% от дневной цели
            await self._emergency_adjustment()
        elif current_daily >= target_daily:
            self.logger.log_event(
                "PROFIT_TRACKER",
                "SUCCESS",
                f"🎯 Дневная цель достигнута! ${current_daily:.2f}/день (цель: ${target_daily})",
            )

        # Сбрасываем счетчик дня
        self.current_day_profit = 0.0

    async def _check_performance_and_adjust(self):
        """Проверка производительности и автоматическая корректировка"""
        win_rate = self.winning_trades / max(self.total_trades, 1)

        # Проверяем винрейт
        if win_rate < self.min_win_rate and self.total_trades >= 10:
            await self._improve_win_rate()

        # Проверяем дневные потери
        if self.current_day_profit < -self.max_daily_loss:
            await self._emergency_stop()

        # Проверяем часовую производительность для адаптации
        if self.total_trades >= 5:  # Минимум 5 сделок для анализа
            if self.current_hour_profit < self.profit_target_hourly * 0.5:
                await self._increase_aggression()
            elif self.current_hour_profit > self.profit_target_hourly * 1.5:
                await self._reduce_risk()

    async def _increase_aggression(self):
        """Увеличение агрессивности торговли"""
        self.aggression_level = min(self.aggression_level * 1.2, 2.0)
        self.position_size_multiplier = min(self.position_size_multiplier * 1.1, 1.5)
        self.tp_target_multiplier = max(self.tp_target_multiplier * 0.9, 0.7)

        self.logger.log_event(
            "PROFIT_TRACKER",
            "WARNING",
            f"📈 Увеличиваем агрессивность: уровень {self.aggression_level:.2f}",
        )

        # Вызываем callbacks
        for callback in self.adjustment_callbacks:
            try:
                await callback(
                    "increase_aggression",
                    {
                        "aggression_level": self.aggression_level,
                        "position_size_multiplier": self.position_size_multiplier,
                        "tp_target_multiplier": self.tp_target_multiplier,
                    },
                )
            except Exception as e:
                self.logger.log_event("PROFIT_TRACKER", "ERROR", f"Callback error: {e}")

    async def _reduce_risk(self):
        """Снижение риска"""
        self.aggression_level = max(self.aggression_level * 0.9, 0.5)
        self.position_size_multiplier = max(self.position_size_multiplier * 0.9, 0.7)
        self.tp_target_multiplier = min(self.tp_target_multiplier * 1.1, 1.3)

        self.logger.log_event(
            "PROFIT_TRACKER", "INFO", f"📉 Снижаем риск: уровень {self.aggression_level:.2f}"
        )

        # Вызываем callbacks
        for callback in self.adjustment_callbacks:
            try:
                await callback(
                    "reduce_risk",
                    {
                        "aggression_level": self.aggression_level,
                        "position_size_multiplier": self.position_size_multiplier,
                        "tp_target_multiplier": self.tp_target_multiplier,
                    },
                )
            except Exception as e:
                self.logger.log_event("PROFIT_TRACKER", "ERROR", f"Callback error: {e}")

    async def _improve_win_rate(self):
        """Улучшение винрейта"""
        self.aggression_level = max(self.aggression_level * 0.8, 0.5)
        self.tp_target_multiplier = min(self.tp_target_multiplier * 1.2, 1.5)

        self.logger.log_event(
            "PROFIT_TRACKER",
            "WARNING",
            f"🎯 Улучшаем винрейт: снижаем агрессивность до {self.aggression_level:.2f}",
        )

    async def _emergency_adjustment(self):
        """Экстренная корректировка при плохой производительности"""
        self.aggression_level = 0.5
        self.position_size_multiplier = 0.5
        self.tp_target_multiplier = 1.5

        self.logger.log_event(
            "PROFIT_TRACKER", "CRITICAL", "🚨 ЭКСТРЕННАЯ КОРРЕКТИРОВКА: Снижаем все параметры"
        )

    async def _emergency_stop(self):
        """Экстренная остановка при превышении дневных потерь"""
        self.logger.log_event(
            "PROFIT_TRACKER",
            "CRITICAL",
            f"🚨 ЭКСТРЕННАЯ ОСТАНОВКА: Дневные потери ${self.current_day_profit:.2f} превышают лимит ${self.max_daily_loss}",
        )

        # Вызываем callbacks для экстренной остановки
        for callback in self.adjustment_callbacks:
            try:
                await callback("emergency_stop", {"daily_loss": self.current_day_profit})
            except Exception as e:
                self.logger.log_event("PROFIT_TRACKER", "ERROR", f"Emergency callback error: {e}")

    def add_adjustment_callback(self, callback):
        """Добавление callback для автоматической корректировки"""
        self.adjustment_callbacks.append(callback)

    def get_profit_stats(self) -> dict[str, Any]:
        """Получение статистики прибыльности"""
        win_rate = self.winning_trades / max(self.total_trades, 1)
        avg_hourly = sum(self.hourly_profits) / max(len(self.hourly_profits), 1)
        avg_daily = sum(self.daily_profits) / max(len(self.daily_profits), 1)

        return {
            "current_hour_profit": self.current_hour_profit,
            "current_day_profit": self.current_day_profit,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": win_rate,
            "avg_hourly_profit": avg_hourly,
            "avg_daily_profit": avg_daily,
            "aggression_level": self.aggression_level,
            "position_size_multiplier": self.position_size_multiplier,
            "tp_target_multiplier": self.tp_target_multiplier,
            "profit_target_hourly": self.profit_target_hourly,
            "profit_target_daily": self.profit_target_daily,
        }

    def get_performance_summary(self) -> str:
        """Получение краткой сводки производительности"""
        stats = self.get_profit_stats()

        return (
            f"💰 Прибыльность: ${stats['current_hour_profit']:.2f}/час | "
            f"${stats['current_day_profit']:.2f}/день | "
            f"Винрейт: {stats['win_rate']:.1%} | "
            f"Агрессивность: {stats['aggression_level']:.2f}"
        )

    async def update_stats(self):
        """Обновление статистики (заглушка для совместимости)"""
        # Этот метод вызывается из торгового цикла для обновления статистики
        # В текущей реализации статистика обновляется автоматически в record_trade
        pass
