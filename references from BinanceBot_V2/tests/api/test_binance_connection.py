#!/usr/bin/env python3
"""
Тест подключения к Binance API
"""

import hashlib
import hmac
import time
from urllib.parse import urlencode

import requests


def test_binance_connection():
    """Тестирует подключение к Binance API"""

    # API ключи
    API_KEY = "w2LwaYZq0x1t50ARb3IP69y9XQLssukr78dSnFcQF9XfbngkELA8hprvtTPAhX5S"
    API_SECRET = "hmG7FVUeyQ8wK09596iDJE8ipQqWvpdlRZ8obwAnCwOa8qlZyHyO9fTvr6oQvMFD"

    # Базовый URL для Futures
    BASE_URL = "https://fapi.binance.com"

    print("🧪 ТЕСТ ПОДКЛЮЧЕНИЯ К BINANCE FUTURES")
    print("=" * 40)

    # 1. Тест публичного API (без подписи)
    print("1. Тест публичного API...")
    try:
        response = requests.get(f"{BASE_URL}/fapi/v1/ping")
        if response.status_code == 200:
            print("✅ Публичный API работает")
        else:
            print(f"❌ Публичный API ошибка: {response.status_code}")
    except Exception as e:
        print(f"❌ Ошибка публичного API: {e}")

    # 2. Тест получения времени сервера
    print("\n2. Тест времени сервера...")
    try:
        response = requests.get(f"{BASE_URL}/fapi/v1/time")
        if response.status_code == 200:
            server_time = response.json()["serverTime"]
            print(f"✅ Время сервера: {server_time}")
        else:
            print(f"❌ Ошибка времени сервера: {response.status_code}")
    except Exception as e:
        print(f"❌ Ошибка времени сервера: {e}")

    # 3. Тест получения информации об аккаунте
    print("\n3. Тест информации об аккаунте...")
    try:
        # Параметры запроса
        params = {
            "timestamp": int(time.time() * 1000)
        }

        # Создаем подпись
        query_string = urlencode(params)
        signature = hmac.new(
            API_SECRET.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        # Добавляем подпись к параметрам
        params["signature"] = signature

        # Заголовки
        headers = {
            "X-MBX-APIKEY": API_KEY
        }

        # Запрос к API
        response = requests.get(
            f"{BASE_URL}/fapi/v2/account",
            params=params,
            headers=headers
        )

        if response.status_code == 200:
            account_info = response.json()
            print("✅ Информация об аккаунте получена")
            print(f"   • Статус: {account_info.get('accountStatus', 'N/A')}")
            print(f"   • Комиссии: {account_info.get('commissionRates', 'N/A')}")
        else:
            print(f"❌ Ошибка получения информации об аккаунте: {response.status_code}")
            print(f"   Ответ: {response.text[:200]}...")

    except Exception as e:
        print(f"❌ Ошибка получения информации об аккаунте: {e}")

    # 4. Тест получения баланса
    print("\n4. Тест получения баланса...")
    try:
        response = requests.get(
            f"{BASE_URL}/fapi/v2/account",
            params=params,
            headers=headers
        )

        if response.status_code == 200:
            account_info = response.json()
            assets = account_info.get("assets", [])

            print("✅ Баланс получен:")
            for asset in assets:
                if asset["asset"] == "USDC":
                    balance = float(asset["walletBalance"])
                    available = float(asset["availableBalance"])
                    print(f"   • USDC Баланс: {balance}")
                    print(f"   • USDC Доступно: {available}")
                    break
            else:
                print("   • USDC не найден в аккаунте")
        else:
            print(f"❌ Ошибка получения баланса: {response.status_code}")

    except Exception as e:
        print(f"❌ Ошибка получения баланса: {e}")

    # 5. Тест получения позиций
    print("\n5. Тест получения позиций...")
    try:
        response = requests.get(
            f"{BASE_URL}/fapi/v2/positionRisk",
            params=params,
            headers=headers
        )

        if response.status_code == 200:
            positions = response.json()
            print("✅ Позиции получены:")
            for pos in positions:
                if float(pos["positionAmt"]) != 0:
                    print(f"   • {pos['symbol']}: {pos['positionAmt']} @ {pos['entryPrice']}")
            else:
                print("   • Активных позиций нет")
        else:
            print(f"❌ Ошибка получения позиций: {response.status_code}")

    except Exception as e:
        print(f"❌ Ошибка получения позиций: {e}")

    print("\n" + "=" * 40)
    print("🎉 Тест подключения завершен!")

if __name__ == "__main__":
    test_binance_connection()
