# main.py

from trader import start_trading_loop
from telegram_handler import start_telegram_loop
from stats import start_weekly_report_loop

if __name__ == "__main__":
    # Запуск потоков: торговля, Telegram-команды, отчёты
    start_trading_loop()
    start_telegram_loop()
    start_weekly_report_loop()

    # Основной поток ничего не делает, чтобы не завершался
    while True:
        pass
