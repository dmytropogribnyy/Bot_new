# core/trading_engine.py

import asyncio
from typing import Any


class TradingEngine:
    def __init__(
        self,
        config,
        exchange_client,
        symbol_selector,
        leverage_manager,
        risk_manager,
        logger,
        order_manager=None,
        strategy_manager=None,
        profit_tracker=None,
        external_monitoring=None,
    ):
        self.config = config
        self.exchange = exchange_client
        self.symbol_selector = symbol_selector
        self.leverage_manager = leverage_manager
        self.risk_manager = risk_manager
        self.logger = logger
        self.order_manager = order_manager
        self.strategy_manager = strategy_manager
        self.profit_tracker = profit_tracker
        self.external_monitoring = external_monitoring

        self.in_position = {}  # {symbol: position_data} - для обратной совместимости
        self.lock = asyncio.Lock()
        self.paused = False  # Флаг приостановки торговли
        self.running = True  # Флаг работы движка

    async def run_trading_cycle(self):
        while self.running:
            # Проверяем флаг приостановки
            if self.paused:
                self.logger.log_event("TRADING_ENGINE", "INFO", "Trading paused, waiting...")
                await asyncio.sleep(10)
                continue

            if not await self.risk_manager.is_trading_allowed():
                await asyncio.sleep(10)
                continue

            # Проверяем лимит позиций
            if self.order_manager:
                current_positions = self.order_manager.get_position_count()
                if current_positions >= self.config.max_concurrent_positions:
                    self.logger.log_event(
                        "TRADING_ENGINE",
                        "INFO",
                        f"Max positions reached ({current_positions}/{self.config.max_concurrent_positions})",
                    )
                    await asyncio.sleep(30)
                    continue

            active_symbols = await self.symbol_selector.get_symbols_for_trading()
            balance = await self.exchange.get_balance()

            for symbol in active_symbols:
                # Проверяем, не в позиции ли уже
                if self.order_manager:
                    positions = self.order_manager.get_active_positions()
                    if any(pos["symbol"] == symbol for pos in positions):
                        continue
                elif symbol in self.in_position:
                    continue

                entry_signal = await self.analyze_entry_signal(symbol)
                if not entry_signal:
                    continue

                leverage = self.leverage_manager.get_optimal_leverage(symbol, {})
                qty = self.risk_manager.calculate_position_size(
                    symbol, entry_signal["entry_price"], balance, leverage
                )

                if qty < self.config.min_trade_qty:
                    continue  # Micro position, skip

                await self.execute_trade(symbol, entry_signal, qty, leverage)

            await asyncio.sleep(5)  # Pause between cycles

    async def analyze_entry_signal(self, symbol: str) -> dict[str, Any] | None:
        """Анализирует сигнал входа с использованием StrategyManager"""
        try:
            if self.strategy_manager:
                # Получаем рыночные данные для анализа режима
                market_data = await self._get_market_data(symbol)

                # Используем гибридный сигнал от StrategyManager
                signal = await self.strategy_manager.get_hybrid_signal(symbol, market_data)
                if signal:
                    return signal

                # Fallback: используем оптимальную стратегию
                strategy = await self.strategy_manager.get_optimal_strategy(symbol, market_data)
                return await strategy.analyze_market(symbol)
            else:
                # Fallback без StrategyManager
                return {"side": "BUY", "entry_price": 50.0}

        except Exception as e:
            self.logger.log_event(
                "TRADING_ENGINE", "ERROR", f"Signal analysis failed for {symbol}: {e}"
            )
            return None

    async def _get_market_data(self, symbol: str) -> dict[str, Any]:
        """Получает рыночные данные для анализа"""
        try:
            # Получаем базовые данные
            ticker = await self.exchange.get_ticker(symbol)
            atr_percent = await self.symbol_selector.symbol_manager.get_atr_percent(symbol)

            return {
                "atr_percent": atr_percent,
                "price_change_percent": float(ticker.get("priceChangePercent", 0)),
                "volume_ratio": 1.0,  # TODO: Реализовать расчет
                "last_price": float(ticker.get("lastPrice", 0)),
            }
        except Exception as e:
            self.logger.log_event(
                "TRADING_ENGINE", "ERROR", f"Failed to get market data for {symbol}: {e}"
            )
            return {}

    async def execute_trade(
        self, symbol: str, entry_signal: dict[str, Any], qty: float, leverage: int
    ):
        """Выполнение торговой операции с использованием OrderManager"""
        async with self.lock:
            side = entry_signal["side"]
            entry_price = entry_signal["entry_price"]

            try:
                if self.order_manager:
                    # Используем OrderManager для размещения позиции с TP/SL
                    result = await self.order_manager.place_position_with_tp_sl(
                        symbol=symbol,
                        side=side,
                        quantity=qty,
                        entry_price=entry_price,
                        leverage=leverage,
                    )

                    if result["success"]:
                        # Обновляем локальный трекинг для обратной совместимости
                        self.in_position[symbol] = {
                            "entry_price": entry_price,
                            "qty": qty,
                            "side": side,
                        }

                        # Используем новый метод логирования торговых событий
                        self.logger.log_trading_event(
                            "ENTRY",
                            symbol,
                            {
                                "entry_price": entry_price,
                                "qty": qty,
                                "leverage": leverage,
                                "side": side,
                                "signal_strength": entry_signal.get("signal_strength", 0),
                                "reason": entry_signal.get("reason", "unknown"),
                            },
                        )

                        # Record trade in ProfitTracker if available
                        if self.profit_tracker:
                            try:
                                await self.profit_tracker.record_trade(
                                    symbol=symbol,
                                    side=side,
                                    entry_price=entry_price,
                                    exit_price=entry_price,  # Will be updated on exit
                                    quantity=qty,
                                    pnl=0.0,  # Will be calculated on exit
                                    duration_seconds=0,
                                )
                            except Exception as e:
                                self.logger.log_event(
                                    "TRADING_ENGINE",
                                    "WARNING",
                                    f"Failed to record trade in ProfitTracker: {e}",
                                )

                        if self.logger.config.telegram_enabled:
                            await self.logger.telegram.send_trade_notification(
                                {
                                    "symbol": symbol,
                                    "side": side,
                                    "price": entry_price,
                                    "quantity": qty,
                                }
                            )
                    else:
                        self.logger.log_trading_event(
                            "ENTRY_FAILED",
                            symbol,
                            {
                                "error": result.get("error"),
                                "entry_price": entry_price,
                                "qty": qty,
                                "side": side,
                            },
                        )

                else:
                    # Fallback без OrderManager
                    response = await self.exchange.place_order(symbol, side, qty)
                    if response.get("status") != "FILLED":
                        self.logger.log_event(
                            f"Order failed: {response}", "ERROR", "trading_engine"
                        )
                        return

                    self.in_position[symbol] = {
                        "entry_price": entry_price,
                        "qty": qty,
                        "side": side,
                    }
                    self.logger.log_trade(
                        symbol, side, qty, entry_price, "Position opened", 0.0, True
                    )

                    if self.logger.config.telegram_enabled:
                        await self.logger.telegram.send_trade_notification(
                            {
                                "symbol": symbol,
                                "side": side,
                                "price": entry_price,
                                "quantity": qty,
                            }
                        )

                    asyncio.create_task(self.monitor_position(symbol))

            except Exception as e:
                self.logger.log_trading_event(
                    "EXECUTION_ERROR",
                    symbol,
                    {"error": str(e), "entry_price": entry_price, "qty": qty, "side": side},
                )

    async def monitor_position(self, symbol: str):
        """Мониторинг позиции (fallback без OrderManager)"""
        if not self.order_manager:
            position = self.in_position[symbol]
            entry_price = position["entry_price"]
            qty = position["qty"]
            side = position["side"]

            await asyncio.sleep(300)  # Placeholder (5 minutes monitoring)

            await self.close_position(symbol, exit_price=entry_price * 1.01)  # Example +1%

    async def close_position(self, symbol: str, exit_price: float = None):
        """Закрывает позицию по символу"""
        async with self.lock:
            if self.order_manager:
                # Используем OrderManager для закрытия
                return await self.order_manager.close_position_emergency(symbol)
            else:
                # Fallback без OrderManager
                position = self.in_position.get(symbol)
                if not position:
                    return {"success": False, "error": "Position not found"}

                qty = position["qty"]
                side = "SELL" if position["side"] == "BUY" else "BUY"

                # Если exit_price не указан, получаем текущую цену
                if exit_price is None:
                    ticker = await self.exchange.get_ticker(symbol)
                    if ticker:
                        exit_price = float(ticker["lastPrice"])
                    else:
                        return {"success": False, "error": "Failed to get current price"}

                response = await self.exchange.place_order(symbol, side, qty)
                if response.get("status") != "FILLED":
                    self.logger.log_event(
                        f"Close order failed: {response}", "ERROR", "trading_engine"
                    )
                    return {"success": False, "error": f"Order failed: {response}"}

                pnl = (
                    (exit_price - position["entry_price"]) * qty
                    if side == "SELL"
                    else (position["entry_price"] - exit_price) * qty
                )
                win = pnl > 0

                self.logger.log_trade(symbol, side, qty, exit_price, "Position closed", pnl, win)

                if win:
                    await self.risk_manager.register_win()
                else:
                    await self.risk_manager.register_sl_hit()

                del self.in_position[symbol]

                self.logger.log_trading_event(
                    "EXIT",
                    symbol,
                    {
                        "pnl": pnl,
                        "win": win,
                        "exit_price": exit_price,
                        "entry_price": position["entry_price"],
                        "qty": qty,
                        "side": side,
                        "duration_seconds": 0,  # TODO: calculate actual duration
                    },
                )

                return {"success": True, "pnl": pnl, "win": win}

    def get_open_positions(self):
        """Получение активных позиций"""
        if self.order_manager:
            return self.order_manager.get_active_positions()
        else:
            # Fallback без OrderManager
            return [
                {
                    "symbol": symbol,
                    "side": data["side"],
                    "qty": data["qty"],
                    "entry_price": data["entry_price"],
                }
                for symbol, data in self.in_position.items()
            ]

    def get_capital_utilization(self) -> float:
        """Рассчитывает использование капитала"""
        try:
            if self.order_manager:
                positions = self.order_manager.get_active_positions()
                total_value = sum(
                    abs(pos.get("qty", 0) * pos.get("entry_price", 0)) for pos in positions
                )
                balance = (
                    self.exchange.get_balance() if hasattr(self.exchange, "get_balance") else 0
                )
                return (total_value / balance * 100) if balance > 0 else 0.0
            else:
                # Fallback без OrderManager
                total_value = sum(
                    abs(data.get("qty", 0) * data.get("entry_price", 0))
                    for data in self.in_position.values()
                )
                balance = (
                    self.exchange.get_balance() if hasattr(self.exchange, "get_balance") else 0
                )
                return (total_value / balance * 100) if balance > 0 else 0.0
        except Exception as e:
            self.logger.log_event(
                "TRADING_ENGINE", "ERROR", f"Capital utilization calculation failed: {e}"
            )
            return 0.0

    def pause_trading(self):
        """Приостанавливает торговлю"""
        self.paused = True
        self.logger.log_runtime_status(
            "PAUSED",
            {
                "reason": "manual_pause",
                "active_positions": len(self.get_open_positions()),
                "capital_utilization": self.get_capital_utilization(),
            },
        )

    def resume_trading(self):
        """Возобновляет торговлю"""
        self.paused = False
        self.logger.log_runtime_status(
            "ACTIVE",
            {
                "reason": "manual_resume",
                "active_positions": len(self.get_open_positions()),
                "capital_utilization": self.get_capital_utilization(),
            },
        )

    def stop_trading(self):
        """Полностью останавливает торговый движок"""
        self.running = False
        self.paused = True
        self.logger.log_runtime_status(
            "STOPPED",
            {
                "reason": "manual_stop",
                "active_positions": len(self.get_open_positions()),
                "capital_utilization": self.get_capital_utilization(),
            },
        )

    def get_performance_report(self, days: int = 1) -> dict[str, Any]:
        """Получает отчет о производительности"""
        try:
            if self.profit_tracker:
                stats = self.profit_tracker.get_profit_stats()
                return {
                    "pnl": stats.get("current_day_profit", 0.0),
                    "win_rate": stats.get("win_rate", 0.0),
                    "total_trades": stats.get("total_trades", 0),
                    "hourly_profit": stats.get("current_hour_profit", 0.0),
                    "aggression_level": stats.get("aggression_level", 1.0),
                }
            else:
                # Fallback без ProfitTracker
                return {
                    "pnl": 0.0,
                    "win_rate": 0.0,
                    "total_trades": 0,
                    "hourly_profit": 0.0,
                    "aggression_level": 1.0,
                }
        except Exception as e:
            self.logger.log_event("TRADING_ENGINE", "ERROR", f"Performance report failed: {e}")
            return {"pnl": 0.0, "win_rate": 0.0, "total_trades": 0}
