# common/messaging.py

from telegram_handler import send_error_to_admin, send_message_to_channel


def send_notification(text: str):
    """Отправить обычное уведомление пользователю."""
    send_message_to_channel(text)


def send_error(text: str):
    """Отправить сообщение об ошибке админу."""
    send_error_to_admin(text)
