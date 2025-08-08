#!/usr/bin/env python3
"""
Position History Reporter для BinanceBot_V2
Получает сводку позиций и торговых данных из Binance API
для точной перепроверки статистики по рану
"""

import asyncio
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from core.config import TradingConfig
from core.exchange_client import OptimizedExchangeClient
from core.unified_logger import UnifiedLogger


@dataclass
class TradePosition:
    """Данные о торговой позиции"""
    symbol: str
    side: str  # 'buy' или 'sell'
    entry_price: float
    exit_price: float
    quantity: float
    entry_time: datetime
    exit_time: datetime
    entry_order_id: str
    exit_order_id: str
    entry_fee: float
    exit_fee: float
    realized_pnl: float
    hold_duration_minutes: float


@dataclass
class PositionSummary:
    """Сводка по позициям"""
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_pnl: float
    total_fees: float
    win_rate: float
    avg_profit_per_trade: float
    avg_loss_per_trade: float
    max_profit: float
    max_loss: float
    avg_hold_duration_minutes: float
    best_symbol: str | None
    worst_symbol: str | None
    symbol_performance: dict[str, dict[str, float]]
    funding_fees: float
    net_pnl: float


class PositionHistoryReporter:
    """Репортер для получения сводки позиций из Binance API"""

    def __init__(self, config: TradingConfig, logger: UnifiedLogger | None = None):
        self.config = config
        self.logger = logger or UnifiedLogger(config)
        self.exchange_client = OptimizedExchangeClient(config, logger)

    async def initialize(self) -> bool:
        """Инициализация репортера"""
        try:
            await self.exchange_client.initialize()
            self.logger.log_event("POSITION_REPORTER", "INFO", "✅ Position History Reporter initialized")
            return True
        except Exception as e:
            self.logger.log_event("POSITION_REPORTER", "ERROR", f"❌ Failed to initialize: {e}")
            return False

    async def get_user_trades(self, symbol: str | None = None,
                            start_time: datetime | None = None,
                            end_time: datetime | None = None,
                            limit: int = 1000) -> list[dict[str, Any]]:
        """Получает историю сделок пользователя"""
        try:
            async with self.exchange_client._async_semaphore:
                await self.exchange_client.rate_limiter.acquire(10)

                params = {
                    'limit': limit
                }

                if symbol:
                    params['symbol'] = symbol

                if start_time:
                    params['startTime'] = int(start_time.timestamp() * 1000)

                if end_time:
                    params['endTime'] = int(end_time.timestamp() * 1000)

                trades = self.exchange_client.exchange.fapiPrivateGetUserTrades(params)
                return trades

        except Exception as e:
            self.logger.log_event("POSITION_REPORTER", "ERROR", f"❌ Failed to get user trades: {e}")
            return []

    async def get_position_risk(self) -> list[dict[str, Any]]:
        """Получает информацию о риске позиций"""
        try:
            async with self.exchange_client._async_semaphore:
                await self.exchange_client.rate_limiter.acquire(5)

                # Используем fetch_positions вместо fapiPrivateGetPositionRisk
                positions = self.exchange_client.exchange.fetch_positions()
                return [pos for pos in positions if float(pos.get('contracts', 0)) != 0]

        except Exception as e:
            self.logger.log_event("POSITION_REPORTER", "ERROR", f"❌ Failed to get position risk: {e}")
            return []

    async def get_income_history(self, symbol: str | None = None,
                               start_time: datetime | None = None,
                               end_time: datetime | None = None,
                               limit: int = 1000) -> list[dict[str, Any]]:
        """Получает историю доходов (funding fees, etc.)"""
        try:
            async with self.exchange_client._async_semaphore:
                await self.exchange_client.rate_limiter.acquire(5)

                params = {
                    'limit': limit
                }

                if symbol:
                    params['symbol'] = symbol

                if start_time:
                    params['startTime'] = int(start_time.timestamp() * 1000)

                if end_time:
                    params['endTime'] = int(end_time.timestamp() * 1000)

                income = self.exchange_client.exchange.fapiPrivateGetIncome(params)
                return income

        except Exception as e:
            self.logger.log_event("POSITION_REPORTER", "ERROR", f"❌ Failed to get income history: {e}")
            return []

    async def get_account_info(self) -> dict[str, Any] | None:
        """Получает информацию об аккаунте"""
        try:
            async with self.exchange_client._async_semaphore:
                await self.exchange_client.rate_limiter.acquire(5)

                # Используем fetch_balance вместо fapiPrivateGetAccount
                balance = self.exchange_client.exchange.fetch_balance()
                return {
                    'totalWalletBalance': balance.get('total', {}).get('USDT', 0),
                    'totalUnrealizedProfit': 0,  # Будет рассчитано из позиций
                    'availableBalance': balance.get('free', {}).get('USDT', 0)
                }

        except Exception as e:
            self.logger.log_event("POSITION_REPORTER", "ERROR", f"❌ Failed to get account info: {e}")
            return None

    def _group_trades_into_positions(self, trades: list[dict[str, Any]]) -> list[TradePosition]:
        """Группирует сделки в позиции"""
        positions = []
        trade_groups = defaultdict(list)

        # Группируем сделки по symbol и orderId
        for trade in trades:
            symbol = trade['symbol']
            order_id = trade['orderId']
            key = f"{symbol}_{order_id}"
            trade_groups[key].append(trade)

        # Создаем позиции из групп сделок
        for key, trade_group in trade_groups.items():
            if len(trade_group) < 2:  # Нужны минимум 2 сделки (вход и выход)
                continue

            # Сортируем по времени
            trade_group.sort(key=lambda x: x['time'])

            # Первая сделка - вход, последняя - выход
            entry_trade = trade_group[0]
            exit_trade = trade_group[-1]

            # Определяем сторону позиции
            side = 'buy' if entry_trade['side'] == 'BUY' else 'sell'

            # Рассчитываем данные позиции
            entry_price = float(entry_trade['price'])
            exit_price = float(exit_trade['price'])
            quantity = float(entry_trade['qty'])

            entry_time = datetime.fromtimestamp(entry_trade['time'] / 1000)
            exit_time = datetime.fromtimestamp(exit_trade['time'] / 1000)

            entry_fee = float(entry_trade['commission'])
            exit_fee = float(exit_trade['commission'])

            # Рассчитываем PnL
            if side == 'buy':
                realized_pnl = (exit_price - entry_price) * quantity - entry_fee - exit_fee
            else:
                realized_pnl = (entry_price - exit_price) * quantity - entry_fee - exit_fee

            hold_duration = (exit_time - entry_time).total_seconds() / 60

            position = TradePosition(
                symbol=symbol,
                side=side,
                entry_price=entry_price,
                exit_price=exit_price,
                quantity=quantity,
                entry_time=entry_time,
                exit_time=exit_time,
                entry_order_id=entry_trade['orderId'],
                exit_order_id=exit_trade['orderId'],
                entry_fee=entry_fee,
                exit_fee=exit_fee,
                realized_pnl=realized_pnl,
                hold_duration_minutes=hold_duration
            )

            positions.append(position)

        return positions

    def _calculate_position_summary(self, positions: list[TradePosition],
                                  funding_fees: float = 0) -> PositionSummary:
        """Рассчитывает сводку по позициям"""
        if not positions:
            return PositionSummary(
                total_trades=0, winning_trades=0, losing_trades=0,
                total_pnl=0, total_fees=0, win_rate=0,
                avg_profit_per_trade=0, avg_loss_per_trade=0,
                max_profit=0, max_loss=0, avg_hold_duration_minutes=0,
                best_symbol=None, worst_symbol=None,
                symbol_performance={}, funding_fees=funding_fees, net_pnl=0
            )

        # Базовые метрики
        total_trades = len(positions)
        winning_trades = len([p for p in positions if p.realized_pnl > 0])
        losing_trades = len([p for p in positions if p.realized_pnl < 0])

        total_pnl = sum(p.realized_pnl for p in positions)
        total_fees = sum(p.entry_fee + p.exit_fee for p in positions)

        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        # Средние показатели
        profits = [p.realized_pnl for p in positions if p.realized_pnl > 0]
        losses = [p.realized_pnl for p in positions if p.realized_pnl < 0]

        avg_profit_per_trade = statistics.mean(profits) if profits else 0
        avg_loss_per_trade = statistics.mean(losses) if losses else 0

        max_profit = max(p.realized_pnl for p in positions) if positions else 0
        max_loss = min(p.realized_pnl for p in positions) if positions else 0

        avg_hold_duration = statistics.mean(p.hold_duration_minutes for p in positions)

        # Анализ по символам
        symbol_performance = defaultdict(lambda: {
            'trades': 0, 'pnl': 0, 'fees': 0, 'win_rate': 0
        })

        for position in positions:
            symbol = position.symbol
            symbol_performance[symbol]['trades'] += 1
            symbol_performance[symbol]['pnl'] += position.realized_pnl
            symbol_performance[symbol]['fees'] += position.entry_fee + position.exit_fee

        # Рассчитываем win rate для каждого символа
        for symbol in symbol_performance:
            symbol_positions = [p for p in positions if p.symbol == symbol]
            symbol_wins = len([p for p in symbol_positions if p.realized_pnl > 0])
            symbol_performance[symbol]['win_rate'] = symbol_wins / len(symbol_positions)

        # Находим лучший и худший символы
        best_symbol = max(symbol_performance.items(), key=lambda x: x[1]['pnl'])[0] if symbol_performance else None
        worst_symbol = min(symbol_performance.items(), key=lambda x: x[1]['pnl'])[0] if symbol_performance else None

        net_pnl = total_pnl + funding_fees

        return PositionSummary(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            total_pnl=total_pnl,
            total_fees=total_fees,
            win_rate=win_rate,
            avg_profit_per_trade=avg_profit_per_trade,
            avg_loss_per_trade=avg_loss_per_trade,
            max_profit=max_profit,
            max_loss=max_loss,
            avg_hold_duration_minutes=avg_hold_duration,
            best_symbol=best_symbol,
            worst_symbol=worst_symbol,
            symbol_performance=dict(symbol_performance),
            funding_fees=funding_fees,
            net_pnl=net_pnl
        )

    async def generate_position_report(self, hours: int = 24) -> tuple[PositionSummary, list[TradePosition]]:
        """Генерирует полный отчет о позициях"""
        try:
            self.logger.log_event("POSITION_REPORTER", "INFO", f"📊 Generating position report for last {hours} hours...")

            # Определяем временной диапазон
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours)

            # Получаем данные
            trades = await self.get_user_trades(start_time=start_time, end_time=end_time)
            income_history = await self.get_income_history(start_time=start_time, end_time=end_time)

            # Рассчитываем funding fees
            funding_fees = sum(
                float(income['income'])
                for income in income_history
                if income['incomeType'] == 'FUNDING_FEE'
            )

            # Группируем сделки в позиции
            positions = self._group_trades_into_positions(trades)

            # Рассчитываем сводку
            summary = self._calculate_position_summary(positions, funding_fees)

            self.logger.log_event("POSITION_REPORTER", "INFO",
                                f"✅ Position report generated: {summary.total_trades} trades, "
                                f"PnL: ${summary.total_pnl:.2f}, Win Rate: {summary.win_rate:.1%}")

            return summary, positions

        except Exception as e:
            self.logger.log_event("POSITION_REPORTER", "ERROR", f"❌ Failed to generate position report: {e}")
            return self._calculate_position_summary([]), []

    def format_position_report(self, summary: PositionSummary, positions: list[TradePosition]) -> str:
        """Форматирует отчет о позициях в читаемый вид"""
        report = f"""
{'='*80}
📊 ПОЗИЦИОННАЯ СВОДКА (ДЕТАЛЬНЫЙ АНАЛИЗ)
{'='*80}

📈 ОСНОВНЫЕ МЕТРИКИ:
• Общее количество сделок: {summary.total_trades}
• Выигрышных сделок: {summary.winning_trades}
• Проигрышных сделок: {summary.losing_trades}
• Винрейт: {summary.win_rate:.1%}

💰 ФИНАНСОВЫЕ ПОКАЗАТЕЛИ:
• Общий PnL: ${summary.total_pnl:.2f}
• Общие комиссии: ${summary.total_fees:.2f}
• Funding Fees: ${summary.funding_fees:.2f}
• Чистый PnL: ${summary.net_pnl:.2f}

📊 СРЕДНИЕ ПОКАЗАТЕЛИ:
• Средняя прибыль за сделку: ${summary.avg_profit_per_trade:.2f}
• Средний убыток за сделку: ${summary.avg_loss_per_trade:.2f}
• Максимальная прибыль: ${summary.max_profit:.2f}
• Максимальный убыток: ${summary.max_loss:.2f}
• Среднее время удержания: {summary.avg_hold_duration_minutes:.1f} мин

🏆 АНАЛИЗ ПО СИМВОЛАМ:
• Лучший символ: {summary.best_symbol or 'N/A'}
• Худший символ: {summary.worst_symbol or 'N/A'}

📋 ДЕТАЛЬНАЯ СВОДКА ПО СИМВОЛАМ:
"""

        for symbol, perf in summary.symbol_performance.items():
            report += f"• {symbol}: {perf['trades']} сделок, PnL: ${perf['pnl']:.2f}, Win Rate: {perf['win_rate']:.1%}\n"

        if positions:
            report += "\n📝 ПОСЛЕДНИЕ 10 СДЕЛОК:\n"
            for i, pos in enumerate(positions[-10:], 1):
                report += (f"{i}. {pos.symbol} {pos.side.upper()} | "
                          f"Вход: ${pos.entry_price:.4f} | Выход: ${pos.exit_price:.4f} | "
                          f"PnL: ${pos.realized_pnl:.2f} | "
                          f"Время: {pos.hold_duration_minutes:.1f}мин\n")

        report += f"\n{'='*80}"

        return report

    async def cleanup(self):
        """Очистка ресурсов"""
        await self.exchange_client.cleanup()
        self.logger.log_event("POSITION_REPORTER", "INFO", "🧹 Position History Reporter cleanup completed")

    async def _cleanup_old_position_reports(self, days_to_keep: int = 30):
        """Очищает старые position reports, оставляя только последние N дней"""
        try:
            position_reports_dir = Path("data/position_reports")
            if not position_reports_dir.exists():
                return

            # Находим все файлы position reports
            report_files = list(position_reports_dir.glob("position_report_*.txt"))

            # Фильтруем файлы старше N дней
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            files_to_delete = []

            for file_path in report_files:
                try:
                    # Пытаемся извлечь дату из имени файла
                    file_date_str = file_path.stem.split('_')[-1]  # Последняя часть имени
                    if len(file_date_str) >= 8:  # YYYYMMDD
                        file_date = datetime.strptime(file_date_str[:8], "%Y%m%d")
                        if file_date < cutoff_date:
                            files_to_delete.append(file_path)
                except Exception:
                    # Если не удается извлечь дату, проверяем время модификации
                    if file_path.stat().st_mtime < cutoff_date.timestamp():
                        files_to_delete.append(file_path)

            # Удаляем старые файлы
            deleted_count = 0
            for file_path in files_to_delete:
                try:
                    file_path.unlink()
                    deleted_count += 1
                except Exception as e:
                    self.logger.log_event("POSITION_REPORTER", "WARNING",
                        f"Failed to delete old position report {file_path}: {e}")

            if deleted_count > 0:
                self.logger.log_event("POSITION_REPORTER", "INFO",
                    f"Cleaned up {deleted_count} old position report files (older than {days_to_keep} days)")

        except Exception as e:
            self.logger.log_event("POSITION_REPORTER", "ERROR",
                f"Failed to cleanup old position reports: {e}")

    def save_position_report(self, report_content: str, filename: str = None) -> str:
        """Сохраняет position report в файл"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"position_report_real_{timestamp}.txt"

        report_path = Path("data/position_reports") / filename
        report_path.parent.mkdir(exist_ok=True)

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_content)

        # Очищаем старые отчеты (синхронно)
        asyncio.create_task(self._cleanup_old_position_reports())

        return str(report_path)
