import requests

# Copy your new token from BotFather
telegram_token = "7681205697:AAFB1FogqFMgoTgcu2vkDOmdcd-FYW4YdbU"  # Replace with your actual new token
telegram_chat_id = 383821734  # Your existing chat ID

# Simple test message
url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
payload = {"chat_id": telegram_chat_id, "text": "Test message with new token", "parse_mode": ""}

# Make the API call
try:
    print("Testing new Telegram bot token...")
    response = requests.get(url, params=payload, timeout=10)
    print(f"Response code: {response.status_code}")
    print(f"Response body: {response.text}")
except Exception as e:
    print(f"Error: {e}")
