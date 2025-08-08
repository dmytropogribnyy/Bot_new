#!/usr/bin/env python3
"""
IP Monitor для проверки IP адреса
"""

import asyncio
import time

import requests

from core.unified_logger import UnifiedLogger


class IPMonitor:
    """Мониторинг IP адреса для безопасности"""

    def __init__(self, logger: UnifiedLogger | None = None):
        self.logger = logger
        self.current_ip = None
        self.last_check = 0
        self.check_interval = 300  # 5 минут

    async def get_current_ip(self) -> str | None:
        """Получает текущий IP адрес"""
        try:
            response = requests.get("https://api.ipify.org?format=json", timeout=10)
            if response.status_code == 200:
                return response.json()["ip"]
            return None
        except Exception as e:
            if self.logger:
                # Игнорируем ошибки sys.builtin_module_names и sys.maxsize в Windows
                if "builtin_module_names" not in str(e) and "maxsize" not in str(e):
                    self.logger.log_event("IP_MONITOR", "ERROR", f"❌ Ошибка получения IP: {e}")
            return None

    async def check_ip_change(self) -> bool:
        """Проверяет изменение IP адреса"""
        current_time = time.time()

        # Проверяем не чаще чем раз в 5 минут
        if current_time - self.last_check < self.check_interval:
            return False

        new_ip = await self.get_current_ip()
        if not new_ip:
            return False

        self.last_check = current_time

        if self.current_ip is None:
            # Первая проверка
            self.current_ip = new_ip
            if self.logger:
                self.logger.log_event("IP_MONITOR", "INFO", f"🌐 IP адрес: {new_ip}")
            return False

        if new_ip != self.current_ip:
            # IP изменился!
            old_ip = self.current_ip
            self.current_ip = new_ip

            if self.logger:
                self.logger.log_event("IP_MONITOR", "WARNING",
                    f"⚠️ IP адрес изменился: {old_ip} → {new_ip}")

            return True

        return False

    async def monitor_loop(self):
        """Основной цикл мониторинга IP"""
        if self.logger:
            self.logger.log_event("IP_MONITOR", "INFO", "🌐 Запуск мониторинга IP адреса")

        while True:
            try:
                # Проверяем изменение IP
                ip_changed = await self.check_ip_change()

                if ip_changed:
                    # Отправляем уведомление о смене IP
                    if self.logger:
                        self.logger.log_event("IP_MONITOR", "CRITICAL",
                            "🚨 ВНИМАНИЕ: IP адрес изменился! Проверьте безопасность!")

                # Ждем 5 минут до следующей проверки
                await asyncio.sleep(self.check_interval)

            except Exception as e:
                if self.logger:
                    self.logger.log_event("IP_MONITOR", "ERROR", f"❌ Ошибка мониторинга IP: {e}")
                await asyncio.sleep(60)  # Ждем минуту при ошибке
