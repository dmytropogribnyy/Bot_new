import requests

token = "7681205697:AAEXMKIoWYP_vwH9ek5o_2295bH0hwSUtJ0"
chat_id = "383821734"
message = "Test message from direct API call"

response = requests.get(
    f"https://api.telegram.org/bot{token}/sendMessage", params={"chat_id": chat_id, "text": message}
)

print(response.status_code)
print(response.text)
