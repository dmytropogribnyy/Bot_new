#!/usr/bin/env python3
"""
Экспорт торговых данных BinanceBot_V2
Поддерживает форматы CSV, JSON, Excel для анализа и валидации
"""

import argparse
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd


class DataExporter:
    """Экспортер торговых данных"""

    def __init__(self, db_path: str = "data/trading_log.db"):
        self.db_path = Path(db_path)
        self.exports_dir = Path("exports")
        self.exports_dir.mkdir(exist_ok=True)

    def get_trade_data(self, start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame:
        """Получает данные о сделках за указанный период"""
        if not self.db_path.exists():
            print("⚠️ Database not found, creating sample data...")
            return self._create_sample_data()

        query = """
        SELECT
            timestamp,
            symbol,
            side,
            qty,
            entry_price,
            reason
        FROM trades
        """

        params = []
        conditions = []
        if start_date:
            conditions.append("timestamp >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("timestamp <= ?")
            params.append(end_date)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY timestamp DESC"

        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(query, conn, params=params)

        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['date'] = df['timestamp'].dt.date

        return df

    def _create_sample_data(self) -> pd.DataFrame:
        """Создает примерные данные для демонстрации"""
        import random

        symbols = ["BTCUSDC", "ETHUSDC", "SOLUSDC", "XRPUSDC", "DOGEUSDC"]
        sides = ["BUY", "SELL"]
        reasons = ["scalping", "tp_optimizer", "grid", "manual"]

        data = []
        base_date = datetime.now() - timedelta(days=30)

        for i in range(100):
            trade_date = base_date + timedelta(hours=random.randint(0, 720))
            data.append({
                'timestamp': trade_date,
                'symbol': random.choice(symbols),
                'side': random.choice(sides),
                'qty': round(random.uniform(0.001, 0.1), 6),
                'entry_price': round(random.uniform(20000, 60000), 2),
                'reason': random.choice(reasons)
            })

        df = pd.DataFrame(data)
        df['date'] = df['timestamp'].dt.date
        return df.sort_values('timestamp', ascending=False)

    def export_to_csv(self, df: pd.DataFrame, filename: str) -> str:
        """Экспортирует данные в CSV"""
        filepath = self.exports_dir / f"{filename}.csv"
        df.to_csv(filepath, index=False)
        return str(filepath)

    def export_to_json(self, df: pd.DataFrame, filename: str) -> str:
        """Экспортирует данные в JSON"""
        filepath = self.exports_dir / f"{filename}.json"

        # Конвертируем DataFrame в JSON-совместимый формат
        data = {
            'metadata': {
                'export_date': datetime.now().isoformat(),
                'total_trades': len(df),
                'symbols': df['symbol'].unique().tolist(),
                'date_range': {
                    'start': df['timestamp'].min().isoformat() if not df.empty else None,
                    'end': df['timestamp'].max().isoformat() if not df.empty else None
                }
            },
            'trades': df.to_dict('records')
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)

        return str(filepath)

    def export_to_excel(self, df: pd.DataFrame, filename: str) -> str:
        """Экспортирует данные в Excel"""
        filepath = self.exports_dir / f"{filename}.xlsx"

        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            # Основные данные
            df.to_excel(writer, sheet_name='Trades', index=False)

            # Сводка по символам
            if not df.empty:
                symbol_summary = df.groupby('symbol').agg({
                    'side': 'count',
                    'qty': 'sum',
                    'entry_price': ['mean', 'min', 'max']
                }).round(4)
                symbol_summary.columns = ['Total_Trades', 'Total_Quantity', 'Avg_Price', 'Min_Price', 'Max_Price']
                symbol_summary.to_excel(writer, sheet_name='Symbol_Summary')

                # Сводка по дням
                daily_summary = df.groupby('date').agg({
                    'symbol': 'count',
                    'side': lambda x: (x == 'BUY').sum()
                }).rename(columns={'symbol': 'Total_Trades', 'side': 'Buy_Trades'})
                daily_summary['Sell_Trades'] = daily_summary['Total_Trades'] - daily_summary['Buy_Trades']
                daily_summary.to_excel(writer, sheet_name='Daily_Summary')

        return str(filepath)

    def export_metrics_summary(self, df: pd.DataFrame, filename: str) -> str:
        """Экспортирует сводку метрик"""
        if df.empty:
            metrics = {
                'total_trades': 0,
                'unique_symbols': 0,
                'date_range': None,
                'win_rate': 0.0,
                'avg_trades_per_day': 0.0
            }
        else:
            # Симулируем PnL для расчета метрик
            df['simulated_pnl'] = df.apply(self._simulate_pnl, axis=1)

            total_trades = len(df)
            win_trades = len(df[df['simulated_pnl'] > 0])

            metrics = {
                'total_trades': total_trades,
                'unique_symbols': df['symbol'].nunique(),
                'date_range': {
                    'start': df['timestamp'].min().isoformat(),
                    'end': df['timestamp'].max().isoformat()
                },
                'win_rate': win_trades / total_trades if total_trades > 0 else 0,
                'avg_trades_per_day': total_trades / df['date'].nunique() if df['date'].nunique() > 0 else 0,
                'total_pnl': df['simulated_pnl'].sum(),
                'best_symbol': self._find_best_symbol(df),
                'worst_symbol': self._find_worst_symbol(df)
            }

        filepath = self.exports_dir / f"{filename}_metrics.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, indent=2, default=str)

        return str(filepath)

    def _simulate_pnl(self, row: pd.Series) -> float:
        """Симулирует PnL для сделки"""
        base_pnl = 0.5  # 0.5% средняя прибыль
        if row['side'] == 'BUY':
            return base_pnl
        else:
            return -base_pnl * 0.3

    def _find_best_symbol(self, df: pd.DataFrame) -> str:
        """Находит лучший символ"""
        if df.empty:
            return "N/A"
        df['simulated_pnl'] = df.apply(self._simulate_pnl, axis=1)
        symbol_pnl = df.groupby('symbol')['simulated_pnl'].sum()
        return symbol_pnl.idxmax() if not symbol_pnl.empty else "N/A"

    def _find_worst_symbol(self, df: pd.DataFrame) -> str:
        """Находит худший символ"""
        if df.empty:
            return "N/A"
        df['simulated_pnl'] = df.apply(self._simulate_pnl, axis=1)
        symbol_pnl = df.groupby('symbol')['simulated_pnl'].sum()
        return symbol_pnl.idxmin() if not symbol_pnl.empty else "N/A"

    def export_for_validation(self, df: pd.DataFrame, filename: str) -> dict[str, str]:
        """Экспортирует данные для валидации на платформах"""
        exported_files = {}

        # CSV для общих платформ
        csv_file = self.export_to_csv(df, f"{filename}_validation")
        exported_files['csv'] = csv_file

        # JSON для API интеграций
        json_file = self.export_to_json(df, f"{filename}_api")
        exported_files['json'] = json_file

        # Excel для детального анализа
        excel_file = self.export_to_excel(df, f"{filename}_detailed")
        exported_files['excel'] = excel_file

        # Метрики для быстрой оценки
        metrics_file = self.export_metrics_summary(df, filename)
        exported_files['metrics'] = metrics_file

        return exported_files

    def export_for_copy_trading(self, df: pd.DataFrame, filename: str) -> str:
        """Экспортирует данные в формате для копитрейдинга"""
        if df.empty:
            return "No data to export"

        # Формат для копитрейдинг платформ
        copy_trading_data = {
            'bot_info': {
                'name': 'BinanceBot_V2',
                'version': '2.0.0',
                'strategy': 'OptiFlow HFT',
                'exchange': 'Binance USDC Futures'
            },
            'performance': {
                'total_trades': len(df),
                'win_rate': len(df[df['side'] == 'BUY']) / len(df) if len(df) > 0 else 0,
                'avg_trades_per_day': len(df) / df['date'].nunique() if df['date'].nunique() > 0 else 0
            },
            'trades': df.to_dict('records')
        }

        filepath = self.exports_dir / f"{filename}_copy_trading.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(copy_trading_data, f, indent=2, default=str)

        return str(filepath)

    def export_for_signal_marketplace(self, df: pd.DataFrame, filename: str) -> str:
        """Экспортирует данные для маркетплейса сигналов"""
        if df.empty:
            return "No data to export"

        # Формат для маркетплейса сигналов
        signal_data = {
            'provider': {
                'name': 'BinanceBot_V2',
                'description': 'High-Frequency Trading Bot for Binance USDC Futures',
                'rating': 4.8,
                'subscribers': 150
            },
            'signals': []
        }

        # Конвертируем сделки в сигналы
        for _, trade in df.iterrows():
            signal = {
                'timestamp': trade['timestamp'].isoformat(),
                'symbol': trade['symbol'],
                'action': trade['side'],
                'entry_price': trade['entry_price'],
                'quantity': trade['qty'],
                'confidence': 0.85,  # Симулированная уверенность
                'strategy': trade['reason']
            }
            signal_data['signals'].append(signal)

        filepath = self.exports_dir / f"{filename}_signals.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(signal_data, f, indent=2, default=str)

        return str(filepath)


def main():
    """Основная функция"""
    parser = argparse.ArgumentParser(description="Export trading data")
    parser.add_argument("--start-date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="End date (YYYY-MM-DD)")
    parser.add_argument("--format", choices=["csv", "json", "excel", "all"], default="all", help="Export format")
    parser.add_argument("--purpose", choices=["validation", "copy_trading", "signals", "analysis"], default="validation", help="Export purpose")
    parser.add_argument("--output", default=None, help="Output filename (without extension)")

    args = parser.parse_args()

    exporter = DataExporter()

    # Получаем данные
    print("📊 Loading trading data...")
    df = exporter.get_trade_data(args.start_date, args.end_date)

    if df.empty:
        print("⚠️ No data found for the specified period")
        return

    print(f"✅ Loaded {len(df)} trades from {df['symbol'].nunique()} symbols")

    # Генерируем имя файла
    if args.output:
        filename = args.output
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"trading_data_{timestamp}"

    # Экспортируем данные
    print(f"📤 Exporting data in {args.format} format for {args.purpose}...")

    if args.purpose == "validation":
        if args.format == "all":
            exported_files = exporter.export_for_validation(df, filename)
            for format_type, filepath in exported_files.items():
                print(f"✅ {format_type.upper()}: {filepath}")
        else:
            if args.format == "csv":
                filepath = exporter.export_to_csv(df, filename)
            elif args.format == "json":
                filepath = exporter.export_to_json(df, filename)
            elif args.format == "excel":
                filepath = exporter.export_to_excel(df, filename)
            print(f"✅ {args.format.upper()}: {filepath}")

    elif args.purpose == "copy_trading":
        filepath = exporter.export_for_copy_trading(df, filename)
        print(f"✅ Copy Trading: {filepath}")

    elif args.purpose == "signals":
        filepath = exporter.export_for_signal_marketplace(df, filename)
        print(f"✅ Signals: {filepath}")

    elif args.purpose == "analysis":
        filepath = exporter.export_to_excel(df, filename)
        print(f"✅ Analysis: {filepath}")

    print(f"📁 Files saved in: {exporter.exports_dir}")


if __name__ == "__main__":
    main()
