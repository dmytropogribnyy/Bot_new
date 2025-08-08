# core/command_handlers.py


class CommandHandlers:
    def __init__(self, trading_engine, leverage_manager, risk_manager, symbol_selector, post_run_analyzer, logger, telegram_bot, external_monitoring=None):
        self.trading_engine = trading_engine
        self.leverage_manager = leverage_manager
        self.risk_manager = risk_manager
        self.symbol_selector = symbol_selector
        self.post_run_analyzer = post_run_analyzer
        self.logger = logger
        self.telegram_bot = telegram_bot
        self.external_monitoring = external_monitoring
        self.config = trading_engine.config if hasattr(trading_engine, 'config') else None

    async def get_status(self) -> str:
        status = "\U0001f4ca Bot Status:\n"
        if self.config:
            status += f"• Mode: {self.config.exchange_mode}\n"
            status += f"• Max Positions: {self.config.max_concurrent_positions}\n"
        if hasattr(self.trading_engine, 'in_position'):
            status += f"• Active Positions: {len(self.trading_engine.in_position)}\n"
        if hasattr(self.trading_engine, 'get_capital_utilization'):
            status += f"• Capital Utilization: {self.trading_engine.get_capital_utilization():.1%}\n"
        return status

    async def get_positions(self) -> str:
        if hasattr(self.trading_engine, 'get_open_positions'):
            positions = self.trading_engine.get_open_positions()
            if not positions:
                return "\U0001f4ed No active positions."
            text = "\U0001f4cc Active Positions:\n"
            for pos in positions:
                text += f"• {pos['symbol']}: {pos['side']} {pos['qty']} @ {pos['entry_price']}\n"
            return text
        else:
            return "\U0001f4ed Position data not available."

    async def get_balance(self) -> str:
        if hasattr(self.trading_engine, 'exchange'):
            balance = await self.trading_engine.exchange.get_balance()
            return f"\U0001f4b0 Account Balance: {balance:.2f} USDC"
        else:
            return "\U0001f4b0 Balance data not available."

    async def get_performance(self, period: str = "1d") -> str:
        """Получает детальный отчет производительности"""
        try:
            from core.performance_monitor import PerformanceMonitor

            monitor = PerformanceMonitor(self.config, self.logger)
            summary = await monitor.get_performance_summary(period)

            report = f"""
📊 Performance Report ({period})

📈 Trading Statistics:
• Total Trades: {summary['total_trades']}
• Win Rate: {summary['win_rate']:.1%}
• Total PnL: ${summary['total_pnl']:.2f}
• Average PnL: ${summary['avg_pnl']:.2f}
• Max Profit: ${summary['max_profit']:.2f}
• Max Loss: ${summary['max_loss']:.2f}
• Profit Factor: {summary['profit_factor']:.2f}
• Sharpe Ratio: {summary['sharpe_ratio']:.2f}
• Max Drawdown: {summary['max_drawdown']:.1f}%
• Trades/Hour: {summary['trades_per_hour']:.1f}

🎯 Target Status:
"""

            for target_name, target_data in summary["targets_status"].items():
                status_emoji = "✅" if target_data["achieved"] else "❌"
                report += f"• {target_name}: {status_emoji} {target_data['actual']:.2f}/{target_data['target']:.2f}\n"

            if summary["best_symbol"]:
                report += f"\n🏆 Best Symbol: {summary['best_symbol']}"
            if summary["worst_symbol"]:
                report += f"\n📉 Worst Symbol: {summary['worst_symbol']}"

            return report

        except Exception as e:
            return f"❌ Failed to get performance report: {e}"

    async def get_symbol_performance(self, symbol: str, period: str = "1d") -> str:
        """Получает производительность по символу"""
        try:
            from core.performance_monitor import PerformanceMonitor

            monitor = PerformanceMonitor(self.config, self.logger)
            perf = await monitor.get_symbol_performance(symbol, period)

            if perf["total_trades"] == 0:
                return f"📊 No trades found for {symbol} in {period}"

            report = f"""
📊 {symbol} Performance ({period})

📈 Statistics:
• Total Trades: {perf['total_trades']}
• Win Rate: {perf['win_rate']:.1%}
• Total PnL: ${perf['total_pnl']:.2f}
• Average PnL: ${perf['avg_pnl']:.2f}
• Max Profit: ${perf['max_profit']:.2f}
• Max Loss: ${perf['max_loss']:.2f}
• Profit Factor: {perf['profit_factor']:.2f}
"""
            return report

        except Exception as e:
            return f"❌ Failed to get symbol performance: {e}"

    async def get_strategy_performance(self, strategy: str, period: str = "1d") -> str:
        """Получает производительность по стратегии"""
        try:
            from core.performance_monitor import PerformanceMonitor

            monitor = PerformanceMonitor(self.config, self.bot_engine.logger)
            perf = await monitor.get_strategy_performance(strategy, period)

            if perf["total_trades"] == 0:
                return f"📊 No trades found for {strategy} strategy in {period}"

            report = f"""
📊 {strategy} Strategy Performance ({period})

📈 Statistics:
• Total Trades: {perf['total_trades']}
• Win Rate: {perf['win_rate']:.1%}
• Total PnL: ${perf['total_pnl']:.2f}
• Average PnL: ${perf['avg_pnl']:.2f}
• Max Profit: ${perf['max_profit']:.2f}
• Max Loss: ${perf['max_loss']:.2f}
• Profit Factor: {perf['profit_factor']:.2f}
"""
            return report

        except Exception as e:
            return f"❌ Failed to get strategy performance: {e}"

    async def export_performance(self, period: str = "1m", format: str = "csv") -> str:
        """Экспортирует данные производительности"""
        try:
            from core.performance_monitor import PerformanceMonitor

            monitor = PerformanceMonitor(self.config, self.bot_engine.logger)
            result = await monitor.export_performance_data(period, format)

            return f"📊 Export completed: {result}"

        except Exception as e:
            return f"❌ Export failed: {e}"

    async def pause_trading(self) -> str:
        self.bot_engine.pause_trading()
        return "⏸ Trading paused."

    async def resume_trading(self) -> str:
        self.bot_engine.resume_trading()
        return "▶️ Trading resumed."

    async def close_position(self, symbol: str) -> str:
        result = await self.bot_engine.close_position(symbol)
        if result.get("success"):
            return f"✅ Position {symbol} closed."
        else:
            return f"❌ Failed to close {symbol}: {result.get('error', 'Unknown error')}"

    async def get_config(self) -> str:
        text = (
            f"\U0001f6e0 Config Summary:\n"
            f"• Risk per trade: {self.config.base_risk_pct:.1%}\n"
            f"• SL: {self.config.sl_percent:.1%}\n"
            f"• Max Positions: {self.config.max_concurrent_positions}\n"
            f"• AutoProfit: {self.config.auto_profit_threshold:.1%}\n"
            f"• Symbols: {len(self.symbol_selector.selected_symbols)}\n"
        )
        return text

    async def leverage_report(self) -> str:
        report = self.leverage_manager.get_leverage_report()
        text = "\U0001f4ca Leverage Report:\n"
        for level, symbols in report["risk_levels"].items():
            text += f"\n• {level.title()}: {len(symbols)} symbols"
        return text

    async def approve_leverage(self, symbol: str, leverage: int) -> str:
        result = self.leverage_manager.apply_suggestion(symbol, leverage, auto_apply=True)
        if result.get("applied"):
            return f"✅ Leverage for {symbol} updated: {result['old']}x → {result['new']}x"
        else:
            return f"❌ Failed to apply leverage change for {symbol}"

    async def refresh_symbols(self) -> str:
        result = await self.symbol_selector.manual_refresh()
        return result

    async def get_analysis_report(self, hours: int = 24) -> str:
        """Получает анализ торговой сессии"""
        try:
            from core.post_run_analyzer import PostRunAnalyzer

            analyzer = PostRunAnalyzer(self.logger, self.config)

            # Используем новый метод для генерации детального отчета
            report = await analyzer.generate_detailed_report(hours)
            return report

        except Exception as e:
            return f"❌ Failed to get analysis report: {e}"

    async def get_quick_summary(self, hours: int = 24) -> str:
        """Получает краткую сводку"""
        try:
            from core.post_run_analyzer import PostRunAnalyzer

            analyzer = PostRunAnalyzer(self.logger, self.config)

            # Используем новый метод для генерации краткой сводки
            summary = await analyzer.generate_quick_summary(hours)
            return summary

        except Exception as e:
            return f"❌ Failed to get quick summary: {e}"

    async def get_position_history(self, hours: int = 24) -> str:
        """Получает сводку позиций из Binance API"""
        try:
            from core.position_history_reporter import PositionHistoryReporter

            reporter = PositionHistoryReporter(self.config, self.logger)
            await reporter.initialize()

            try:
                summary, positions = await reporter.generate_position_report(hours)

                report = f"""
📊 Position History Report ({hours}h)

📈 Trading Summary:
• Total Trades: {summary.total_trades}
• Winning Trades: {summary.winning_trades}
• Losing Trades: {summary.losing_trades}
• Win Rate: {summary.win_rate:.1%}

💰 Financial Summary:
• Total PnL: ${summary.total_pnl:.2f}
• Total Fees: ${summary.total_fees:.2f}
• Funding Fees: ${summary.funding_fees:.2f}
• Net PnL: ${summary.net_pnl:.2f}

📊 Performance Metrics:
• Avg Profit/Trade: ${summary.avg_profit_per_trade:.2f}
• Avg Loss/Trade: ${summary.avg_loss_per_trade:.2f}
• Max Profit: ${summary.max_profit:.2f}
• Max Loss: ${summary.max_loss:.2f}
• Avg Hold Time: {summary.avg_hold_duration_minutes:.1f} min

🏆 Symbol Analysis:
• Best Symbol: {summary.best_symbol or 'N/A'}
• Worst Symbol: {summary.worst_symbol or 'N/A'}
"""

                # Добавляем топ-5 символов по производительности
                if summary.symbol_performance:
                    report += "\n📋 Top Symbols:\n"
                    sorted_symbols = sorted(
                        summary.symbol_performance.items(),
                        key=lambda x: x[1]['pnl'],
                        reverse=True
                    )[:5]

                    for symbol, perf in sorted_symbols:
                        report += f"• {symbol}: ${perf['pnl']:.2f} ({perf['trades']} trades, {perf['win_rate']:.1%} WR)\n"

                return report

            finally:
                await reporter.cleanup()

        except Exception as e:
            return f"❌ Failed to get position history: {e}"

    async def get_reports_info(self) -> str:
        """Получает информацию о сохраненных отчетах"""
        try:
            from core.post_run_analyzer import PostRunAnalyzer

            analyzer = PostRunAnalyzer(self.bot_engine.logger, self.config)
            reports_info = analyzer.get_reports_info()

            if reports_info["total_reports"] == 0:
                return "📁 Нет сохраненных отчетов"

            report = "📁 ИНФОРМАЦИЯ ОБ ОТЧЕТАХ:\n\n"
            report += f"📊 Всего отчетов: {reports_info['total_reports']}\n"
            report += f"💾 Общий размер: {reports_info['total_size_mb']} MB\n\n"
            report += "📋 ПОСЛЕДНИЕ ОТЧЕТЫ:\n"

            for i, file_info in enumerate(reports_info["reports"][:5], 1):
                report += f"{i}. {file_info['filename']}\n"
                report += f"   📄 Тип: {file_info['type'].upper()}\n"
                report += f"   💾 Размер: {file_info['size_mb']} MB\n"
                report += f"   ⏰ Изменен: {file_info['modified']}\n\n"

            if reports_info["total_reports"] > 5:
                report += f"... и еще {reports_info['total_reports'] - 5} отчетов"

            return report

        except Exception as e:
            return f"❌ Failed to get reports info: {e}"

    async def get_logs_info(self) -> str:
        """Получает информацию о файлах логов"""
        try:
            log_files_info = self.bot_engine.logger.get_log_files_info()

            report = "📁 Информация о файлах логов:\n\n"

            for log_file, info in log_files_info.items():
                if info.get('exists', True):
                    report += f"📄 {log_file}:\n"
                    report += f"   • Размер: {info['size_mb']:.2f} MB\n"
                    report += f"   • Строк: {info['lines']}\n"
                    report += f"   • Изменен: {info['modified'][:19]}\n\n"
                else:
                    report += f"❌ {log_file}: Файл не существует\n\n"

            return report

        except Exception as e:
            return f"❌ Failed to get logs info: {e}"

    async def get_recent_logs(self, hours: int = 4) -> str:
        """Получает последние логи"""
        try:
            logs = self.bot_engine.logger.get_recent_logs(hours)

            if not logs:
                return f"📋 Нет логов за последние {hours} часов"

            report = f"📋 Последние логи ({hours}ч, показано {min(10, len(logs))}):\n\n"

            for i, log in enumerate(logs[:10]):
                timestamp = log['timestamp'][:19] if log['timestamp'] else 'N/A'
                level = log['level']
                component = log['component']
                message = log['message'][:50] + "..." if len(log['message']) > 50 else log['message']

                report += f"{i+1}. [{timestamp}] {level}[{component}] {message}\n"

            if len(logs) > 10:
                report += f"\n... и еще {len(logs) - 10} записей"

            return report

        except Exception as e:
            return f"❌ Failed to get recent logs: {e}"

    async def get_grid_status(self) -> str:
        """Получает статус grid стратегий"""
        try:
            # Получаем стратегию grid из engine
            if hasattr(self.bot_engine, 'strategy_manager'):
                grid_strategy = self.bot_engine.strategy_manager.strategies.get("grid")
                if grid_strategy:
                    grids_status = await grid_strategy.get_all_grids_status()

                    if not grids_status:
                        return "📊 No active grid strategies."

                    report = "📊 Grid Strategies Status:\n\n"
                    for symbol, status in grids_status.items():
                        if status:
                            report += f"🔸 {symbol}:\n"
                            report += f"   • Center Price: ${status['center_price']:.4f}\n"
                            report += f"   • Levels: {status['executed_orders']}/{status['total_levels']}\n"
                            report += f"   • Completion: {status['completion_rate']:.1%}\n"
                            report += f"   • Created: {status['created_at'].strftime('%H:%M:%S')}\n"
                            if status['stats']['total_trades'] > 0:
                                report += f"   • Trades: {status['stats']['total_trades']}\n"
                                report += f"   • Win Rate: {status['stats']['win_rate']:.1%}\n"
                            report += "\n"

                    return report
                else:
                    return "❌ Grid strategy not available."
            else:
                return "❌ Strategy manager not available."

        except Exception as e:
            return f"❌ Failed to get grid status: {e}"

    async def stop_trading(self) -> str:
        """Останавливает торговлю (ждет завершения ордеров)"""
        try:
            # Логируем начало остановки
            self.bot_engine.logger.log_event("TELEGRAM", "WARNING", "Trading stop requested via Telegram")

            # Приостанавливаем торговлю
            self.bot_engine.pause_trading()

            # Получаем активные позиции
            positions = self.bot_engine.get_open_positions()

            if not positions:
                return "⏸ Trading stopped. No active positions."

            # Ждем завершения позиций (максимум 5 минут)
            import asyncio
            from datetime import datetime, timedelta

            start_time = datetime.utcnow()
            timeout = timedelta(minutes=5)

            while positions and (datetime.utcnow() - start_time) < timeout:
                await asyncio.sleep(1)  # Проверяем каждую секунду (для тестов)
                positions = self.bot_engine.get_open_positions()

            if positions:
                return f"⚠️ Trading stopped but {len(positions)} positions still active. Use /shutdown for emergency stop."
            else:
                return "✅ Trading stopped successfully. All positions closed."

        except Exception as e:
            return f"❌ Error stopping trading: {e}"

    async def shutdown_bot(self) -> str:
        """Экстренная остановка бота (закрывает все позиции)"""
        try:
            # Логируем экстренную остановку
            self.bot_engine.logger.log_event("TELEGRAM", "CRITICAL", "Emergency shutdown requested via Telegram")

            # Получаем активные позиции
            positions = self.bot_engine.get_open_positions()

            if positions:
                # Принудительно закрываем все позиции
                closed_count = 0
                for pos in positions:
                    try:
                        result = await self.bot_engine.close_position(pos['symbol'])
                        if result.get("success"):
                            closed_count += 1
                    except Exception as e:
                        self.bot_engine.logger.log_event("SHUTDOWN", "ERROR", f"Failed to close {pos['symbol']}: {e}")

                # Останавливаем торговлю
                self.bot_engine.pause_trading()

                return f"🚨 Emergency shutdown executed. Closed {closed_count}/{len(positions)} positions."
            else:
                # Просто останавливаем торговлю
                self.bot_engine.pause_trading()
                return "🛑 Bot shutdown completed. No active positions."

        except Exception as e:
            return f"❌ Error during shutdown: {e}"

    async def get_run_status(self) -> str:
        """Получает статус текущего рана"""
        try:
            # Получаем сводку за последние 24 часа
            summary = self.bot_engine.logger.get_run_summary(24)

            # Получаем статистику логов
            log_stats = self.bot_engine.logger.get_log_stats()

            report = f"""
📊 Run Status (Last 24h)

🎯 Trading Performance:
• Trades: {summary['total_trades']}
• PnL: ${summary['total_pnl']:.2f}
• Win Rate: {summary['win_rate']:.1%}
• Avg PnL: ${summary['avg_pnl']:.2f}

📈 System Events:
"""
            for level, count in summary['events'].items():
                emoji = {"INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "❌", "CRITICAL": "🚨"}.get(level, "📊")
                report += f"• {emoji} {level}: {count}\n"

            report += f"""
💾 Log Stats:
• DB Size: {log_stats['db_size_mb']}MB / {log_stats['max_size_mb']}MB
• Records: {sum(log_stats['table_counts'].values())}
• Last Update: {summary['last_updated'][:19]}
"""

            return report

        except Exception as e:
            return f"❌ Failed to get run status: {e}"

    async def restart_bot(self) -> str:
        """Перезапуск бота"""
        try:
            self.bot_engine.logger.log_event("TELEGRAM", "WARNING", "Bot restart requested via Telegram")

            # Останавливаем торговлю
            self.bot_engine.pause_trading()

            # Отправляем сигнал для перезапуска
            if hasattr(self.bot_engine, 'restart_requested'):
                self.bot_engine.restart_requested = True

            return "🔄 Bot restart initiated. Please wait..."

        except Exception as e:
            return f"❌ Error restarting bot: {e}"

    async def get_aggression_status(self) -> str:
        """Получает текущий статус агрессивности"""
        try:
            from core.aggression_manager import AggressionManager

            # Получаем агрессию из trading_engine или создаем новый
            if hasattr(self.trading_engine, 'aggression_manager'):
                aggression_manager = self.trading_engine.aggression_manager
            else:
                aggression_manager = AggressionManager(self.config, self.logger)

            current_level = aggression_manager.get_aggression_level()
            available_levels = aggression_manager.get_available_levels()
            profile_info = aggression_manager.get_profile_info()

            status = f"""
🎯 **Aggression Status**

📊 Current Level: **{current_level}**
🔄 Available Levels: {', '.join(available_levels)}

📈 Profile Settings:
"""

            if profile_info:
                for key, value in profile_info.items():
                    if key != 'description':
                        status += f"• {key}: {value}\n"

            # Добавляем информацию о стратегиях
            if hasattr(self.trading_engine, 'strategy_manager'):
                strategy_info = await self._get_strategy_aggression_info()
                status += f"\n📋 Strategy Status:\n{strategy_info}"

            return status

        except Exception as e:
            return f"❌ Failed to get aggression status: {e}"

    async def set_aggression_level(self, level: str) -> str:
        """Устанавливает уровень агрессивности"""
        try:
            from core.aggression_manager import AggressionManager

            # Получаем агрессию из trading_engine или создаем новый
            if hasattr(self.trading_engine, 'aggression_manager'):
                aggression_manager = self.trading_engine.aggression_manager
            else:
                aggression_manager = AggressionManager(self.config, self.logger)

            # Валидируем уровень
            available_levels = aggression_manager.get_available_levels()
            if level.upper() not in [l.upper() for l in available_levels]:
                return f"❌ Invalid aggression level. Available: {', '.join(available_levels)}"

            # Устанавливаем уровень
            success = aggression_manager.set_aggression_level(level.upper())

            if success:
                # Обновляем стратегии если есть strategy_manager
                if hasattr(self.trading_engine, 'strategy_manager'):
                    await self._update_strategies_aggression()

                return f"✅ Aggression level changed to: **{level.upper()}**\n\n{await self.get_aggression_status()}"
            else:
                return f"❌ Failed to change aggression level to: {level.upper()}"

        except Exception as e:
            return f"❌ Error setting aggression level: {e}"

    async def _get_strategy_aggression_info(self) -> str:
        """Получает информацию об агрессивности стратегий"""
        try:
            strategy_manager = self.trading_engine.strategy_manager
            info = []

            for strategy_name, strategy in strategy_manager.strategies.items():
                if hasattr(strategy, 'aggression_manager'):
                    settings = strategy.aggression_manager.get_strategy_settings(strategy_name)
                    info.append(f"• {strategy_name}: {settings.get('aggression_mode', 'UNKNOWN')}")
                else:
                    info.append(f"• {strategy_name}: NO_AGGRESSION_MANAGER")

            return '\n'.join(info) if info else "No strategies with aggression manager"

        except Exception as e:
            return f"Error getting strategy info: {e}"

    async def _update_strategies_aggression(self):
        """Обновляет агрессивность всех стратегий"""
        try:
            if hasattr(self.trading_engine, 'strategy_manager'):
                strategy_manager = self.trading_engine.strategy_manager

                for strategy_name, strategy in strategy_manager.strategies.items():
                    if hasattr(strategy, '_update_settings_from_aggression'):
                        await strategy._update_settings_from_aggression()
                        self.logger.log_strategy_event(strategy_name, "AGGRESSION_UPDATED",
                                                     f"Updated via Telegram command")

        except Exception as e:
            self.logger.log_event("COMMAND_HANDLERS", "ERROR", f"Failed to update strategies aggression: {e}")

    async def get_auto_switch_status(self) -> str:
        """Получает статус автоматического переключения агрессивности"""
        try:
            from core.aggression_manager import AggressionManager

            # Получаем агрессию из trading_engine или создаем новый
            if hasattr(self.trading_engine, 'aggression_manager'):
                aggression_manager = self.trading_engine.aggression_manager
            else:
                aggression_manager = AggressionManager(self.config, self.logger)

            status = aggression_manager.get_auto_switch_status()

            report = f"""
🤖 **Auto-Switch Status**

📊 Current Level: **{status['current_level']}**
🔄 Auto-Switch: **{'ENABLED' if status['enabled'] else 'DISABLED'}**

⚙️ Market Conditions:
• Volatility Threshold: {status['market_conditions']['volatility_threshold']:.3f}
• Trend Strength Threshold: {status['market_conditions']['trend_strength_threshold']:.2f}
• Volume Spike Threshold: {status['market_conditions']['volume_spike_threshold']:.1f}x
• Market Sentiment Threshold: {status['market_conditions']['market_sentiment_threshold']:.2f}

⏰ Last Switch: {status['last_switch_time']} seconds ago
🕐 Min Switch Interval: {status['min_switch_interval']} seconds
"""

            return report

        except Exception as e:
            return f"❌ Failed to get auto-switch status: {e}"

    async def enable_auto_switch(self, enabled: bool = True) -> str:
        """Включает/выключает автоматическое переключение агрессивности"""
        try:
            from core.aggression_manager import AggressionManager

            # Получаем агрессию из trading_engine или создаем новый
            if hasattr(self.trading_engine, 'aggression_manager'):
                aggression_manager = self.trading_engine.aggression_manager
            else:
                aggression_manager = AggressionManager(self.config, self.logger)

            aggression_manager.enable_auto_switch(enabled)

            status = "ENABLED" if enabled else "DISABLED"
            return f"✅ Auto-switch aggression: **{status}**\n\n{await self.get_auto_switch_status()}"

        except Exception as e:
            return f"❌ Error enabling auto-switch: {e}"

    async def analyze_market_conditions(self) -> str:
        """Анализирует текущие рыночные условия"""
        try:
            from core.aggression_manager import AggressionManager

            # Получаем агрессию из trading_engine или создаем новый
            if hasattr(self.trading_engine, 'aggression_manager'):
                aggression_manager = self.trading_engine.aggression_manager
            else:
                aggression_manager = AggressionManager(self.config, self.logger)

            # Получаем рыночные данные (упрощенная версия)
            market_data = {}

            # Пытаемся получить данные из trading_engine
            if hasattr(self.trading_engine, 'get_market_data'):
                market_data = await self.trading_engine.get_market_data()
            elif hasattr(self.trading_engine, 'symbol_selector'):
                # Получаем данные первого активного символа
                symbols = await self.trading_engine.symbol_selector.get_symbols_for_trading()
                if symbols:
                    symbol = symbols[0]
                    # Упрощенный анализ - в реальности нужно получать реальные данные
                    market_data = {
                        'price': 50000,  # Пример
                        'atr': 1000,     # Пример
                        'rsi': 45,       # Пример
                        'volume_ratio': 1.2  # Пример
                    }

            analysis = aggression_manager.analyze_market_conditions(market_data)

            report = f"""
📊 **Market Conditions Analysis**

🎯 Current Level: **{analysis['recommended_level']}**
🔄 Should Switch: **{'YES' if analysis['should_switch'] else 'NO'}**

📈 Market Metrics:
• Volatility: {analysis['volatility']:.2f}%
• Trend Strength: {analysis['trend_strength']:.2f}
• Volume Spike: {analysis['volume_spike']:.2f}x
• Market Sentiment: {analysis['market_sentiment']:.2f}

💡 Recommendation: {analysis['reason'] if analysis['reason'] else 'No specific recommendation'}
"""

            return report

        except Exception as e:
            return f"❌ Failed to analyze market conditions: {e}"

    async def get_detailed_analytics(self, period: str = "1d") -> str:
        """Получает детальную аналитику производительности"""
        try:
            from core.metrics_aggregator import MetricsAggregator

            # Получаем агрегатор метрик
            if hasattr(self.trading_engine, 'metrics_aggregator'):
                metrics_aggregator = self.trading_engine.metrics_aggregator
            else:
                metrics_aggregator = MetricsAggregator(self.config, self.logger)

            # Получаем детальную аналитику
            analytics = await metrics_aggregator.get_detailed_analytics(period)

            if not analytics:
                return f"❌ No analytics data available for period: {period}"

            report = f"""
📊 **Detailed Analytics Report ({period})**

📈 **Basic Metrics:**
• Total Trades: {analytics['basic_metrics']['total_trades']}
• Win Rate: {analytics['basic_metrics']['win_rate']:.1%}
• Total PnL: ${analytics['basic_metrics']['total_pnl']:.2f}
• Profit Factor: {analytics['basic_metrics']['profit_factor']:.2f}
• Sharpe Ratio: {analytics['basic_metrics']['sharpe_ratio']:.2f}
• Max Drawdown: {analytics['basic_metrics']['max_drawdown']:.1f}%

⏰ **Time Analysis:**
"""

            if analytics['time_analysis']:
                time_analysis = analytics['time_analysis']
                if time_analysis.get('best_period'):
                    report += f"• Best Period: {time_analysis['best_period']['period']} (${time_analysis['best_period']['total_pnl']:.2f})\n"
                if time_analysis.get('worst_period'):
                    report += f"• Worst Period: {time_analysis['worst_period']['period']} (${time_analysis['worst_period']['total_pnl']:.2f})\n"

            report += f"""
🎯 **Strategy Analysis:**
"""

            if analytics['strategy_correlation']:
                strategy_analysis = analytics['strategy_correlation']
                if strategy_analysis.get('best_strategy'):
                    best = strategy_analysis['best_strategy']
                    report += f"• Best Strategy: {best['strategy']} (${best['total_pnl']:.2f}, {best['win_rate']:.1%})\n"
                if strategy_analysis.get('worst_strategy'):
                    worst = strategy_analysis['worst_strategy']
                    report += f"• Worst Strategy: {worst['strategy']} (${worst['total_pnl']:.2f}, {worst['win_rate']:.1%})\n"

            report += f"""
💎 **Symbol Analysis:**
"""

            if analytics['symbol_analysis']:
                symbol_analysis = analytics['symbol_analysis']
                if symbol_analysis.get('best_symbol'):
                    best = symbol_analysis['best_symbol']
                    report += f"• Best Symbol: {best['symbol']} (${best['total_pnl']:.2f}, {best['win_rate']:.1%})\n"
                if symbol_analysis.get('worst_symbol'):
                    worst = symbol_analysis['worst_symbol']
                    report += f"• Worst Symbol: {worst['symbol']} (${worst['total_pnl']:.2f}, {worst['win_rate']:.1%})\n"

            report += f"""
⚠️ **Risk Analysis:**
"""

            if analytics['risk_analysis']:
                risk = analytics['risk_analysis']
                report += f"• VaR (95%): ${risk['var_95']:.2f}\n"
                report += f"• Max Consecutive Losses: {risk['max_consecutive_losses']}\n"
                report += f"• Risk-Adjusted Return: {risk['risk_adjusted_return']:.2f}\n"
                report += f"• Loss Trades: {risk['loss_trades']}/{risk['total_trades']}\n"
                report += f"• Avg Loss: ${risk['avg_loss']:.2f}\n"
                report += f"• Avg Profit: ${risk['avg_profit']:.2f}\n"

            report += f"""
📈 **Trend Analysis:**
"""

            if analytics['trend_analysis']:
                trend = analytics['trend_analysis']
                report += f"• Trend: {trend['trend']}\n"
                report += f"• Slope: {trend['slope']:.4f}\n"
                report += f"• Volatility: {trend['volatility']:.2f}\n"
                report += f"• Consistency: {trend['consistency']:.1%}\n"

            return report

        except Exception as e:
            return f"❌ Failed to get detailed analytics: {e}"

    async def get_external_monitoring_status(self) -> str:
        """Получает статус внешнего мониторинга"""
        try:
            if not self.external_monitoring:
                return "❌ External monitoring not available"

            status = await self.external_monitoring.get_status()

            report = f"""
🔗 External Monitoring Status

📊 General:
• Enabled: {'✅' if status['enabled'] else '❌'}
• Running: {'✅' if status['running'] else '❌'}
• Export Interval: {status['export_interval']}s

📈 Systems:
• Prometheus: {'✅' if status['prometheus_enabled'] else '❌'}
• Grafana: {'✅' if status['grafana_enabled'] else '❌'}
• Webhook: {'✅' if status['webhook_enabled'] else '❌'}

🕐 Last Export: {status['last_export'] or 'Never'}
"""
            return report

        except Exception as e:
            return f"❌ Failed to get external monitoring status: {e}"

    async def enable_external_monitoring(self, enabled: bool = True) -> str:
        """Включает/выключает внешний мониторинг"""
        try:
            if not self.external_monitoring:
                return "❌ External monitoring not available"

            if enabled:
                await self.external_monitoring.start()
                return "✅ External monitoring enabled and started"
            else:
                await self.external_monitoring.stop()
                return "❌ External monitoring disabled and stopped"

        except Exception as e:
            return f"❌ Failed to toggle external monitoring: {e}"

    async def manual_export_metrics(self) -> str:
        """Запускает ручной экспорт метрик"""
        try:
            if not self.external_monitoring:
                return "❌ External monitoring not available"

            success = await self.external_monitoring.manual_export()

            if success:
                return "✅ Manual metrics export completed successfully"
            else:
                return "❌ Manual metrics export failed"

        except Exception as e:
            return f"❌ Failed to export metrics: {e}"
