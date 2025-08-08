# utils/safe_api.py

import asyncio
import time
from typing import Any, Callable, Optional


async def safe_call_retry_async(
    func: Callable, 
    *args, 
    tries: int = 3, 
    delay: float = 1.0, 
    label: str = "API call", 
    **kwargs
) -> Optional[Any]:
    """
    Безопасный асинхронный вызов с повторными попытками.
    Адаптировано из старого бота.
    """
    for attempt in range(tries):
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
                
            if result is None:
                raise ValueError(f"{label} returned None")

            if attempt > 0:
                print(f"✅ {label} succeeded on attempt {attempt + 1}/{tries}")

            return result

        except Exception as e:
            print(f"❌ {label} failed (attempt {attempt + 1}/{tries}): {e}")

            if attempt < tries - 1:
                sleep_time = delay * (2 ** attempt)
                print(f"⏳ {label} retrying in {sleep_time} s...")
                await asyncio.sleep(sleep_time)
            else:
                print(f"❌ {label} exhausted retries")
                return None


def safe_call_retry_sync(
    func: Callable, 
    *args, 
    tries: int = 3, 
    delay: float = 1.0, 
    label: str = "API call", 
    **kwargs
) -> Optional[Any]:
    """
    Безопасный синхронный вызов с повторными попытками.
    Адаптировано из старого бота.
    """
    for attempt in range(tries):
        try:
            result = func(*args, **kwargs)
            
            if result is None:
                raise ValueError(f"{label} returned None")

            if attempt > 0:
                print(f"✅ {label} succeeded on attempt {attempt + 1}/{tries}")

            return result

        except Exception as e:
            print(f"❌ {label} failed (attempt {attempt + 1}/{tries}): {e}")

            if attempt < tries - 1:
                sleep_time = delay * (2 ** attempt)
                print(f"⏳ {label} retrying in {sleep_time} s...")
                time.sleep(sleep_time)
            else:
                print(f"❌ {label} exhausted retries")
                return None


def safe_float_conversion(value: Any, default: float = 0.0) -> float:
    """
    Безопасное преобразование в float.
    Адаптировано из старого бота.
    """
    try:
        if value is None:
            return default
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_decimal(value: Any) -> float:
    """
    Безопасное преобразование в decimal.
    Адаптировано из старого бота.
    """
    try:
        if value is None:
            return 0.0
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def normalize_symbol(symbol: str) -> str:
    """
    Нормализует символ для использования в API.
    Адаптировано из старого бота.
    """
    if not symbol:
        return ""
    
    # Убираем лишние пробелы
    symbol = symbol.strip().upper()
    
    # Заменяем разделители
    symbol = symbol.replace(" ", "").replace("-", "").replace("_", "")
    
    return symbol


def extract_symbol(symbol: str) -> str:
    """
    Извлекает базовый символ из полного названия.
    Адаптировано из старого бота.
    """
    if not symbol:
        return ""
    
    # Убираем суффиксы
    symbol = symbol.replace(":USDC", "").replace(":USDT", "")
    symbol = symbol.replace("/USDC", "").replace("/USDT", "")
    
    return symbol.strip().upper() 