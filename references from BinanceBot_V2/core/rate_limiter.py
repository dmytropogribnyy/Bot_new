import asyncio
import time
from collections import deque


class RateLimiter:
    def __init__(
        self,
        weight_limit_per_minute: int = 1200,
        request_limit_per_second: int = 10,
        buffer_pct: float = 0.8,
    ):
        self.weight_limit_per_minute = weight_limit_per_minute
        self.request_limit_per_second = request_limit_per_second
        self.buffer_pct = buffer_pct

        # Текущее использование
        self.used_weight = 0
        self.request_count = 0

        # Sliding windows
        self.weight_window = deque()
        self.request_window = deque()

        # Lock для потокобезопасности
        self.lock = asyncio.Lock()

    async def acquire(self, request_weight: int = 1):
        async with self.lock:
            now = time.time()

            # Очищаем старые записи
            while self.weight_window and now - self.weight_window[0][0] > 60:
                _, weight = self.weight_window.popleft()
                self.used_weight -= weight

            while self.request_window and now - self.request_window[0] > 1:
                self.request_window.popleft()
                self.request_count -= 1

            # Проверяем лимиты
            projected_weight = self.used_weight + request_weight
            projected_requests = self.request_count + 1

            # Ограничение веса (per minute)
            if projected_weight > self.weight_limit_per_minute * self.buffer_pct:
                sleep_time = 60 - (now - self.weight_window[0][0])
                print(f"⏳ Weight limit reached. Sleeping for {sleep_time:.2f}s")
                await asyncio.sleep(sleep_time)
                return await self.acquire(request_weight)

            # Ограничение по количеству запросов (per second)
            if projected_requests > self.request_limit_per_second:
                sleep_time = 1 - (now - self.request_window[0])
                print(f"⏳ Request rate limit reached. Sleeping for {sleep_time:.2f}s")
                await asyncio.sleep(sleep_time)
                return await self.acquire(request_weight)

            # Регистрируем текущий запрос
            self.weight_window.append((now, request_weight))
            self.used_weight += request_weight
            self.request_window.append(now)
            self.request_count += 1

    def update_limits(
        self, weight_limit_per_minute: int = None, request_limit_per_second: int = None
    ):
        """Обновляет лимиты rate limiter"""
        if weight_limit_per_minute is not None:
            self.weight_limit_per_minute = weight_limit_per_minute
        if request_limit_per_second is not None:
            self.request_limit_per_second = request_limit_per_second

    async def wrap(self, request_weight: int = 1):
        """Декоратор для методов API"""

        async def decorator(func):
            async def wrapper(*args, **kwargs):
                await self.acquire(request_weight)
                return await func(*args, **kwargs)

            return wrapper

        return decorator
