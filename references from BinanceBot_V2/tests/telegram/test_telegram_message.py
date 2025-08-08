#!/usr/bin/env python3
"""
Тестовый скрипт для проверки Telegram бота
"""


import requests


def test_telegram_bot():
    """Тестирует отправку сообщения в Telegram"""

    # Конфигурация
    BOT_TOKEN = "7681205697:AAFB1FogqFMgoTgcu2vkDOmdcd-FYW4YdbU"
    CHAT_ID = "383821734"

    # URL для отправки сообщения
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    # Простое тестовое сообщение
    message = """
🤖 ТЕСТ ПОДКЛЮЧЕНИЯ

✅ Бот: @diplex_trade_alert_bot
✅ Статус: Работает
✅ Время: Тестовое сообщение

📊 Готов к торговле!
"""

    # Данные для отправки (без Markdown)
    data = {
        "chat_id": CHAT_ID,
        "text": message
    }

    try:
        print("📤 Отправка тестового сообщения...")
        print(f"📝 URL: {url}")
        print(f"📝 Chat ID: {CHAT_ID}")
        print(f"📝 Message: {message[:50]}...")

        response = requests.post(url, json=data, timeout=10)

        print(f"📊 Response Status: {response.status_code}")
        print(f"📊 Response Headers: {dict(response.headers)}")

        if response.status_code == 200:
            result = response.json()
            print(f"📊 Response JSON: {result}")

            if result.get("ok"):
                print("✅ Сообщение отправлено успешно!")
                print(f"📝 Message ID: {result['result']['message_id']}")
                return True
            else:
                print(f"❌ Ошибка Telegram API: {result}")
                return False
        else:
            print(f"❌ HTTP ошибка: {response.status_code}")
            print(f"📊 Response Text: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")
        return False

def test_bot_status():
    """Проверяет статус бота"""

    BOT_TOKEN = "7681205697:AAFB1FogqFMgoTgcu2vkDOmdcd-FYW4YdbU"
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"

    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                bot_info = result["result"]
                print("✅ Статус бота:")
                print(f"   Имя: {bot_info['first_name']}")
                print(f"   Username: @{bot_info['username']}")
                print(f"   ID: {bot_info['id']}")
                return True
            else:
                print(f"❌ Ошибка получения статуса: {result}")
                return False
        else:
            print(f"❌ HTTP ошибка: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Ошибка проверки статуса: {e}")
        return False

if __name__ == "__main__":
    print("🧪 ТЕСТИРОВАНИЕ TELEGRAM БОТА")
    print("=" * 40)

    # Проверяем статус бота
    print("1. Проверка статуса бота...")
    if test_bot_status():
        print("✅ Статус бота: ОК\n")

        # Отправляем тестовое сообщение
        print("2. Отправка тестового сообщения...")
        if test_telegram_bot():
            print("✅ Тест завершен успешно!")
            print("\n💡 Теперь можете отправить команды боту:")
            print("   /start - Начать работу")
            print("   /help - Список команд")
            print("   /status - Статус бота")
        else:
            print("❌ Ошибка отправки сообщения")
    else:
        print("❌ Ошибка проверки статуса бота")
