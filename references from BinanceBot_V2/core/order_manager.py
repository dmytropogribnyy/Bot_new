#!/usr/bin/env python3
"""
Order Manager для BinanceBot_V2
Управление ордерами TP/SL, синхронизация позиций, мониторинг
"""

import asyncio
import time
from typing import Any

from core.unified_logger import UnifiedLogger


class OrderManager:
    """Комплексная система управления ордерами и позициями"""

    def __init__(self, config, exchange_client, logger: UnifiedLogger, profit_tracker=None):
        self.config = config
        self.exchange = exchange_client
        self.logger = logger
        self.profit_tracker = profit_tracker

        # Трекинг позиций и ордеров
        self.active_positions: dict[str, dict] = {}  # symbol -> position_data
        self.pending_orders: dict[str, list[dict]] = {}  # symbol -> [orders]
        self.tp_orders: dict[str, list[dict]] = {}  # symbol -> [tp_orders]
        self.sl_orders: dict[str, dict] = {}  # symbol -> sl_order

        # Мониторинг и синхронизация
        self.last_sync_time = 0
        self.sync_interval = 30  # секунды
        self.order_timeout = 300  # 5 минут для висящих ордеров

        # Блокировки
        self.position_lock = asyncio.Lock()
        self.order_lock = asyncio.Lock()

        # Флаги состояния
        self.shutdown_requested = False
        self.emergency_mode = False

        # Флаг для отслеживания экстренного закрытия (персистентный)
        self.emergency_shutdown_flag = False
        self.shutdown_timestamp = None
        self.emergency_flag_file = "data/emergency_shutdown.flag"

        # Загружаем состояние флага при инициализации
        self._load_emergency_flag()

    def _load_emergency_flag(self):
        """Загрузка флага экстренного закрытия из файла"""
        try:
            import os
            if os.path.exists(self.emergency_flag_file):
                with open(self.emergency_flag_file) as f:
                    flag_data = f.read().strip()
                    if flag_data == 'EMERGENCY_SHUTDOWN':
                        self.emergency_shutdown_flag = True
                        self.logger.log_event("ORDER_MANAGER", "WARNING",
                            "Emergency shutdown flag detected from previous run")
        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR", f"Failed to load emergency flag: {e}")

    def _save_emergency_flag(self):
        """Сохранение флага экстренного закрытия в файл"""
        try:
            import os
            os.makedirs(os.path.dirname(self.emergency_flag_file), exist_ok=True)
            with open(self.emergency_flag_file, 'w') as f:
                f.write('EMERGENCY_SHUTDOWN')
            self.logger.log_event("ORDER_MANAGER", "INFO", "Emergency shutdown flag saved")
        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR", f"Failed to save emergency flag: {e}")

    def _clear_emergency_flag(self):
        """Очистка флага экстренного закрытия"""
        try:
            import os
            if os.path.exists(self.emergency_flag_file):
                os.remove(self.emergency_flag_file)
                self.logger.log_event("ORDER_MANAGER", "INFO", "Emergency shutdown flag cleared")
        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR", f"Failed to clear emergency flag: {e}")

    async def initialize(self):
        """Инициализация OrderManager"""
        try:
            # Синхронизация с реальными позициями на Binance
            await self.sync_positions_from_exchange()

            # Очистка висящих ордеров
            await self.cleanup_hanging_orders()

            self.logger.log_event("ORDER_MANAGER", "INFO", "OrderManager initialized successfully")
            return True

        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR", f"Failed to initialize OrderManager: {e}")
            return False

    async def sync_positions_from_exchange(self):
        """Синхронизация позиций с Binance"""
        try:
            # Проверяем, не было ли экстренного закрытия
            if self.emergency_shutdown_flag:
                self.logger.log_event("ORDER_MANAGER", "WARNING",
                    "Emergency shutdown detected - skipping position restoration")
                return

            # Получаем реальные позиции с Binance
            positions = await self.exchange.get_positions()

            async with self.position_lock:
                for pos in positions:
                    symbol = pos['symbol']
                    size = float(pos['positionAmt'])

                    if abs(size) > 0:  # Есть позиция
                        if symbol not in self.active_positions:
                            # Новая позиция, добавляем в трекинг
                            self.active_positions[symbol] = {
                                'entry_price': float(pos['entryPrice']),
                                'qty': abs(size),
                                'side': 'BUY' if size > 0 else 'SELL',
                                'unrealized_pnl': float(pos['unRealizedProfit']),
                                'last_update': time.time()
                            }
                            self.logger.log_event("ORDER_MANAGER", "INFO", f"Found existing position: {symbol}")
                    else:
                        # Позиция закрыта, удаляем из трекинга
                        if symbol in self.active_positions:
                            del self.active_positions[symbol]
                            self.logger.log_event("ORDER_MANAGER", "INFO", f"Position closed: {symbol}")

            self.last_sync_time = time.time()

        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR", f"Failed to sync positions: {e}")

    async def place_position_with_tp_sl(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        leverage: int = 5
    ) -> dict[str, Any]:
        """Размещение позиции с автоматическими TP/SL ордерами"""

        try:
                        # 0. Проверяем лимит позиций
            current_positions = len(self.active_positions)
            max_positions = self.config.max_concurrent_positions

            if current_positions >= max_positions:
                # Принудительная синхронизация с биржей
                self.logger.log_event("ORDER_MANAGER", "WARNING",
                    f"Max positions reached ({current_positions}/{max_positions}), syncing with exchange...")
                await self.sync_positions_from_exchange()

                # Проверяем снова после синхронизации
                current_positions = len(self.active_positions)
                if current_positions >= max_positions:
                    self.logger.log_event("ORDER_MANAGER", "WARNING",
                        f"Still max positions reached ({current_positions}/{max_positions}), skipping {symbol}")
                    return {
                        'success': False,
                        'error': f"Max positions reached ({current_positions}/{max_positions})"
                    }

            # 1. Устанавливаем плечо
            await self.exchange.set_leverage(symbol, leverage)

            # 2. Размещаем основной ордер
            main_order = await self.exchange.place_order(
                symbol=symbol,
                side=side,
                order_type="MARKET",
                amount=quantity
            )

            if main_order.get('status') not in ['FILLED', 'closed']:
                return {
                    'success': False,
                    'error': f"Main order failed: {main_order}"
                }

            # 3. Добавляем позицию в трекинг
            async with self.position_lock:
                # Получаем order_id из разных возможных полей
                order_id = None
                if 'id' in main_order:
                    order_id = main_order['id']
                elif 'orderId' in main_order:
                    order_id = main_order['orderId']
                elif 'clientOrderId' in main_order:
                    order_id = main_order['clientOrderId']
                else:
                    order_id = str(time.time())  # Fallback

                self.active_positions[symbol] = {
                    'entry_price': entry_price,
                    'qty': quantity,
                    'side': side,
                    'leverage': leverage,
                    'main_order_id': order_id,
                    'entry_time': time.time(),
                    'unrealized_pnl': 0.0
                }

            # 4. Размещаем TP/SL ордера
            tp_sl_result = await self.place_tp_sl_orders(symbol, side, quantity, entry_price)

            if not tp_sl_result['success']:
                self.logger.log_event("ORDER_MANAGER", "WARNING",
                    f"TP/SL placement failed for {symbol}, but position is open")

            # 5. Логируем успешное открытие
            try:
                self.logger.log_trade(
                    symbol=symbol,
                    side=side,
                    qty=quantity,
                    price=entry_price,
                    reason="Position opened",
                    pnl=0.0,
                    win=True
                )
            except Exception as e:
                self.logger.log_event("ORDER_MANAGER", "WARNING", f"Log trade failed: {e}")

            return {
                'success': True,
                'position_id': main_order.get('id') or main_order.get('orderId'),
                'tp_sl_placed': tp_sl_result['success']
            }

        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR", f"Failed to place position: {e}")
            return {'success': False, 'error': str(e)}

    async def place_tp_sl_orders(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float
    ) -> dict[str, Any]:
        """Размещение Take Profit и Stop Loss ордеров с отменой старых SL"""

        try:
            # Противоположная сторона для выхода
            exit_side = 'SELL' if side == 'BUY' else 'BUY'

            # === КРИТИЧЕСКИЙ FIX: Отменяем все старые SL ордера перед размещением новых ===
            try:
                # Получаем все активные ордера по символу
                open_orders = await self.exchange.fetch_open_orders(symbol)
                sl_orders_to_cancel = []
                
                for order in open_orders:
                    if (order.get('type') == 'STOP_MARKET' and 
                        order.get('side') == exit_side and
                        order.get('reduceOnly')):
                        sl_orders_to_cancel.append(order.get('id') or order.get('orderId'))
                
                # Отменяем все найденные SL ордера
                for order_id in sl_orders_to_cancel:
                    try:
                        await self.exchange.cancel_order(order_id, symbol)
                        self.logger.log_event("ORDER_MANAGER", "INFO",
                            f"Cancelled old SL order {order_id} for {symbol}")
                    except Exception as e:
                        self.logger.log_event("ORDER_MANAGER", "WARNING",
                            f"Failed to cancel old SL order {order_id} for {symbol}: {e}")
                
                if sl_orders_to_cancel:
                    self.logger.log_event("ORDER_MANAGER", "INFO",
                        f"Cancelled {len(sl_orders_to_cancel)} old SL orders for {symbol}")
                    
            except Exception as e:
                self.logger.log_event("ORDER_MANAGER", "WARNING",
                    f"Failed to cancel old SL orders for {symbol}: {e}")

            # 1. Размещаем Stop Loss (первым!)
            sl_price = self.calculate_stop_loss(entry_price, side)

            # Корректировка SL если слишком близко к текущей цене
            try:
                ticker = await self.exchange.get_ticker(symbol)
                current_price = float(ticker['last']) if ticker else entry_price
                sl_gap = abs(current_price - sl_price) / current_price
                min_sl_gap = 0.005  # 0.5%

                if sl_gap < min_sl_gap:
                    old_sl = sl_price
                    if side == 'BUY':
                        adjusted_sl = round(current_price * (1 - min_sl_gap), 6)
                        sl_price = min(adjusted_sl, old_sl * 0.995)
                    else:
                        adjusted_sl = round(current_price * (1 + min_sl_gap), 6)
                        sl_price = max(adjusted_sl, old_sl * 1.005)
                    self.logger.log_event("ORDER_MANAGER", "WARNING",
                        f"SL adjusted for {symbol}: {old_sl:.4f} → {sl_price:.4f}")
            except Exception as e:
                self.logger.log_event("ORDER_MANAGER", "WARNING", f"Failed to adjust SL for {symbol}: {e}")

            # Проверка максимального расстояния SL
            actual_sl_percent = abs(sl_price - entry_price) / entry_price
            max_sl_percent = 0.05
            if actual_sl_percent > max_sl_percent:
                self.logger.log_event("ORDER_MANAGER", "ERROR",
                    f"{symbol}: SL distance {actual_sl_percent:.2%} exceeds max {max_sl_percent:.0%} — aborting")
                return {'success': False, 'error': 'SL distance too far'}

            # Retry логика для SL (как в старом боте)
            sl_retry_limit = 3
            success_sl = False
            sl_order = None

            for retry in range(sl_retry_limit):
                try:
                    # Исправляем вызов create_order - добавляем order_type
                    sl_order = await self.exchange.create_order(
                        symbol=symbol,
                        side=exit_side,
                        order_type='STOP_MARKET',
                        amount=quantity,
                        price=None,
                        params={
                            'stopPrice': sl_price,
                            'reduceOnly': True
                        }
                    )

                    if sl_order and sl_order.get('status') in ['NEW', 'ACCEPTED']:
                        success_sl = True
                        self.logger.log_event("ORDER_MANAGER", "INFO",
                            f"✅ SL placed successfully for {symbol} at {sl_price:.4f}")
                        break
                    elif retry < sl_retry_limit - 1:
                        # Расширяем SL для следующей попытки (как в старом боте)
                        if side == 'BUY':
                            sl_price = sl_price * (0.997 - retry * 0.001)
                        else:
                            sl_price = sl_price * (1.003 + retry * 0.001)
                        sl_price = round(sl_price, 6)
                        self.logger.log_event("ORDER_MANAGER", "WARNING",
                            f"SL retry {retry + 1} for {symbol} at {sl_price:.4f}")

                except Exception as e:
                    if retry < sl_retry_limit - 1:
                        self.logger.log_event("ORDER_MANAGER", "WARNING",
                            f"SL retry {retry + 1} failed for {symbol}: {e}")
                    else:
                        self.logger.log_event("ORDER_MANAGER", "ERROR",
                            f"SL placement failed for {symbol}: {e}")

            if success_sl:
                # Сохраняем информацию о SL ордере
                self.sl_orders[symbol] = {
                    'order_id': sl_order.get('id') or sl_order.get('orderId'),
                    'price': sl_price,
                    'quantity': quantity,
                    'side': exit_side
                }
                self.logger.log_event("ORDER_MANAGER", "INFO",
                    f"SL placed for {symbol} at ${sl_price:.4f}")
            else:
                self.logger.log_event("ORDER_MANAGER", "ERROR",
                    f"Failed to place SL for {symbol} after {sl_retry_limit} retries")
                return {'success': False, 'error': 'SL placement failed'}

            # 2. Размещаем Take Profit уровни (только после успешного SL)
            tp_levels = self.calculate_take_profit_levels(entry_price, side)
            tp_orders = []

            for i, (tp_price, tp_qty) in enumerate(tp_levels):
                try:
                    tp_order = await self.exchange.place_order(
                        symbol=symbol,
                        side=exit_side,
                        order_type='LIMIT',
                        amount=tp_qty,
                        price=tp_price,
                        params={
                            'timeInForce': 'GTC',
                            'reduceOnly': True
                        }
                    )
                    
                    if tp_order:
                        tp_orders.append(tp_order)
                        self.logger.log_event("ORDER_MANAGER", "INFO",
                            f"TP{i+1} placed for {symbol} at ${tp_price:.4f}")
                except Exception as e:
                    self.logger.log_event("ORDER_MANAGER", "WARNING",
                        f"Failed to place TP{i+1} for {symbol}: {e}")

            return {'success': True, 'sl_placed': True, 'tp_count': len(tp_orders)}

        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR", f"Failed to place TP/SL: {e}")
            return {'success': False, 'error': str(e)}

    def calculate_stop_loss(self, entry_price: float, side: str) -> float:
        """Расчет цены Stop Loss"""
        sl_percent = self.config.sl_percent

        if side == 'BUY':
            sl_price = entry_price * (1 - sl_percent)
        else:  # SELL
            sl_price = entry_price * (1 + sl_percent)

        return round(sl_price, 4)

    def calculate_take_profit_levels(self, entry_price: float, side: str) -> list[tuple[float, float]]:
        """Расчет уровней Take Profit"""
        tp_levels = []
        total_qty = 1.0  # Нормализованное количество

        for i, (percent, size_ratio) in enumerate(zip(
            self.config.step_tp_levels,
            self.config.step_tp_sizes, strict=False
        )):
            if side == 'BUY':
                tp_price = entry_price * (1 + percent)
            else:  # SELL
                tp_price = entry_price * (1 - percent)

            tp_qty = total_qty * size_ratio
            tp_levels.append((round(tp_price, 4), round(tp_qty, 6)))

        return tp_levels

    async def close_position_emergency(self, symbol: str) -> dict[str, Any]:
        """Экстренное закрытие позиции"""
        try:
            position = self.active_positions.get(symbol)
            if not position:
                return {'success': False, 'error': 'Position not found'}

            # Отменяем все pending ордера
            await self.cancel_all_orders(symbol)

            # Закрываем позицию по рынку
            exit_side = 'SELL' if position['side'] == 'BUY' else 'BUY'
            close_order = await self.exchange.place_order(
                symbol=symbol,
                side=exit_side,
                order_type='MARKET',
                amount=position['qty']
            )

            if close_order.get('status') == 'FILLED':
                # Calculate PnL
                exit_price = float(close_order.get('price', position['entry_price']))
                entry_price = position['entry_price']
                qty = position['qty']
                side = position['side']

                # Calculate PnL based on side
                if side == 'BUY':
                    pnl = (exit_price - entry_price) * qty
                else:  # SELL
                    pnl = (entry_price - exit_price) * qty

                duration_seconds = time.time() - position.get('entry_time', time.time())

                # Record trade in ProfitTracker if available
                if self.profit_tracker:
                    try:
                        await self.profit_tracker.record_trade(
                            symbol=symbol,
                            side=side,
                            entry_price=entry_price,
                            exit_price=exit_price,
                            quantity=qty,
                            pnl=pnl,
                            duration_seconds=duration_seconds
                        )
                    except Exception as e:
                        self.logger.log_event("ORDER_MANAGER", "WARNING", f"Failed to record trade in ProfitTracker: {e}")

                # Удаляем из трекинга
                async with self.position_lock:
                    if symbol in self.active_positions:
                        del self.active_positions[symbol]

                self.logger.log_event("ORDER_MANAGER", "WARNING",
                    f"Emergency position close: {symbol}, PnL: {pnl:.2f}")

                return {'success': True, 'order_id': close_order.get('id') or close_order.get('orderId'), 'pnl': pnl}
            else:
                return {'success': False, 'error': f"Close order failed: {close_order}"}

        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR", f"Emergency close failed: {e}")
            return {'success': False, 'error': str(e)}

    async def cancel_all_orders(self, symbol: str):
        """Отмена всех ордеров для символа"""
        try:
            # Отменяем TP ордера
            if symbol in self.tp_orders:
                for tp_order in self.tp_orders[symbol]:
                    await self.exchange.cancel_order(symbol, tp_order['order_id'])
                del self.tp_orders[symbol]

            # Отменяем SL ордер
            if symbol in self.sl_orders:
                await self.exchange.cancel_order(symbol, self.sl_orders[symbol]['order_id'])
                del self.sl_orders[symbol]

            self.logger.log_event("ORDER_MANAGER", "INFO", f"Cancelled all orders for {symbol}")

        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR", f"Failed to cancel orders: {e}")

    async def cleanup_hanging_orders(self):
        """Очистка висящих ордеров"""
        try:
            # Получаем все открытые ордера
            open_orders = await self.exchange.get_open_orders()

            current_time = time.time()

            for order in open_orders:
                order_time = order.get('time', 0) / 1000  # Convert to seconds

                # Если ордер висит дольше timeout
                if current_time - order_time > self.order_timeout:
                    await self.exchange.cancel_order(order['symbol'], order['orderId'])
                    self.logger.log_event("ORDER_MANAGER", "WARNING",
                        f"Cancelled hanging order: {order['symbol']} {order['orderId']}")

        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR", f"Cleanup failed: {e}")

    async def monitor_positions(self):
        """Мониторинг позиций и ордеров"""
        while not self.shutdown_requested:
            try:
                # Синхронизация с Binance
                if time.time() - self.last_sync_time > self.sync_interval:
                    await self.sync_positions_from_exchange()

                # Проверка исполнения ордеров
                await self.check_order_executions()

                # Проверка таймаутов
                await self.check_timeouts()

                await asyncio.sleep(10)  # Проверяем каждые 10 секунд

            except Exception as e:
                self.logger.log_event("ORDER_MANAGER", "ERROR", f"Monitor error: {e}")
                await asyncio.sleep(30)

    async def check_order_executions(self):
        """Проверка исполнения ордеров"""
        try:
            # Проверяем TP ордера
            for symbol, tp_orders in list(self.tp_orders.items()):
                for tp_order in tp_orders[:]:  # Копия для итерации
                    order_status = await self.exchange.get_order_status(symbol, tp_order['order_id'])

                    if order_status.get('status') == 'FILLED':
                        # TP исполнен
                        tp_orders.remove(tp_order)
                        self.logger.log_event("ORDER_MANAGER", "INFO",
                            f"TP executed: {symbol} at ${tp_order['price']:.4f}")

                        # Обновляем позицию
                        if symbol in self.active_positions:
                            self.active_positions[symbol]['qty'] -= tp_order['quantity']

                            if self.active_positions[symbol]['qty'] <= 0:
                                # Позиция полностью закрыта
                                del self.active_positions[symbol]
                                if symbol in self.sl_orders:
                                    del self.sl_orders[symbol]

            # Проверяем SL ордера
            for symbol, sl_order in list(self.sl_orders.items()):
                order_status = await self.exchange.get_order_status(symbol, sl_order['order_id'])

                if order_status.get('status') == 'FILLED':
                    # SL исполнен
                    del self.sl_orders[symbol]
                    if symbol in self.active_positions:
                        del self.active_positions[symbol]

                    self.logger.log_event("ORDER_MANAGER", "WARNING",
                        f"SL executed: {symbol} at ${sl_order['price']:.4f}")

        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR", f"Order check failed: {e}")

    async def check_timeouts(self):
        """Проверка таймаутов позиций с расширенной логикой"""
        current_time = time.time()

        for symbol, position in list(self.active_positions.items()):
            position_age = current_time - position.get('entry_time', current_time)
            position_age_minutes = position_age / 60

            # Получаем текущую цену для расчета PnL
            try:
                ticker = await self.exchange.get_ticker(symbol)
                if not ticker:
                    continue

                current_price = float(ticker['lastPrice'])
                entry_price = position['entry_price']
                qty = position['qty']
                side = position['side']

                # Расчет текущего PnL
                if side == 'BUY':
                    pnl = (current_price - entry_price) * qty
                    pnl_percent = ((current_price - entry_price) / entry_price) * 100
                else:  # SELL
                    pnl = (entry_price - current_price) * qty
                    pnl_percent = ((entry_price - current_price) / entry_price) * 100

                # Обновляем unrealized PnL
                position['unrealized_pnl'] = pnl
                position['current_price'] = current_price
                position['pnl_percent'] = pnl_percent

            except Exception as e:
                self.logger.log_event("ORDER_MANAGER", "ERROR", f"Failed to get price for {symbol}: {e}")
                continue

            # 1. Максимальное время удержания (1 час)
            max_hold_minutes = getattr(self.config, 'max_hold_minutes', 30)
            if position_age_minutes > max_hold_minutes:
                self.logger.log_event("ORDER_MANAGER", "WARNING",
                    f"Position timeout: {symbol} (age: {position_age_minutes:.1f}min), closing...")
                await self.close_position_emergency(symbol)
                continue

            # 2. Soft exit при небольшой прибыли после времени
            soft_exit_minutes = getattr(self.config, 'soft_exit_minutes', 15)
            if position_age_minutes > soft_exit_minutes and pnl_percent > 0.2:
                self.logger.log_event("ORDER_MANAGER", "INFO",
                    f"Soft exit: {symbol} (age: {position_age_minutes:.1f}min, PnL: {pnl_percent:.2f}%)")
                await self.close_position_emergency(symbol)
                continue

            # 3. Auto-profit threshold
            auto_profit_threshold = getattr(self.config, 'auto_profit_threshold', 0.7)
            if pnl_percent >= auto_profit_threshold:
                self.logger.log_event("ORDER_MANAGER", "INFO",
                    f"Auto-profit triggered: {symbol} (PnL: {pnl_percent:.2f}%)")
                await self.close_position_emergency(symbol)
                continue

            # 4. Trailing stop (если была хорошая прибыль)
            max_pnl = position.get('max_pnl', 0)
            if pnl > max_pnl:
                position['max_pnl'] = pnl

            if max_pnl > 0:
                drawdown_from_peak = (max_pnl - pnl) / max_pnl if max_pnl > 0 else 0
                if drawdown_from_peak > 0.3:  # 30% от пика
                    self.logger.log_event("ORDER_MANAGER", "INFO",
                        f"Trailing stop: {symbol} (drawdown: {drawdown_from_peak:.1%})")
                    await self.close_position_emergency(symbol)
                    continue

            # 5. Экстренный выход при большой просадке
            position_value = entry_price * qty
            emergency_loss_threshold = getattr(self.config, 'emergency_stop_threshold', -2.0)
            if pnl_percent < emergency_loss_threshold:
                self.logger.log_event("ORDER_MANAGER", "WARNING",
                    f"Emergency exit: {symbol} (PnL: {pnl_percent:.2f}%)")
                await self.close_position_emergency(symbol)
                continue

            # 6. Закрытие слабых позиций (долго висят без движения)
            weak_position_minutes = getattr(self.config, 'weak_position_minutes', 45)
            if position_age_minutes > weak_position_minutes and abs(pnl_percent) < 0.5:
                self.logger.log_event("ORDER_MANAGER", "INFO",
                    f"Weak position closed: {symbol} (age: {position_age_minutes:.1f}min, PnL: {pnl_percent:.2f}%)")
                await self.close_position_emergency(symbol)
                continue

            # 7. Закрытие рискованных позиций (большая просадка)
            risky_loss_threshold = getattr(self.config, 'risky_loss_threshold', -1.5)
            if pnl_percent <= risky_loss_threshold:
                self.logger.log_event("ORDER_MANAGER", "WARNING",
                    f"Risky position closed: {symbol} (PnL: {pnl_percent:.2f}%)")
                await self.close_position_emergency(symbol)
                continue

    def get_active_positions(self) -> list[dict]:
        """Получение активных позиций"""
        return [
            {
                'symbol': symbol,
                'side': pos['side'],
                'qty': pos['qty'],
                'entry_price': pos['entry_price'],
                'unrealized_pnl': pos.get('unrealized_pnl', 0.0)
            }
            for symbol, pos in self.active_positions.items()
        ]

    def get_position_count(self) -> int:
        """Получает количество активных позиций"""
        return len(self.active_positions)

    async def has_position(self, symbol: str) -> bool:
        """Проверяет, есть ли активная позиция по символу"""
        try:
            positions = await self.exchange.get_positions()
            for position in positions:
                if position.get('symbol') == symbol and abs(float(position.get('positionAmt', 0))) > 0:
                    return True
            return False
        except Exception as e:
            self.logger.log_event("ORDER_MANAGER", "ERROR", f"Ошибка проверки позиции {symbol}: {e}")
            return False

    def reset_emergency_flag(self):
        """Сброс флага экстренного закрытия (для восстановления позиций)"""
        self.emergency_shutdown_flag = False
        self.shutdown_timestamp = None
        self._clear_emergency_flag()
        self.logger.log_event("ORDER_MANAGER", "INFO", "Emergency shutdown flag reset - position restoration enabled")

    def is_emergency_shutdown(self) -> bool:
        """Проверка, был ли экстренный shutdown"""
        return self.emergency_shutdown_flag

    async def shutdown(self, emergency: bool = False):
        """Завершение работы OrderManager"""
        self.shutdown_requested = True
        self.shutdown_timestamp = time.time()

        if emergency:
            self.emergency_mode = True
            self.emergency_shutdown_flag = True  # Устанавливаем флаг экстренного закрытия
            self._save_emergency_flag()  # Сохраняем флаг
            self.logger.log_event("ORDER_MANAGER", "CRITICAL", "Emergency shutdown initiated")

            # Экстренное закрытие всех позиций
            for symbol in list(self.active_positions.keys()):
                await self.close_position_emergency(symbol)
        else:
            self.logger.log_event("ORDER_MANAGER", "INFO", "Graceful shutdown initiated")

            # Graceful закрытие - ждем исполнения ордеров
            timeout = 300  # 5 минут
            start_time = time.time()

            while self.active_positions and (time.time() - start_time) < timeout:
                await asyncio.sleep(10)

            # Если остались позиции, закрываем экстренно
            if self.active_positions:
                self.logger.log_event("ORDER_MANAGER", "WARNING",
                    "Timeout reached, emergency closing remaining positions")
                self.emergency_shutdown_flag = True  # Устанавливаем флаг при экстренном закрытии
                self._save_emergency_flag()  # Сохраняем флаг
                for symbol in list(self.active_positions.keys()):
                    await self.close_position_emergency(symbol)

        self.logger.log_event("ORDER_MANAGER", "INFO", "OrderManager shutdown completed")
