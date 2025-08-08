#!/usr/bin/env python3
"""
Простой тест Telegram для диагностики
"""

import asyncio

import requests

# Данные из runtime_config.json
TELEGRAM_TOKEN = "7681205697:AAFB1FogqFMgoTgcu2vkDOmdcd-FYW4YdbU"
CHAT_ID = "383821734"

async def test_telegram_simple():
    """Простой тест Telegram через requests"""

    print("🧪 ПРОСТОЙ ТЕСТ TELEGRAM")
    print("=" * 40)

    print(f"📱 Token: {TELEGRAM_TOKEN[:20]}...")
    print(f"💬 Chat ID: {CHAT_ID}")

    # Тест 1: Проверка бота
    print("\n1. Проверка бота...")
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getMe"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            bot_info = response.json()
            print(f"✅ Бот найден: {bot_info['result']['first_name']}")
            print(f"✅ Username: @{bot_info['result']['username']}")
        else:
            print(f"❌ Ошибка получения информации о боте: {response.status_code}")
            print(f"Ответ: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Ошибка проверки бота: {e}")
        return False

    # Тест 2: Отправка сообщения
    print("\n2. Отправка тестового сообщения...")
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {
            "chat_id": CHAT_ID,
            "text": "🧪 Тест Telegram бота\n✅ Соединение работает!"
        }

        response = requests.post(url, json=data, timeout=10)

        if response.status_code == 200:
            result = response.json()
            print("✅ Сообщение отправлено успешно!")
            print(f"✅ Message ID: {result['result']['message_id']}")
        else:
            print(f"❌ Ошибка отправки сообщения: {response.status_code}")
            print(f"Ответ: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Ошибка отправки сообщения: {e}")
        return False

    # Тест 3: Отправка нескольких сообщений
    print("\n3. Отправка нескольких сообщений...")
    messages = [
        "🚀 OptiFlow HFT Bot - Тест 1",
        "💰 Баланс: 343.00 USDC",
        "🌐 IP: 178.41.93.39",
        "✅ Система работает!"
    ]

    for i, message in enumerate(messages, 1):
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            data = {
                "chat_id": CHAT_ID,
                "text": f"Тест {i}: {message}"
            }

            response = requests.post(url, json=data, timeout=10)

            if response.status_code == 200:
                print(f"✅ Тест {i} отправлен")
            else:
                print(f"❌ Ошибка теста {i}: {response.status_code}")

        except Exception as e:
            print(f"❌ Ошибка теста {i}: {e}")

    print("\n🎉 ТЕСТ ЗАВЕРШЕН!")
    print("💡 Проверьте ваш Telegram: @diplex_trade_alert_bot")
    return True

if __name__ == "__main__":
    try:
        result = asyncio.run(test_telegram_simple())
        if result:
            print("\n✅ Telegram тест успешен!")
        else:
            print("\n❌ Telegram тест провален!")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
