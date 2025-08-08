📘 Концепт и Roadmap: BinanceBot v2 "OptiFlow HFT"
Версия: 2.2 (Полная версия без ML)
Дата: Август 2025
Статус: Готов к реализации

🎯 ЦЕЛЬ: $2/час прибыли с депозита $250-350 USDC

📑 Содержание

Введение и философия
Архитектура системы

2.1 Структура проекта
2.2 Основные компоненты
2.3 Потоки данных

Стратегия и источники альфы

3.1 Микроструктурные сигналы
3.2 Гибридный подход
3.3 Дополнительные стратегии

Управление ордерами и исполнение

4.1 Типы ордеров и комиссии
4.2 WebSocket мониторинг

Технические улучшения

5.1 Производительность
5.2 Надежность

Инфраструктура и развертывание
Roadmap внедрения

7.1 Фаза 1: Фундамент (1 неделя)
7.2 Фаза 2: Оптимизация (1-2 недели)
7.3 Фаза 3: Стратегии (1 неделя)
7.4 Фаза 4: Расширенные возможности (2-4 недели)

Ожидаемые результаты
Критические детали реализации

1. Введение и философия
   "OptiFlow HFT" — это полностью переработанная, высокопроизводительная торговая система, предназначенная для работы на криптовалютных фьючерсных рынках с минимальной задержкой. Система оптимизирована для достижения целевой прибыли **$2/час** с минимальным депозитом **$250-350 USDC**. В отличие от традиционных ботов, работающих на свечных данных, OptiFlow HFT спроектирован для использования микроструктуры рынка и неэффективностей, возникающих в миллисекундном диапазоне.
   Ключевые принципы:

Скорость превыше всего: Каждый компонент оптимизирован для минимальной задержки
Надежность и отказоустойчивость: Работа 24/7/365 с механизмами самовосстановления
Модульность и масштабируемость: Легко добавлять новые стратегии, рынки и источники данных
Точность симуляции: Бэктестинг максимально отражает реальные условия, включая задержки и позицию в очереди

Что НЕ включаем:

❌ Machine Learning (отложено до накопления 100k+ сделок)
❌ Полное переписывание с нуля
❌ Непроверенные экспериментальные подходы

2.  Архитектура системы
    2.1 Структура проекта
    BinanceBot_v2/
    ├── core/
    │ ├── config.py # Единая типизированная конфигурация
    │ ├── exchange_client.py # API + WebSocket + Rate Limiter
    │ ├── async_engine.py # Асинхронный Producer-Consumer движок
    │ ├── trading_engine.py # Исполнение сделок
    │ ├── risk_manager.py # Все риск-проверки
    │ ├── unified_logger.py # SQLite вместо CSV
    │ ├── rate_limiter.py # Централизованный Rate Limiter
    │ └── monitoring.py # Performance monitoring
    │
    ├── strategies/
    │ ├── base_strategy.py # Базовый класс
    │ ├── scalping_v1.py # Ваша текущая стратегия
    │ ├── microstructure.py # HFT сигналы (OBI и др.)
    │ ├── grid_strategy.py # Grid trading для бокового рынка
    │ └── market_maker.py # Market making стратегия
    │
    ├── utils/
    │ ├── helpers.py # Общие функции
    │ ├── validators.py # Валидация ордеров
    │ └── performance.py # Оптимизации (Numba JIT)
    │
    ├── telegram/
    │ └── bot_commands.py # Все Telegram команды
    │
    ├── data/
    │ ├── runtime_config.json # Динамические настройки
    │ ├── trading_log.db # Единая БД
    │ └── backtest/ # Данные для тестирования
    │
    └── main.py # Точка входа
    2.2 Основные компоненты
    🔧 Exchange Client (Расширенный)
    pythonclass ExchangeClient:
    """Единая точка взаимодействия с Binance"""

        def __init__(self, config):
            self.rate_limiter = CentralizedRateLimiter()
            self.websocket_manager = WebSocketManager()
            self.user_stream = None

        async def create_order(self, symbol, side, type, quantity, price=None):
            """Создание ордера с приоритетом на WebSocket"""
            # Валидация количества
            quantity = self.validate_and_adjust_quantity(symbol, quantity, price)

            # Проверка Rate Limits
            await self.rate_limiter.wait_if_needed('order', weight=1)

            # WebSocket для ордеров (быстрее)
            if self.websocket_manager.is_connected:
                return await self._ws_create_order(...)
            else:
                return await self._rest_create_order(...)

        async def subscribe_user_stream(self):
            """Подписка на обновления аккаунта в реальном времени"""
            self.user_stream = await self.websocket_manager.create_user_stream()
            # Мгновенные обновления позиций, ордеров, баланса

        def update_from_headers(self, headers):
            """Синхронизация с реальными лимитами сервера"""
            if 'X-MBX-USED-WEIGHT' in headers:
                self.rate_limiter.sync_server_weight(headers['X-MBX-USED-WEIGHT'])

    ⚡ Async Engine (Producer-Consumer)
    pythonclass AsyncTradingEngine:
    """Событийно-ориентированная архитектура"""

        def __init__(self, symbols):
            self.market_data_queue = asyncio.Queue()
            self.signal_queue = asyncio.Queue()
            self.order_queue = asyncio.Queue()

        async def run(self):
            """Запуск всех продюсеров и консьюмеров"""
            producers = [
                self._aggTrade_producer(symbol),
                self._orderbook_producer(symbol),
                self._user_data_producer()
            ]

            consumers = [
                self._signal_consumer(),
                self._execution_consumer(),
                self._monitoring_consumer()
            ]

            await asyncio.gather(*producers, *consumers)

    🛡️ Risk Manager (Полный)
    pythonclass RiskManager:
    """Централизованное управление рисками"""

        def __init__(self, config):
            self.quantitative_monitor = QuantitativeRulesMonitor()

        async def check_entry_allowed(self, symbol, side, amount):
            """Комплексная проверка перед входом"""
            checks = [
                self._check_position_limits(),
                self._check_daily_drawdown(),
                self._check_ufr_gcr(),  # Binance quantitative rules
                self._check_symbol_exposure(),
                self._check_correlation_risk()
            ]

            return all(await asyncio.gather(*checks))

        def calculate_position_size(self, balance, price, volatility):
            """Адаптивный размер позиции"""
            base_risk = self.config.base_risk_pct

            # Адаптация под баланс
            if balance < 200:
                risk_pct = 0.08
            elif balance < 500:
                risk_pct = 0.06
            else:
                risk_pct = 0.03

            # Корректировка под волатильность
            volatility_multiplier = 1 / (1 + volatility * 10)

            return (balance * risk_pct * volatility_multiplier) / price

    2.3 Потоки данных
    python# WebSocket потоки для каждого символа
    streams = [
    f"{symbol}@aggTrade", # Поток сделок
    f"{symbol}@depth20@100ms", # Стакан ордеров (100мс обновление)
    f"{symbol}@bookTicker", # Лучшие bid/ask
    f"{symbol}@forceOrder" # Ликвидации (для анализа)
    ]

# User Data Stream (критически важно для HFT)

user_streams = [
"executionReport", # Обновления ордеров
"balanceUpdate", # Изменения баланса
"ACCOUNT_UPDATE" # Обновления позиций
]

3.  Стратегия и источники альфы
    3.1 Микроструктурные сигналы
    Order Book Imbalance (OBI) - Расширенный
    pythonclass OrderBookAnalyzer:
    """Продвинутый анализ стакана"""

        def calculate_obi(self, bids, asks, levels=5):
            """Базовый OBI"""
            bid_volume = sum(float(b[1]) for b in bids[:levels])
            ask_volume = sum(float(a[1]) for a in asks[:levels])
            return (bid_volume - ask_volume) / (bid_volume + ask_volume)

        def calculate_weighted_obi(self, bids, asks):
            """OBI с весом по расстоянию от mid price"""
            mid_price = (float(bids[0][0]) + float(asks[0][0])) / 2

            weighted_bid_vol = sum(
                float(b[1]) / (1 + abs(float(b[0]) - mid_price) / mid_price)
                for b in bids[:10]
            )
            weighted_ask_vol = sum(
                float(a[1]) / (1 + abs(float(a[0]) - mid_price) / mid_price)
                for a in asks[:10]
            )

            return (weighted_bid_vol - weighted_ask_vol) / (weighted_bid_vol + weighted_ask_vol)

        def detect_absorption(self, orderbook_history):
            """Обнаружение поглощения крупных ордеров"""
            # Анализ изменений в стакане для выявления крупных игроков

    Trade Flow Toxicity
    pythondef calculate_vpin(trades, bucket_size=50):
    """Volume-Synchronized Probability of Informed Trading""" # Индикатор токсичности потока ордеров # Высокий VPIN = высокий риск adverse selection
    3.2 Гибридный подход
    pythonclass HybridStrategy:
    """Комбинация классики и HFT"""

        def __init__(self):
            # 70% - Проверенная логика
            self.classic = ClassicStrategy()  # MACD/RSI/EMA

            # 20% - Микроструктура
            self.microstructure = MicrostructureAnalyzer()

            # 10% - Режим рынка
            self.market_regime = MarketRegimeDetector()

        async def get_signal(self, data):
            # Определение режима рынка
            regime = await self.market_regime.detect(data)

            # Адаптивные веса под режим
            if regime == "trending":
                weights = [0.8, 0.15, 0.05]  # Больше вес классике
            elif regime == "ranging":
                weights = [0.5, 0.3, 0.2]   # Больше микроструктуре
            else:  # volatile
                weights = [0.6, 0.2, 0.2]   # Сбалансировано

            signals = await asyncio.gather(
                self.classic.calculate(data),
                self.microstructure.analyze(data),
                self.market_regime.get_confidence()
            )

            return sum(w * s for w, s in zip(weights, signals))

    3.3 Дополнительные стратегии
    Grid Trading (для бокового рынка)
    pythonclass GridStrategy:
    """Сеточная торговля для range-bound рынков"""

        def __init__(self, symbol, price_range, grid_levels=10):
            self.grid_prices = np.linspace(
                price_range[0],
                price_range[1],
                grid_levels
            )
            self.orders = {}

        async def place_grid(self):
            """Размещение сетки ордеров"""
            for price in self.grid_prices:
                if price < self.current_price:
                    # Buy limit orders
                    order = await self.place_limit_order('BUY', price)
                    self.orders[price] = order
                else:
                    # Sell limit orders
                    order = await self.place_limit_order('SELL', price)
                    self.orders[price] = order

    Market Making (элементы)
    pythonclass MarketMakerStrategy:
    """Базовый market making"""

        def calculate_fair_value(self, orderbook, trades):
            """Расчет справедливой цены"""
            # Микро-прогнозирование на основе orderbook dynamics

        def calculate_spread(self, volatility, inventory):
            """Динамический спред"""
            base_spread = 0.001  # 0.1%

            # Расширение при высокой волатильности
            vol_adjustment = volatility * 2

            # Корректировка под инвентарь
            inventory_skew = abs(inventory) * 0.0001

            return base_spread + vol_adjustment + inventory_skew

4.  Управление ордерами и исполнение
    4.1 Типы ордеров и комиссии
    pythonclass OrderManager:
    """Оптимизированное управление ордерами"""

        async def create_order_optimized(self, symbol, side, quantity, price=None):
            """Приоритет на LIMIT postOnly для maker комиссий"""

            # Для HFT критично получать maker rebate (-0.01% на Binance)
            if self.config.prefer_maker_orders and price:
                # PostOnly гарантирует maker комиссию
                params = {
                    'timeInForce': 'GTX',  # Good Till Crossing (PostOnly)
                    'postOnly': True
                }

                try:
                    return await self.exchange.create_limit_order(
                        symbol, side, quantity, price, params
                    )
                except OrderWouldImmediatelyMatch:
                    # Если ордер сразу исполнится, корректируем цену
                    if side == 'BUY':
                        price *= 0.9995  # Чуть ниже для покупки
                    else:
                        price *= 1.0005  # Чуть выше для продажи

                    return await self.create_order_optimized(
                        symbol, side, quantity, price
                    )

            # Fallback на market order если нужно быстрое исполнение
            return await self.exchange.create_market_order(symbol, side, quantity)

    4.2 WebSocket мониторинг
    pythonclass UserDataStreamManager:
    """Реал-тайм мониторинг через User Data Stream"""

        async def start_monitoring(self):
            """Подписка на user data stream"""
            listen_key = await self.exchange.create_listen_key()

            async with websockets.connect(f"{WS_URL}/{listen_key}") as ws:
                while True:
                    msg = await ws.recv()
                    data = orjson.loads(msg)

                    if data['e'] == 'executionReport':
                        # Мгновенное обновление статуса ордера
                        await self.handle_order_update(data)

                    elif data['e'] == 'ACCOUNT_UPDATE':
                        # Обновление позиций в реальном времени
                        await self.handle_position_update(data)

        async def handle_order_update(self, data):
            """Обработка обновлений ордеров"""
            order_id = data['i']
            status = data['X']  # NEW, PARTIALLY_FILLED, FILLED, CANCELED

            # Мгновенная реакция без REST API запросов
            if status == 'FILLED':
                await self.on_order_filled(order_id, data)
            elif status == 'CANCELED':
                await self.on_order_canceled(order_id, data)

5.  Технические улучшения
    5.1 Производительность
    Numba JIT для критических функций
    pythonfrom numba import jit, njit, prange
    import numpy as np

@njit(parallel=True, cache=True)
def calculate_indicators_fast(prices, volumes, period=14):
"""Ультра-быстрый расчет индикаторов"""
n = len(prices)
rsi = np.zeros(n)
vwap = np.zeros(n)

    # Параллельные вычисления
    for i in prange(period, n):
        # RSI
        gains = prices[i-period+1:i+1] - prices[i-period:i]
        avg_gain = np.mean(np.maximum(gains, 0))
        avg_loss = np.mean(np.maximum(-gains, 0))
        rs = avg_gain / (avg_loss + 1e-10)
        rsi[i] = 100 - (100 / (1 + rs))

        # VWAP
        vwap[i] = np.sum(prices[i-period:i] * volumes[i-period:i]) / np.sum(volumes[i-period:i])

    return rsi, vwap

Оптимизация парсинга
python# Замена стандартного json на orjson везде
import orjson

def parse_orderbook(data):
"""3-5x быстрее стандартного json"""
parsed = orjson.loads(data)

    # Преобразование в numpy для быстрых вычислений
    bids = np.array(parsed['bids'], dtype=np.float64)
    asks = np.array(parsed['asks'], dtype=np.float64)

    return bids, asks

5.2 Надежность
Централизованный Rate Limiter (Полный)
pythonclass CentralizedRateLimiter:
"""Thread-safe, asyncio-aware rate limiter"""

    def __init__(self):
        self.limits = {
            'ip_weight': {'limit': 2400, 'window': 60},
            'order_10s': {'limit': 300, 'window': 10},
            'order_1m': {'limit': 1200, 'window': 60},
            'raw_requests': {'limit': 6100, 'window': 300}
        }
        self.buckets = {key: deque() for key in self.limits}
        self.lock = asyncio.Lock()
        self.server_weight = 0

    async def wait_if_needed(self, request_type='info', weight=1):
        """Проактивное управление лимитами"""
        async with self.lock:
            # Очистка устаревших записей
            self._clean_buckets()

            # Проверка всех применимых лимитов
            checks = []
            if request_type == 'order':
                checks = ['ip_weight', 'order_10s', 'order_1m']
            else:
                checks = ['ip_weight', 'raw_requests']

            # Ждем если необходимо
            wait_time = self._calculate_wait_time(checks, weight)
            if wait_time > 0:
                await asyncio.sleep(wait_time)

            # Записываем использование
            self._record_usage(checks, weight)

    def sync_server_weight(self, server_weight):
        """Синхронизация с реальным весом от сервера"""
        self.server_weight = int(server_weight)
        # Корректировка локального счетчика
        if self.server_weight > self._get_local_weight():
            # Сервер считает больше - доверяем ему
            self._adjust_local_weight(self.server_weight)

Мониторинг Quantitative Rules
pythonclass QuantitativeRulesMonitor:
"""Мониторинг UFR и GCR для избежания ограничений"""

    def __init__(self):
        self.orders_placed = deque(maxlen=10000)
        self.orders_canceled = deque(maxlen=10000)

    def get_ufr(self):
        """Unfilled Ratio - должен быть < 0.995"""
        total = len(self.orders_placed)
        if total == 0:
            return 0

        unfilled = sum(1 for o in self.orders_placed if o.status != 'FILLED')
        return unfilled / total

    def get_gcr(self):
        """GTC Cancel Ratio - должен быть < 0.99"""
        gtc_orders = [o for o in self.orders_placed if o.time_in_force == 'GTC']
        if not gtc_orders:
            return 0

        canceled = sum(1 for o in gtc_orders if o.status == 'CANCELED')
        return canceled / len(gtc_orders)

    def check_limits(self):
        """Проверка и предупреждение"""
        ufr = self.get_ufr()
        gcr = self.get_gcr()

        if ufr > 0.99:
            logger.warning(f"UFR критически высок: {ufr:.3f}")
            return False

        if gcr > 0.98:
            logger.warning(f"GCR критически высок: {gcr:.3f}")
            return False

        return True

6. Инфраструктура и развертывание
   VPS требования для HFT
   yamllocation: Tokyo, Japan # Ближе к Binance серверам
   specs:
   cpu: 4+ cores (высокая частота важнее количества)
   ram: 8GB minimum
   network: 1Gbps, низкий jitter
   os: Ubuntu 20.04 LTS (оптимизированное ядро)
   Сетевые оптимизации
   bash# /etc/sysctl.conf оптимизации
   net.core.rmem_max = 134217728
   net.core.wmem_max = 134217728
   net.ipv4.tcp_rmem = 4096 65536 134217728
   net.ipv4.tcp_wmem = 4096 65536 134217728
   net.ipv4.tcp_nodelay = 1
   net.ipv4.tcp_low_latency = 1
   Python оптимизации
   python# main.py
   import asyncio
   import uvloop

# Использование uvloop для 2x производительности

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

# Отключение GC во время критических операций

import gc
gc.disable() # Включать только в безопасных точках

7. Roadmap внедрения
   7.1 Фаза 1: Фундамент (1 неделя)
   День 1-2: Базовая структура

Создать структуру папок BinanceBot_v2
Реализовать core/config.py с dataclasses
Внедрить utils/helpers.py с базовыми функциями
Настроить окружение (requirements.txt)

День 3-4: Логирование и конфигурация

Создать core/unified_logger.py (SQLite)
Реализовать миграцию старых CSV в БД
Создать data/runtime_config.json
Добавить Telegram уведомления в logger

День 5-7: Exchange взаимодействие

Разработать core/rate_limiter.py
Создать базовый core/exchange_client.py
Добавить validate_and_adjust_quantity()
Тестировать на Testnet

Результат: Стабильный фундамент с улучшенной производительностью
7.2 Фаза 2: Оптимизация (1-2 недели)
Неделя 2: Асинхронное ядро

Создать core/async_engine.py (Producer-Consumer)
Реализовать WebSocket подключения для data feeds
Внедрить User Data Stream мониторинг
Добавить core/monitoring.py для метрик

Неделя 3: Риск-менеджмент и микроструктура

Полный core/risk_manager.py
Добавить UFR/GCR мониторинг
Создать strategies/microstructure.py
Реализовать Order Book Imbalance (OBI)
Добавить Trade Flow анализ

Результат: Высокопроизводительное ядро с HFT-сигналами
7.3 Фаза 3: Стратегии (1 неделя)
Неделя 4: Интеграция и тестирование

Перенести текущую стратегию в strategies/scalping_v1.py
Создать HybridStrategy с адаптивными весами
Интегрировать все Telegram команды
Реализовать A/B тестирование старой vs новой версии
Оптимизировать критические функции через Numba

Результат: Полностью функциональный бот v2
7.4 Фаза 4: Расширенные возможности (2-4 недели)
Опциональные улучшения (по приоритету)

Grid Trading (1 неделя)

Реализовать strategies/grid_strategy.py
Добавить автоматическое определение range
Интегрировать с risk manager

Market Making элементы (1-2 недели)

Базовый strategies/market_maker.py
Inventory management
Dynamic spread calculation

Инфраструктурные оптимизации (1 неделя)

Развернуть на VPS в Токио
Настроить сетевые оптимизации
Добавить мониторинг и алерты

8. Ожидаемые результаты
   📊 Детальные метрики улучшения
   ПоказательТекущий ботBinanceBot v2УлучшениеПроизводительностьЛатентность сигнала200-500мс20-50мс-90%Обработка символовПоследовательноПараллельно10-20xЧастота сканирования3-5 сек100мс30-50xНадежностьОшибки API5-10/день<1/день-90%Rate limit hitsЧастыеРедкие-95%Синхронизация позицийПроблемыReal-time100%Торговые метрикиWin Rate~45%55-65%+10-20%Средняя прибыль/сделка0.15%0.20-0.25%+33-66%Количество сделок50-100/день200-500/день3-5xФинансовые результатыПрибыль/час$3-5$8-15+150-200%Просадка5-8%2-4%-50%Sharpe Ratio1.2-1.52.5-3.5+100%
   🎯 Качественные преимущества

Масштабируемость

Поддержка 100+ символов одновременно
Легкое добавление новых стратегий
Возможность запуска нескольких инстансов

Прозрачность и контроль

SQL-аналитика всех операций
Real-time метрики производительности
Полная Telegram интеграция

Готовность к будущему

Архитектура готова для ML (когда накопим данные)
Поддержка других бирж (через ccxt)
Модульность для экспериментов

9. Критические детали реализации
   ⚠️ Важные нюансы

Приоритет WebSocket над REST
python# Всегда пытаемся сначала WebSocket
if ws_available:
result = await ws_create_order()
else:
result = await rest_create_order() # Fallback

Обработка реконнектов
pythonasync def maintain_connection(self):
while True:
try:
await self.connect()
await self.subscribe_all_streams()
except Exception as e:
logger.error(f"Connection lost: {e}")
await asyncio.sleep(5) # Экспоненциальный backoff

Защита от частичных заполнений
pythondef handle_partial_fill(order):
if order.filled < order.amount \* 0.1: # Слишком мало заполнено - отменяем
await cancel_order(order.id)
else: # Корректируем TP/SL под реальный объем
await adjust_tp_sl(order.symbol, order.filled)

Синхронизация времени
python# Критично для HFT
async def sync_time():
server_time = await exchange.fetch_time()
local_time = time.time() \* 1000
TIME_OFFSET = server_time - local_time

=========================================

## GPT update 3 August 2025# 📘 Концепт и Roadmap: BinanceBot v2.3 "OptiFlow HFT"

Версия: 2.3 (SymbolSelector Integration)
Дата: Август 2025
Статус: Реализация

---

## 📑 Содержание

1. Введение и философия
2. Архитектура системы

-   2.1 Структура проекта
-   2.2 Основные компоненты
-   2.3 Потоки данных
-   2.4 Логика SymbolSelector

3. Стратегия и источники альфы
4. Управление ордерами и исполнение
5. Технические улучшения
6. Инфраструктура и развертывание
7. Roadmap внедрения
8. Ожидаемые результаты
9. Критические детали реализации

---

## 1. Введение и философия

"OptiFlow HFT" — высокопроизводительная торговая система для Binance USDC Futures, построенная для минимальных задержек и максимальной гибкости. Основные принципы:

-   Скорость исполнения (REST + WebSocket гибрид)
-   Надёжность (авто-рекавери, failover)
-   Модульность (легкое добавление стратегий)
-   Точность (симуляция реальных условий)

---

## 2. Архитектура системы

### 2.1 Структура проекта

BinanceBot_v2/
├── core/
│ ├── config.py
│ ├── exchange_client.py
│ ├── websocket_manager.py
│ ├── trading_engine.py
│ ├── risk_manager.py
│ ├── unified_logger.py
│ ├── rate_limiter.py
│ └── symbol_manager.py
├── strategies/
│ ├── base_strategy.py
│ ├── scalping_v1.py
│ └── symbol_selector.py
├── utils/
│ ├── helpers.py
│ └── performance.py
├── telegram/
│ ├── telegram_bot.py
│ └── command_handlers.py
├── data/
│ ├── runtime_config.json
│ └── trading_log.db
└── main.py

### 2.2 Основные компоненты

```python
class SymbolSelector:
    def __init__(self, config, symbol_manager, exchange_client, logger):
        self.selected_symbols = []

    async def update_selected_symbols(self):
        # Фильтрация и ранжирование символов
        pass

    async def get_symbols_for_trading(self):
        return self.selected_symbols
```

### 2.3 Потоки данных

```python
# SymbolSelector поток ротации
async def symbol_rotation_loop():
    while True:
        await symbol_selector.update_selected_symbols()
        await asyncio.sleep(rotation_interval)

# TradingEngine получает пары из SymbolSelector
active_symbols = await symbol_selector.get_symbols_for_trading()
```

### 2.4 Логика SymbolSelector

```python
class SymbolSelector:
    async def update_selected_symbols(self):
        # Получение active_symbols из SymbolManager
        # Фильтрация (volume, blacklist, min_price)
        # Расчёт scoring (volume, volatility, trend, win_rate, avg_pnl)
        # Выбор top-N символов
        pass

    async def manual_refresh(self):
        await self.update_selected_symbols()
        return f"🔄 Manual refresh complete: {self.selected_symbols}"
```

---

## 3. Стратегия и источники альфы

```python
class ScalpingV1(BaseStrategy):
    async def analyze_market(self, symbol: str) -> dict | None:
        df = await self.symbol_manager.get_recent_ohlcv(symbol)
        # MACD, RSI, EMA, Volume Hybrid Logic
```

---

## 4. Управление ордерами и исполнение

```python
class TradingEngine:
    async def run_trading_cycle(self):
        active_symbols = await self.symbol_selector.get_symbols_for_trading()
        # Анализ сигналов и исполнение ордеров
```

```python
class ExchangeClient:
    async def place_order(self, symbol, side, qty):
        # REST + WebSocket fallback logic
```

---

## 5. Технические улучшения

```python
# Numba JIT оптимизация индикаторов
@njit(parallel=True)
def calculate_indicators_fast(prices, volumes):
    pass

# orjson для JSON парсинга
import orjson
parsed = orjson.loads(data)
```

---

## 6. Инфраструктура и развертывание

```yaml
location: Tokyo, Japan
cpu: 4+ cores (high freq)
network: 1Gbps low latency
os: Ubuntu 20.04
```

---

## 7. Roadmap внедрения

-   Фаза 1: Базовая структура и логика (готово)
-   Фаза 2: SymbolSelector интеграция (Текущий этап)
-   Фаза 3: Расширенные стратегии (OBI, VPIN)
-   Фаза 4: Market Making, Grid, AI Signals

---

## 8. Ожидаемые результаты

-   500+ сделок/день
-   Win Rate до 60%
-   Сигналы <30ms latency
-   Полная автоматизация отбора пар

---

## 9. Критические детали реализации

```python
# Trading Cycle (до 100ms)
active_symbols = await symbol_selector.get_symbols_for_trading()
entry_signal = await strategy.analyze_market(symbol)
await exchange.place_order(...)

# Telegram Command
@dp.message(Command("refresh_symbols"))
async def refresh_symbols_cmd(message):
    result = await symbol_selector.manual_refresh()
    await message.answer(result)
```

=========================================================
