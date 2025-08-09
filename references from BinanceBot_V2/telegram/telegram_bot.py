# Import Windows compatibility error handling
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.utils.markdown import hbold


class TelegramBot:
    def __init__(self, token: str, chat_id: str = None, logger=None):
        self.bot = Bot(token=token)
        self.dp = Dispatcher()
        self.callbacks = {}
        self.chat_id = chat_id
        self.logger = logger

    def setup_callbacks(self, callbacks: dict):
        """Подключает callbacks для бизнес-логики"""
        self.callbacks = callbacks

        # Устанавливаем chat_id из callbacks
        if "chat_id" in callbacks:
            self.chat_id = callbacks["chat_id"]

        # Команды
        self.dp.message(Command("start"))(self._cmd_start)
        self.dp.message(Command("help"))(self._cmd_help)
        self.dp.message(Command("status"))(self._cmd_status)
        self.dp.message(Command("positions"))(self._cmd_positions)
        self.dp.message(Command("balance"))(self._cmd_balance)
        self.dp.message(Command("performance"))(self._cmd_performance)
        self.dp.message(Command("pause"))(self._cmd_pause)
        self.dp.message(Command("resume"))(self._cmd_resume)
        self.dp.message(Command("close"))(self._cmd_close)
        self.dp.message(Command("config"))(self._cmd_config)
        self.dp.message(Command("leverage_report"))(self._cmd_leverage_report)
        self.dp.message(Command("approve_leverage"))(self._cmd_approve_leverage)
        self.dp.message(Command("stop"))(self._cmd_stop)
        self.dp.message(Command("shutdown"))(self._cmd_shutdown)
        self.dp.message(Command("restart"))(self._cmd_restart)
        self.dp.message(Command("run_status"))(self._cmd_run_status)
        self.dp.message(Command("grid_status"))(self._cmd_grid_status)
        self.dp.message(Command("analysis"))(self._cmd_analysis)
        self.dp.message(Command("position_history"))(self._cmd_position_history)

        # Новые команды для агрессивности
        self.dp.message(Command("aggression"))(self._cmd_aggression)
        self.dp.message(Command("aggression_status"))(self._cmd_aggression_status)
        self.dp.message(Command("aggression_conservative"))(self._cmd_aggression_conservative)
        self.dp.message(Command("aggression_balanced"))(self._cmd_aggression_balanced)
        self.dp.message(Command("aggression_aggressive"))(self._cmd_aggression_aggressive)

        # Команды для автоматического переключения
        self.dp.message(Command("auto_switch"))(self._cmd_auto_switch)
        self.dp.message(Command("auto_switch_status"))(self._cmd_auto_switch_status)
        self.dp.message(Command("auto_switch_enable"))(self._cmd_auto_switch_enable)
        self.dp.message(Command("auto_switch_disable"))(self._cmd_auto_switch_disable)
        self.dp.message(Command("market_analysis"))(self._cmd_market_analysis)

        # Команды для детальной аналитики
        self.dp.message(Command("detailed_analytics"))(self._cmd_detailed_analytics)

        # Команды для внешнего мониторинга
        self.dp.message(Command("external_monitoring"))(self._cmd_external_monitoring)
        self.dp.message(Command("external_monitoring_status"))(self._cmd_external_monitoring_status)
        self.dp.message(Command("external_monitoring_enable"))(self._cmd_external_monitoring_enable)
        self.dp.message(Command("external_monitoring_disable"))(
            self._cmd_external_monitoring_disable
        )
        self.dp.message(Command("export_metrics"))(self._cmd_export_metrics)

    def set_chat_id(self, chat_id: str):
        """Устанавливает chat_id для уведомлений"""
        self.chat_id = chat_id

    async def run(self):
        await self.dp.start_polling(self.bot)

    async def polling_loop(self):
        """Запускает polling в бесконечном цикле"""
        try:
            # Удаляем webhook перед запуском polling
            try:
                await self.bot.delete_webhook(drop_pending_updates=True)
                if self.logger:
                    self.logger.log_event("TELEGRAM", "INFO", "🔧 Webhook deleted successfully")
            except Exception as webhook_error:
                if self.logger:
                    self.logger.log_event(
                        "TELEGRAM", "WARNING", f"⚠️ Webhook deletion warning: {webhook_error}"
                    )

            # Запускаем polling без блокировки
            await self.dp.start_polling(self.bot, skip_updates=True)
        except Exception as e:
            if self.logger:
                self.logger.log_event("TELEGRAM", "ERROR", f"❌ Telegram polling error: {e}")
            else:
                print(f"Telegram polling error: {e}")
            # Перезапуск через 5 секунд
            await asyncio.sleep(5)
            await self.polling_loop()

    async def send_notification(self, text: str, chat_id: str = None):
        """Отправляет уведомление в Telegram"""
        # Используем переданный chat_id или сохраненный
        target_chat_id = chat_id or self.chat_id

        if not target_chat_id:
            print(f"❌ Ошибка: chat_id не установлен для отправки: {text}")
            return

        try:
            await self.bot.send_message(chat_id=target_chat_id, text=text)
            print(f"✅ Telegram отправлено: {text[:50]}...")
        except Exception as e:
            print(f"❌ Ошибка отправки в Telegram: {e}")
            print(f"Text: {text}")
            print(f"Chat ID: {target_chat_id}")

    async def send_message(self, text: str, chat_id: str = None):
        """Отправляет сообщение в Telegram (алиас для send_notification)"""
        await self.send_notification(text, chat_id)

    async def send_trade_notification(self, trade_data: dict):
        text = f"🚀 Trade Executed: {hbold(trade_data['symbol'])}\nSide: {trade_data['side']}\nPrice: {trade_data['price']}\nQty: {trade_data['quantity']}"
        await self.send_notification(text)

    # --- Команды ---

    async def _cmd_start(self, message: Message):
        await message.answer("🤖 Bot is online. Use /help to see commands.")

    async def _cmd_help(self, message: Message):
        await message.answer(
            "🤖 BinanceBot Commands:\n\n"
            "📊 Status & Info:\n"
            "/status - Bot status\n"
            "/positions - Active positions\n"
            "/balance - Account balance\n"
            "/performance [days] - PnL report\n"
            "/run_status - Current run summary\n"
            "/grid_status - Grid strategies status\n"
            "/analysis [hours] - Trading session analysis\n"
            "/position_history [hours] - Position history from Binance API\n"
            "/logs [hours] - Recent logs\n"
            "/logs_info - Log files information\n\n"
            "🎛️ Trading Control:\n"
            "/pause - Pause trading\n"
            "/resume - Resume trading\n"
            "/stop - Stop trading (wait for orders)\n"
            "/shutdown - Emergency stop (close all)\n"
            "/restart - Restart bot\n"
            "/close <symbol> - Close position\n\n"
            "⚙️ Configuration:\n"
            "/config - Show current config\n"
            "/leverage_report - Leverage summary\n"
            "/approve_leverage <symbol> <leverage> - Approve leverage change"
        )

    async def _cmd_status(self, message: Message):
        status = await self.callbacks["get_status"]()
        await message.answer(status)

    async def _cmd_positions(self, message: Message):
        positions = await self.callbacks["get_positions"]()
        await message.answer(positions)

    async def _cmd_balance(self, message: Message):
        balance = await self.callbacks["get_balance"]()
        await message.answer(balance)

    async def _cmd_performance(self, message: Message):
        args = message.text.split()
        days = int(args[1]) if len(args) > 1 else 1
        report = await self.callbacks["get_performance"](days)
        await message.answer(report)

    async def _cmd_pause(self, message: Message):
        result = await self.callbacks["pause_trading"]()
        await message.answer(result)

    async def _cmd_resume(self, message: Message):
        result = await self.callbacks["resume_trading"]()
        await message.answer(result)

    async def _cmd_close(self, message: Message):
        args = message.text.split()
        if len(args) < 2:
            await message.answer("Usage: /close <symbol>")
            return
        result = await self.callbacks["close_position"](args[1])
        await message.answer(result)

    async def _cmd_config(self, message: Message):
        config_text = await self.callbacks["get_config"]()
        await message.answer(config_text)

    async def _cmd_leverage_report(self, message: Message):
        report = await self.callbacks["leverage_report"]()
        await message.answer(report)

    async def _cmd_approve_leverage(self, message: Message):
        args = message.text.split()
        if len(args) != 3:
            await message.answer("Usage: /approve_leverage <symbol> <leverage>")
            return
        symbol = args[1].upper()
        leverage = int(args[2])
        result = await self.callbacks["approve_leverage"](symbol, leverage)
        await message.answer(result)

    async def _cmd_stop(self, message: Message):
        """Останавливает торговлю (ждет завершения ордеров)"""
        result = await self.callbacks["stop_trading"]()
        await message.answer(result)

    async def _cmd_shutdown(self, message: Message):
        """Экстренная остановка бота"""
        result = await self.callbacks["shutdown_bot"]()
        await message.answer(result)

    async def _cmd_restart(self, message: Message):
        """Перезапуск бота"""
        result = await self.callbacks["restart_bot"]()
        await message.answer(result)

    async def _cmd_run_status(self, message: Message):
        """Статус текущего рана"""
        result = await self.callbacks["get_run_status"]()
        await message.answer(result)

    async def _cmd_grid_status(self, message: Message):
        """Статус grid стратегий"""
        result = await self.callbacks["get_grid_status"]()
        await message.answer(result)

    async def _cmd_analysis(self, message: Message):
        """Обработчик команды /analysis"""
        try:
            # Парсим параметры (по умолчанию 24 часа)
            text = message.text.strip()
            hours = 24

            if len(text.split()) > 1:
                try:
                    hours = int(text.split()[1])
                    if hours <= 0 or hours > 168:  # Максимум 7 дней
                        await message.answer("❌ Hours must be between 1 and 168 (7 days)")
                        return
                except ValueError:
                    await message.answer("❌ Invalid hours parameter. Use: /analysis [hours]")
                    return

            if "get_analysis_report" in self.callbacks:
                result = await self.callbacks["get_analysis_report"](hours)
                await message.answer(result)
            else:
                await message.answer("❌ Analysis not available")

        except Exception as e:
            await message.answer(f"❌ Analysis error: {e}")

    async def _cmd_position_history(self, message: Message):
        """Обработчик команды /position_history"""
        try:
            # Парсим параметры (по умолчанию 24 часа)
            text = message.text.strip()
            hours = 24

            if len(text.split()) > 1:
                try:
                    hours = int(text.split()[1])
                    if hours <= 0 or hours > 168:  # Максимум 7 дней
                        await message.answer("❌ Hours must be between 1 and 168 (7 days)")
                        return
                except ValueError:
                    await message.answer(
                        "❌ Invalid hours parameter. Use: /position_history [hours]"
                    )
                    return

            if "get_position_history" in self.callbacks:
                result = await self.callbacks["get_position_history"](hours)
                await message.answer(result)
            else:
                await message.answer("❌ Position history not available")

        except Exception as e:
            await message.answer(f"❌ Position history error: {e}")

    async def _cmd_logs(self, message: Message):
        """Обработчик команды /logs"""
        try:
            # Парсим параметры (по умолчанию 4 часа)
            text = message.text.strip()
            hours = 4

            if len(text.split()) > 1:
                try:
                    hours = int(text.split()[1])
                    if hours <= 0 or hours > 168:  # Максимум 7 дней
                        await message.answer("❌ Hours must be between 1 and 168 (7 days)")
                        return
                except ValueError:
                    await message.answer("❌ Invalid hours parameter. Use: /logs [hours]")
                    return

            if "get_recent_logs" in self.callbacks:
                result = await self.callbacks["get_recent_logs"](hours)
                await message.answer(result)
            else:
                await message.answer("❌ Logs not available")

        except Exception as e:
            await message.answer(f"❌ Logs error: {e}")

    async def _cmd_logs_info(self, message: Message):
        """Обработчик команды /logs_info"""
        try:
            if "get_logs_info" in self.callbacks:
                result = await self.callbacks["get_logs_info"]()
                await message.answer(result)
            else:
                await message.answer("❌ Logs info not available")

        except Exception as e:
            await message.answer(f"❌ Logs info error: {e}")

    async def _cmd_aggression(self, message: Message):
        """Команда для управления агрессивностью с параметром"""
        try:
            text = message.text.strip()
            parts = text.split()

            if len(parts) < 2:
                # Показываем текущий статус
                if "get_aggression_status" in self.callbacks:
                    status = await self.callbacks["get_aggression_status"]()
                    await message.answer(status)
                else:
                    await message.answer("❌ Aggression management not available")
                return

            level = parts[1].upper()
            if "set_aggression_level" in self.callbacks:
                result = await self.callbacks["set_aggression_level"](level)
                await message.answer(result)
            else:
                await message.answer("❌ Aggression management not available")

        except Exception as e:
            await message.answer(f"❌ Error: {e}")

    async def _cmd_aggression_status(self, message: Message):
        """Команда для получения статуса агрессивности"""
        try:
            if "get_aggression_status" in self.callbacks:
                status = await self.callbacks["get_aggression_status"]()
                await message.answer(status)
            else:
                await message.answer("❌ Aggression status not available")
        except Exception as e:
            await message.answer(f"❌ Error: {e}")

    async def _cmd_aggression_conservative(self, message: Message):
        """Команда для переключения на консервативный режим"""
        try:
            if "set_aggression_level" in self.callbacks:
                result = await self.callbacks["set_aggression_level"]("CONSERVATIVE")
                await message.answer(result)
            else:
                await message.answer("❌ Aggression management not available")
        except Exception as e:
            await message.answer(f"❌ Error: {e}")

    async def _cmd_aggression_balanced(self, message: Message):
        """Команда для переключения на сбалансированный режим"""
        try:
            if "set_aggression_level" in self.callbacks:
                result = await self.callbacks["set_aggression_level"]("BALANCED")
                await message.answer(result)
            else:
                await message.answer("❌ Aggression management not available")
        except Exception as e:
            await message.answer(f"❌ Error: {e}")

    async def _cmd_aggression_aggressive(self, message: Message):
        """Команда для переключения на агрессивный режим"""
        try:
            if "set_aggression_level" in self.callbacks:
                result = await self.callbacks["set_aggression_level"]("AGGRESSIVE")
                await message.answer(result)
            else:
                await message.answer("❌ Aggression management not available")
        except Exception as e:
            await message.answer(f"❌ Error: {e}")

    async def _cmd_auto_switch(self, message: Message):
        """Команда для управления автоматическим переключением с параметром"""
        try:
            text = message.text.strip()
            parts = text.split()

            if len(parts) < 2:
                # Показываем текущий статус
                if "get_auto_switch_status" in self.callbacks:
                    status = await self.callbacks["get_auto_switch_status"]()
                    await message.answer(status)
                else:
                    await message.answer("❌ Auto-switch management not available")
                return

            action = parts[1].lower()
            if action in ["enable", "on", "true"]:
                if "enable_auto_switch" in self.callbacks:
                    result = await self.callbacks["enable_auto_switch"](True)
                    await message.answer(result)
                else:
                    await message.answer("❌ Auto-switch management not available")
            elif action in ["disable", "off", "false"]:
                if "enable_auto_switch" in self.callbacks:
                    result = await self.callbacks["enable_auto_switch"](False)
                    await message.answer(result)
                else:
                    await message.answer("❌ Auto-switch management not available")
            else:
                await message.answer("❌ Invalid action. Use: enable/disable")

        except Exception as e:
            await message.answer(f"❌ Error: {e}")

    async def _cmd_auto_switch_status(self, message: Message):
        """Команда для получения статуса автоматического переключения"""
        try:
            if "get_auto_switch_status" in self.callbacks:
                status = await self.callbacks["get_auto_switch_status"]()
                await message.answer(status)
            else:
                await message.answer("❌ Auto-switch status not available")
        except Exception as e:
            await message.answer(f"❌ Error: {e}")

    async def _cmd_auto_switch_enable(self, message: Message):
        """Команда для включения автоматического переключения"""
        try:
            if "enable_auto_switch" in self.callbacks:
                result = await self.callbacks["enable_auto_switch"](True)
                await message.answer(result)
            else:
                await message.answer("❌ Auto-switch management not available")
        except Exception as e:
            await message.answer(f"❌ Error: {e}")

    async def _cmd_auto_switch_disable(self, message: Message):
        """Команда для выключения автоматического переключения"""
        try:
            if "enable_auto_switch" in self.callbacks:
                result = await self.callbacks["enable_auto_switch"](False)
                await message.answer(result)
            else:
                await message.answer("❌ Auto-switch management not available")
        except Exception as e:
            await message.answer(f"❌ Error: {e}")

    async def _cmd_market_analysis(self, message: Message):
        """Команда для анализа рыночных условий"""
        try:
            if "analyze_market_conditions" in self.callbacks:
                analysis = await self.callbacks["analyze_market_conditions"]()
                await message.answer(analysis)
            else:
                await message.answer("❌ Market analysis not available")
        except Exception as e:
            await message.answer(f"❌ Error: {e}")

    async def _cmd_detailed_analytics(self, message: Message):
        """Команда для получения детальной аналитики производительности"""
        try:
            text = message.text.strip()
            parts = text.split()

            period = "1d"  # По умолчанию
            if len(parts) > 1:
                period = parts[1]

            if "get_detailed_analytics" in self.callbacks:
                analytics = await self.callbacks["get_detailed_analytics"](period)
                await message.answer(analytics)
            else:
                await message.answer("❌ Detailed analytics not available")
        except Exception as e:
            await message.answer(f"❌ Error: {e}")

    async def _cmd_export_metrics(self, message: Message):
        """Запускает ручной экспорт метрик"""
        try:
            if "manual_export_metrics" in self.callbacks:
                result = await self.callbacks["manual_export_metrics"]()
                await message.answer(result)
            else:
                await message.answer("❌ External monitoring not available")
        except Exception as e:
            await message.answer(f"❌ Error: {e}")

    async def _cmd_external_monitoring(self, message: Message):
        """Показывает информацию о внешнем мониторинге"""
        try:
            if "get_external_monitoring_status" in self.callbacks:
                status = await self.callbacks["get_external_monitoring_status"]()
                await message.answer(status)
            else:
                await message.answer("❌ External monitoring not available")
        except Exception as e:
            await message.answer(f"❌ Error: {e}")

    async def _cmd_external_monitoring_status(self, message: Message):
        """Показывает статус внешнего мониторинга"""
        try:
            if "get_external_monitoring_status" in self.callbacks:
                status = await self.callbacks["get_external_monitoring_status"]()
                await message.answer(status)
            else:
                await message.answer("❌ External monitoring not available")
        except Exception as e:
            await message.answer(f"❌ Error: {e}")

    async def _cmd_external_monitoring_enable(self, message: Message):
        """Включает внешний мониторинг"""
        try:
            if "enable_external_monitoring" in self.callbacks:
                result = await self.callbacks["enable_external_monitoring"](True)
                await message.answer(result)
            else:
                await message.answer("❌ External monitoring not available")
        except Exception as e:
            await message.answer(f"❌ Error: {e}")

    async def _cmd_external_monitoring_disable(self, message: Message):
        """Выключает внешний мониторинг"""
        try:
            if "enable_external_monitoring" in self.callbacks:
                result = await self.callbacks["enable_external_monitoring"](False)
                await message.answer(result)
            else:
                await message.answer("❌ External monitoring not available")
        except Exception as e:
            await message.answer(f"❌ Error: {e}")
