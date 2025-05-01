# common/config_loader.py

import os

from dotenv import load_dotenv

# Загрузка переменных окружения из файла .env
load_dotenv()


def get_config(var_name: str, default=None):
    """Получить значение переменной окружения или вернуть дефолт."""
    return os.getenv(var_name, default)
