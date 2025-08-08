#!/usr/bin/env python3
"""
Enhanced WebSocket Manager для BinanceBot_V2
Реальное время, высокая производительность, автоматическое переподключение
"""

# Import Windows compatibility error handling
import core.windows_compatibility

import asyncio
import json
import time
from collections import defaultdict, deque
from collections.abc import Callable
from typing import Any

import websockets

from core.unified_logger import UnifiedLogger


class WebSocketManager:
    """🚀 Улучшенный WebSocket Manager для максимальной производительности"""

    def __init__(self, exchange_client, telegram=None, logger: UnifiedLogger | None = None):
        self.exchange = exchange_client
        self.telegram = telegram
        self.logger = logger

        # WebSocket connections
        self.connections = {}
        self.user_stream_ws = None
        self.listen_key = None

        # Performance tracking - улучшенные метрики
        self.message_count = 0
        self.latency_tracker = deque(maxlen=1000)
        self.reconnect_count = 0
        self.last_message_time = time.time()
        self.start_time = time.time()

        # Data handlers
        self.market_data_handlers = defaultdict(list)
        self.order_update_handlers = []
        self.position_update_handlers = []

        # Connection management - улучшенные параметры
        self.is_running = False
        self.reconnect_delay = 5
        self.max_reconnect_attempts = 10
        self.heartbeat_interval = 30

        # Real-time data storage
        self.latest_prices = {}
        self.order_book_cache = {}
        self.trade_cache = deque(maxlen=1000)

        # Performance metrics - улучшенные метрики
        self.performance_metrics = {
            'messages_per_second': 0,
            'average_latency': 0,
            'connection_uptime': 0,
            'reconnect_frequency': 0,
            'total_messages': 0,
            'uptime_seconds': 0
        }

        # Connection health monitoring
        self.connection_health = {}
        self.last_health_check = time.time()

        # Кэш для валидных символов
        self._valid_symbols_cache = set()
        self._symbols_cache_time = 0

    async def start(self):
        """Запуск WebSocket Manager"""
        try:
            self.is_running = True
            self.start_time = time.time()
            self.logger.log_event("WEBSOCKET", "INFO", "🚀 Запуск Enhanced WebSocket Manager")

            # Создаем listen key для user data stream
            await self._create_listen_key()

            # Запускаем задачи
            tasks = [
                asyncio.create_task(self._maintain_user_stream()),
                asyncio.create_task(self._performance_monitor()),
                asyncio.create_task(self._heartbeat_monitor()),
                asyncio.create_task(self._connection_health_monitor())
            ]

            await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            self.logger.log_event("WEBSOCKET", "ERROR", f"Ошибка запуска WebSocket: {e}")
            raise

    async def subscribe_market_data(self, symbols: list[str]):
        """Подписка на рыночные данные с оптимизированными потоками"""
        try:
            # Валидация символов перед подключением
            valid_symbols = await self._validate_websocket_symbols(symbols)
            if not valid_symbols:
                self.logger.log_event("WEBSOCKET", "WARNING", "No valid symbols for WebSocket subscription")
                return

            # Подготавливаем символы для WebSocket (lowercase, без / и :USDC)
            streams = [f"{s.replace('/', '').replace(':USDC', '').lower()}@ticker" for s in valid_symbols]

            # Ограничиваем количество символов чтобы избежать timeout
            if len(streams) > 5:
                streams = streams[:5]
                self.logger.log_event("WEBSOCKET", "INFO", f"Limited to 5 symbols to avoid timeout")

            # Используем combined stream для всех символов
            stream_query = "/".join(streams)
            url = f"wss://fstream.binance.com/stream?streams={stream_query}"

            self.logger.log_event("WEBSOCKET", "INFO", f"🔌 Connecting to combined stream: {url}")

                        # Добавляем retry логику для WebSocket
            max_retries = 3
            retry_delay = 5
            
            for attempt in range(max_retries):
                try:
                    async with websockets.connect(
                        url,
                        ping_interval=30,     # ping каждые 30 секунд
                        ping_timeout=10,      # pong в течение 10 секунд
                        open_timeout=5,       # уменьшаем timeout еще больше
                        max_size=2**20
                    ) as ws:
                        self.connections['combined'] = {
                            'websocket': ws,
                            'streams': streams,
                            'last_message': time.time(),
                            'message_count': 0,
                            'is_healthy': True
                        }

                        self.logger.log_event("WEBSOCKET", "INFO", f"✅ WebSocket connected successfully")

                        async for raw_message in ws:
                            try:
                                data = json.loads(raw_message)
                                # В combined формате: {'stream': ..., 'data': {...}}
                                payload = data.get("data", data)
                                await self._process_market_message("combined", payload)
                            except Exception as e:
                                self.logger.log_event("WEBSOCKET", "ERROR", f"Failed to process message: {e}")
                        
                        # Если дошли сюда, значит соединение закрылось
                        break
                        
                except Exception as e:
                    self.logger.log_event("WEBSOCKET", "ERROR", f"WebSocket connection attempt {attempt + 1} failed: {e}")
                    if attempt < max_retries - 1:
                        self.logger.log_event("WEBSOCKET", "INFO", f"Retrying in {retry_delay} seconds...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        self.logger.log_event("WEBSOCKET", "WARNING", "All WebSocket connection attempts failed")
                        self.logger.log_event("WEBSOCKET", "INFO", "WebSocket disabled - using REST API only")
                        # Продолжаем работу без WebSocket
                        await asyncio.sleep(30)

        except Exception as e:
            self.logger.log_event("WEBSOCKET", "ERROR", f"Ошибка подписки на рыночные данные: {e}")
            self.logger.log_event("WEBSOCKET", "INFO", "WebSocket disabled for stability - using REST API only")

    async def _connect_market_streams(self, symbol: str, streams: list[str]):
        """Подключение к рыночным потокам с оптимизацией"""
        try:
            # Определяем правильный URL для WebSocket в зависимости от режима
            if self.exchange.config.is_testnet_mode():
                base_url = "wss://stream.binancefuture.com"  # Testnet WebSocket
                self.logger.log_event("WEBSOCKET", "INFO", "🧪 Using testnet WebSocket")
            else:
                base_url = "wss://fstream.binance.com"  # Production Futures WebSocket
                self.logger.log_event("WEBSOCKET", "INFO", "🚀 Using production WebSocket")

            # Создаем WebSocket соединение с улучшенными параметрами
            # Используем правильный формат для futures
            symbol_lower = symbol.replace("/", "").lower()
            stream_url = f"{base_url}/ws/{symbol_lower}@ticker"

            websocket = await websockets.connect(
                stream_url,
                ping_interval=20,
                ping_timeout=30,
                close_timeout=30,
                max_size=2**20,  # 1MB max message size
                compression=None,   # Отключаем сжатие для скорости
                open_timeout=30    # Увеличиваем timeout подключения
            )

            self.connections[symbol] = {
                'websocket': websocket,
                'streams': streams,
                'last_message': time.time(),
                'message_count': 0,
                'connection_time': time.time(),
                'is_healthy': True
            }

            # Запускаем обработчик сообщений
            asyncio.create_task(self._handle_market_messages(symbol, websocket))

            self.logger.log_event("WEBSOCKET", "INFO", f"🔌 Подключение к {symbol}: {len(streams)} потоков")

        except Exception as e:
            self.logger.log_event("WEBSOCKET", "ERROR", f"Ошибка подключения к {symbol}: {e}")
            # Fallback - не блокируем работу бота из-за WebSocket
            self.logger.log_event("WEBSOCKET", "INFO", f"Пропускаем WebSocket для {symbol}, продолжаем работу")

    async def _handle_market_messages(self, symbol: str, websocket):
        """Обработка рыночных сообщений с оптимизацией производительности"""
        try:
            async for message in websocket:
                start_time = time.time()

                try:
                    data = json.loads(message)

                    # Обновляем метрики производительности
                    self.message_count += 1
                    self.performance_metrics['total_messages'] += 1

                    # Измеряем латентность обработки
                    processing_time = time.time() - start_time
                    self.latency_tracker.append(processing_time)
                    self.last_message_time = time.time()

                    # Обрабатываем различные типы сообщений
                    await self._process_market_message(symbol, data)

                    # Обновляем статистику соединения
                    if symbol in self.connections:
                        self.connections[symbol]['message_count'] += 1
                        self.connections[symbol]['last_message'] = time.time()
                        self.connections[symbol]['is_healthy'] = True

                except json.JSONDecodeError as e:
                    self.logger.log_event("WEBSOCKET", "WARNING", f"Invalid JSON from {symbol}: {e}")
                except Exception as e:
                    self.logger.log_event("WEBSOCKET", "ERROR", f"Ошибка обработки сообщения {symbol}: {e}")

        except websockets.exceptions.ConnectionClosed:
            self.logger.log_event("WEBSOCKET", "WARNING", f"Соединение закрыто для {symbol}")
            if symbol in self.connections:
                self.connections[symbol]['is_healthy'] = False
            await self._reconnect_stream(symbol)
        except Exception as e:
            self.logger.log_event("WEBSOCKET", "ERROR", f"Ошибка WebSocket для {symbol}: {e}")
            if symbol in self.connections:
                self.connections[symbol]['is_healthy'] = False
            await self._reconnect_stream(symbol)

    async def _process_market_message(self, symbol: str, data: dict[str, Any]):
        """Обработка рыночных сообщений с кешированием"""
        try:
            # Обновляем кеш цен
            if 'c' in data:  # ticker data
                self.latest_prices[symbol] = {
                    'price': float(data['c']),
                    'volume': float(data['v']),
                    'timestamp': time.time()
                }

            # Обновляем order book
            if 'b' in data and 'a' in data:  # depth data
                self.order_book_cache[symbol] = {
                    'bids': data['b'][:10],  # Top 10 bids
                    'asks': data['a'][:10],  # Top 10 asks
                    'timestamp': time.time()
                }

            # Кешируем сделки
            if 'p' in data and 'q' in data:  # trade data
                trade_info = {
                    'symbol': symbol,
                    'price': float(data['p']),
                    'quantity': float(data['q']),
                    'timestamp': time.time()
                }
                self.trade_cache.append(trade_info)

            # Вызываем пользовательские обработчики
            for handler in self.market_data_handlers[symbol]:
                try:
                    await handler(symbol, data)
                except Exception as e:
                    self.logger.log_event("WEBSOCKET", "ERROR", f"Handler error for {symbol}: {e}")

        except Exception as e:
            self.logger.log_event("WEBSOCKET", "ERROR", f"Ошибка обработки данных {symbol}: {e}")

    async def _create_listen_key(self):
        """Создание listen key для user data stream"""
        try:
            # Временно отключаем WebSocket для Windows
            self.logger.log_event("WEBSOCKET", "INFO", "WebSocket отключен для Windows")
            return

        except Exception as e:
            # Handle Windows compatibility errors
            if core.windows_compatibility.is_windows_compatibility_error(str(e)):
                self.logger.log_event("WEBSOCKET", "INFO", "WebSocket отключен для Windows (compatibility)")
            else:
                self.logger.log_event("WEBSOCKET", "ERROR", f"Ошибка создания listen key: {e}")

    async def _maintain_user_stream(self):
        """Поддержание user data stream"""
        last_log_time = 0
        while self.is_running:
            try:
                if not self.listen_key:
                    current_time = time.time()
                    # Логируем только раз в 5 минут
                    if current_time - last_log_time > 300:
                        self.logger.log_event("WEBSOCKET", "INFO", "WebSocket отключен для Windows")
                        last_log_time = current_time
                    await asyncio.sleep(60)  # Ждем минуту перед следующей попыткой
                    continue

                # Определяем правильный URL для user data stream
                # Для USDC-M Futures используем правильные endpoints
                if self.exchange.config.is_testnet_mode():
                    user_stream_url = f"wss://stream.binancefuture.com/ws/{self.listen_key}"
                else:
                    user_stream_url = f"wss://fstream.binance.com/ws/{self.listen_key}"

                async with websockets.connect(user_stream_url) as websocket:
                    self.user_stream_ws = websocket
                    self.logger.log_event("WEBSOCKET", "INFO", "🔌 User data stream подключен")

                    async for message in websocket:
                        try:
                            data = json.loads(message)
                            await self._handle_user_data(data)
                        except json.JSONDecodeError:
                            continue
                        except Exception as e:
                            self.logger.log_event("WEBSOCKET", "ERROR", f"User data error: {e}")

            except Exception as e:
                self.logger.log_event("WEBSOCKET", "WARNING", f"User stream error: {e}")
                await asyncio.sleep(self.reconnect_delay)
            except Exception as e:
                self.logger.log_event("WEBSOCKET", "ERROR", f"User stream error: {e}")
                await asyncio.sleep(self.reconnect_delay)

    async def _handle_user_data(self, data: dict[str, Any]):
        """Обработка user data сообщений"""
        try:
            event_type = data.get('e')

            if event_type == 'executionReport':
                await self._handle_order_update(data)
            elif event_type == 'ACCOUNT_UPDATE':
                await self._handle_position_update(data)
            elif event_type == 'outboundAccountPosition':
                await self._handle_balance_update(data)

        except Exception as e:
            self.logger.log_event("WEBSOCKET", "ERROR", f"Ошибка обработки user data: {e}")

    async def _handle_order_update(self, data: dict[str, Any]):
        """Обработка обновлений ордеров в реальном времени"""
        try:
            order_status = data.get('X')
            symbol = data.get('s')
            side = data.get('S')
            price = float(data.get('p', 0))
            quantity = float(data.get('q', 0))

            if order_status == 'FILLED':
                # Мгновенное уведомление о исполнении
                if self.telegram:
                    await self.telegram.send_trade_alert({
                        "symbol": symbol,
                        "side": side,
                        "price": price,
                        "quantity": quantity,
                        "status": "FILLED"
                    })

                self.logger.log_event("WEBSOCKET", "INFO",
                    f"🎯 Ордер исполнен: {symbol} {side} {quantity} @ {price}")

            # Вызываем пользовательские обработчики
            for handler in self.order_update_handlers:
                try:
                    await handler(data)
                except Exception as e:
                    self.logger.log_event("WEBSOCKET", "ERROR", f"Order handler error: {e}")

        except Exception as e:
            self.logger.log_event("WEBSOCKET", "ERROR", f"Ошибка обработки order update: {e}")

    async def _handle_position_update(self, data: dict[str, Any]):
        """Обработка обновлений позиций"""
        try:
            positions = data.get('a', {}).get('P', [])

            for position in positions:
                symbol = position.get('s')
                size = float(position.get('pa', 0))

                if abs(size) > 0:
                    self.logger.log_event("WEBSOCKET", "INFO",
                        f"📊 Позиция обновлена: {symbol} = {size}")

            # Вызываем пользовательские обработчики
            for handler in self.position_update_handlers:
                try:
                    await handler(data)
                except Exception as e:
                    self.logger.log_event("WEBSOCKET", "ERROR", f"Position handler error: {e}")

        except Exception as e:
            self.logger.log_event("WEBSOCKET", "ERROR", f"Ошибка обработки position update: {e}")

    async def _handle_balance_update(self, data: dict[str, Any]):
        """Обработка обновлений баланса"""
        try:
            balances = data.get('B', [])

            for balance in balances:
                asset = balance.get('a')
                wallet_balance = float(balance.get('wb', 0))

                if asset == 'USDC':
                    self.logger.log_event("WEBSOCKET", "INFO",
                        f"💰 Баланс обновлен: {wallet_balance:.2f} USDC")

        except Exception as e:
            self.logger.log_event("WEBSOCKET", "ERROR", f"Ошибка обработки balance update: {e}")

    async def _reconnect_stream(self, symbol: str):
        """Переподключение к потоку с экспоненциальной задержкой"""
        try:
            self.reconnect_count += 1
            delay = min(self.reconnect_delay * (2 ** (self.reconnect_count - 1)), 60)

            self.logger.log_event("WEBSOCKET", "WARNING",
                f"🔄 Переподключение к {symbol} через {delay}с (попытка {self.reconnect_count})")

            await asyncio.sleep(delay)

            if symbol in self.connections:
                streams = self.connections[symbol]['streams']
                await self._connect_market_streams(symbol, streams)

        except Exception as e:
            self.logger.log_event("WEBSOCKET", "ERROR", f"Ошибка переподключения к {symbol}: {e}")

    async def _performance_monitor(self):
        """Мониторинг производительности WebSocket"""
        while self.is_running:
            try:
                current_time = time.time()

                # Рассчитываем метрики производительности
                if len(self.latency_tracker) > 0:
                    self.performance_metrics['average_latency'] = sum(self.latency_tracker) / len(self.latency_tracker)

                # Сообщений в секунду - улучшенный расчет
                uptime = current_time - self.start_time
                if uptime > 0:
                    self.performance_metrics['messages_per_second'] = self.message_count / uptime
                    self.performance_metrics['uptime_seconds'] = uptime

                # Время работы соединения
                self.performance_metrics['connection_uptime'] = current_time - self.last_message_time

                # Частота переподключений
                self.performance_metrics['reconnect_frequency'] = self.reconnect_count

                # Логируем метрики каждые 60 секунд
                if int(current_time) % 60 == 0:
                    self.logger.log_event("WEBSOCKET", "INFO",
                        f"📊 WebSocket метрики: "
                        f"Latency: {self.performance_metrics['average_latency']:.3f}ms, "
                        f"Msg/s: {self.performance_metrics['messages_per_second']:.1f}, "
                        f"Total: {self.performance_metrics['total_messages']}, "
                        f"Reconnects: {self.performance_metrics['reconnect_frequency']}")

                await asyncio.sleep(10)

            except Exception as e:
                self.logger.log_event("WEBSOCKET", "ERROR", f"Ошибка мониторинга производительности: {e}")
                await asyncio.sleep(10)

    async def _heartbeat_monitor(self):
        """Мониторинг heartbeat для поддержания соединений"""
        while self.is_running:
            try:
                current_time = time.time()

                # Проверяем все соединения
                for symbol, connection in list(self.connections.items()):
                    last_message = connection.get('last_message', 0)

                    # Если нет сообщений более 60 секунд, переподключаемся
                    if current_time - last_message > 60:
                        self.logger.log_event("WEBSOCKET", "WARNING",
                            f"💓 Heartbeat timeout для {symbol}, переподключение...")
                        await self._reconnect_stream(symbol)

                # Обновляем listen key каждые 30 минут
                if self.listen_key and int(current_time) % 1800 == 0:
                    await self._create_listen_key()

                await asyncio.sleep(30)

            except Exception as e:
                self.logger.log_event("WEBSOCKET", "ERROR", f"Ошибка heartbeat мониторинга: {e}")
                await asyncio.sleep(30)

    async def _connection_health_monitor(self):
        """Мониторинг здоровья соединений"""
        while self.is_running:
            try:
                current_time = time.time()

                for symbol, connection in list(self.connections.items()):
                    # Проверяем здоровье соединения
                    connection_time = connection.get('connection_time', 0)
                    message_count = connection.get('message_count', 0)
                    is_healthy = connection.get('is_healthy', True)

                    # Обновляем статистику здоровья
                    self.connection_health[symbol] = {
                        'uptime': current_time - connection_time,
                        'message_count': message_count,
                        'is_healthy': is_healthy,
                        'last_check': current_time
                    }

                await asyncio.sleep(15)

            except Exception as e:
                self.logger.log_event("WEBSOCKET", "ERROR", f"Ошибка мониторинга здоровья: {e}")
                await asyncio.sleep(15)

    def add_market_data_handler(self, symbol: str, handler: Callable):
        """Добавление обработчика рыночных данных"""
        self.market_data_handlers[symbol].append(handler)

    def add_order_update_handler(self, handler: Callable):
        """Добавление обработчика обновлений ордеров"""
        self.order_update_handlers.append(handler)

    def add_position_update_handler(self, handler: Callable):
        """Добавление обработчика обновлений позиций"""
        self.position_update_handlers.append(handler)

    def get_latest_price(self, symbol: str) -> float | None:
        """Получение последней цены из кеша"""
        if symbol in self.latest_prices:
            return self.latest_prices[symbol]['price']
        return None

    def get_order_book(self, symbol: str) -> dict[str, Any] | None:
        """Получение order book из кеша"""
        return self.order_book_cache.get(symbol)

    def get_performance_metrics(self) -> dict[str, Any]:
        """Получение метрик производительности"""
        return self.performance_metrics.copy()

    def get_connection_health(self) -> dict[str, Any]:
        """Получение здоровья соединений"""
        return self.connection_health.copy()

    async def _validate_websocket_symbols(self, symbols: list[str]) -> list[str]:
        """Валидация символов перед подключением к WebSocket"""
        try:
            # Проверяем кэш
            current_time = time.time()
            if current_time - self._symbols_cache_time < 3600:  # Кэш на 1 час
                # Используем кэш
                valid_symbols = []
                for symbol in symbols:
                    # Проверяем различные форматы символов
                    symbol_clean = symbol.replace('/', '').replace(':USDC', '').upper()
                    if symbol_clean in self._valid_symbols_cache:
                        valid_symbols.append(symbol)
                    else:
                        self.logger.log_event("WEBSOCKET", "DEBUG", f"Invalid symbol filtered: {symbol}")
                return valid_symbols

            # Обновляем кэш валидных символов
            try:
                # Получаем информацию о futures символах через CCXT
                markets = self.exchange.exchange.load_markets()
                self._valid_symbols_cache = {
                    market['id'].upper() 
                    for market in markets.values() 
                    if market.get('settle') == 'USDC' and market.get('active', True)
                }
                self._symbols_cache_time = current_time
                self.logger.log_event("WEBSOCKET", "INFO", f"Updated valid symbols cache: {len(self._valid_symbols_cache)} symbols")
            except Exception as e:
                self.logger.log_event("WEBSOCKET", "ERROR", f"Failed to fetch exchange info: {e}")
                # Используем базовые символы как fallback
                return ["BTC/USDC:USDC", "ETH/USDC:USDC", "BNB/USDC:USDC"]

            # Фильтруем символы
            valid_symbols = []
            invalid_symbols = []

            for symbol in symbols:
                symbol_clean = symbol.replace('/', '').replace(':USDC', '').upper()

                # Специальная обработка для символов с числами
                if symbol_clean.startswith('1000'):
                    # 1000SHIB -> SHIBUSDC и т.д.
                    symbol_check = symbol_clean[4:] + 'USDC'
                elif symbol_clean == 'IP' or symbol_clean == 'IPUSDC':
                    # IP не существует на Binance Futures
                    invalid_symbols.append(symbol)
                    continue
                elif symbol_clean == 'TRUMP' or symbol_clean == 'TRUMPUSDC':
                    # TRUMP может не существовать
                    invalid_symbols.append(symbol)
                    continue
                elif symbol_clean == 'KAITO' or symbol_clean == 'KAITOUSDC':
                    # KAITO может не существовать
                    invalid_symbols.append(symbol)
                    continue
                else:
                    symbol_check = symbol_clean + 'USDC'

                if symbol_check in self._valid_symbols_cache:
                    valid_symbols.append(symbol)
                else:
                    invalid_symbols.append(symbol)

            if invalid_symbols:
                self.logger.log_event("WEBSOCKET", "WARNING", f"Invalid symbols removed: {invalid_symbols}")

            if not valid_symbols:
                # Fallback к базовым символам
                self.logger.log_event("WEBSOCKET", "WARNING", "No valid symbols found, using defaults")
                return ["BTC/USDC:USDC", "ETH/USDC:USDC", "BNB/USDC:USDC"]

            return valid_symbols

        except Exception as e:
            self.logger.log_event("WEBSOCKET", "ERROR", f"Symbol validation error: {e}")
            # Возвращаем минимальный набор символов
            return ["BTC/USDC:USDC", "ETH/USDC:USDC"]

    async def stop(self):
        """Остановка WebSocket Manager"""
        try:
            self.is_running = False

            # Закрываем все соединения
            for symbol, connection in self.connections.items():
                if 'websocket' in connection:
                    try:
                        await connection['websocket'].close()
                    except Exception as e:
                        self.logger.log_event("WEBSOCKET", "WARNING", f"Ошибка закрытия соединения {symbol}: {e}")

            if self.user_stream_ws:
                try:
                    await self.user_stream_ws.close()
                except Exception as e:
                    self.logger.log_event("WEBSOCKET", "WARNING", f"Ошибка закрытия user stream: {e}")

            self.logger.log_event("WEBSOCKET", "INFO", "🛑 WebSocket Manager остановлен")

        except Exception as e:
            self.logger.log_event("WEBSOCKET", "ERROR", f"Ошибка остановки WebSocket: {e}")
