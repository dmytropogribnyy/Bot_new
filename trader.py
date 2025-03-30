import ccxt, ta
import pandas as pd
import time
import threading
from datetime import datetime, timedelta
from config import (
    API_KEY, API_SECRET, SYMBOLS_ACTIVE, LEVERAGE_MAP,
    ADAPTIVE_RISK_PERCENT, AGGRESSIVE_THRESHOLD, SAFE_THRESHOLD,
    ENABLE_TRAILING, TRAILING_PERCENT,
    ENABLE_BREAKEVEN, BREAKEVEN_TRIGGER,
    DRY_RUN, MIN_NOTIONAL, TIMEZONE
)
from telegram_handler import send_telegram_message

trade_stats = {
    'total': 0,
    'wins': 0,
    'losses': 0,
    'pnl': 0.0,
    'streak_loss': 0,
    'tp_results': {},
    'best_tp': (0.025, 0.015)
}

is_aggressive = False
pause_trading = False

exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True,
    'options': {'defaultType': 'future'}
})

def record_tp_result(tp, sl, pnl):
    key = (round(tp, 3), round(sl, 3))
    if key not in trade_stats['tp_results']:
        trade_stats['tp_results'][key] = []
    trade_stats['tp_results'][key].append((pnl, datetime.now()))
    trade_stats['pnl'] += pnl

    if pnl > 0:
        trade_stats['wins'] += 1
        trade_stats['streak_loss'] = max(trade_stats['streak_loss'] - 1, -5)
    else:
        trade_stats['losses'] += 1
        trade_stats['streak_loss'] = min(trade_stats['streak_loss'] + 1, 5)

    check_adaptive_mode()

def check_adaptive_mode():
    global is_aggressive
    if not is_aggressive:
        if trade_stats['streak_loss'] <= -3 or trade_stats['pnl'] >= AGGRESSIVE_THRESHOLD:
            trade_stats['best_tp'] = (0.04, 0.02)
            is_aggressive = True
            send_telegram_message("⚡ Switched to AGGRESSIVE mode", force=True)
    else:
        if trade_stats['streak_loss'] >= 2 or trade_stats['pnl'] <= SAFE_THRESHOLD:
            trade_stats['best_tp'] = (0.025, 0.015)
            is_aggressive = False
            send_telegram_message("🔁 Reverted to SAFE mode", force=True)

def fetch_data(symbol, tf='15m'):
    df = pd.DataFrame(exchange.fetch_ohlcv(symbol, timeframe=tf, limit=50),
                      columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    df['rsi'] = ta.momentum.rsi(df['close'], window=14)
    df['ema'] = ta.trend.ema_indicator(df['close'], window=20)
    df['macd'] = ta.trend.macd(df['close'])
    df['macd_signal'] = ta.trend.macd_signal(df['close'])
    df['atr'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=14)
    df['fast_ema'] = ta.trend.ema_indicator(df['close'], window=9)
    df['slow_ema'] = ta.trend.ema_indicator(df['close'], window=21)
    df['adx'] = ta.trend.adx(df['high'], df['low'], df['close'], window=14)
    bb = ta.volatility.BollingerBands(df['close'], window=20)
    df['bb_width'] = bb.bollinger_hband() - bb.bollinger_lband()
    return df

def confirm_trend(symbol):
    df_1h = fetch_data(symbol, tf='1h')
    return df_1h['close'].iloc[-1] > df_1h['ema'].iloc[-1]

def should_enter_trade(symbol, df):
    rsi = df['rsi'].iloc[-1]
    ema = df['ema'].iloc[-1]
    macd = df['macd'].iloc[-1]
    macd_signal = df['macd_signal'].iloc[-1]
    atr = df['atr'].iloc[-1]
    adx_val = df['adx'].iloc[-1]
    bb_width = df['bb_width'].iloc[-1]
    price = df['close'].iloc[-1]

    if atr / price < 0.005 or adx_val < 20 or bb_width / price < 0.01:
        return None

    trend_up = confirm_trend(symbol)
    if rsi < 30 and macd > macd_signal and price > ema and trend_up:
        return 'buy'
    elif rsi > 70 and macd < macd_signal and price < ema and not trend_up:
        return 'sell'
    return None

def calculate_risk_amount(balance, risk_percent):
    return balance * risk_percent

def calculate_position_size(entry_price, stop_price, risk_amount):
    risk_per_unit = abs(entry_price - stop_price)
    if risk_per_unit == 0:
        return 0
    return round(risk_amount / risk_per_unit, 2)

def place_market_order(symbol, side, qty):
    if not DRY_RUN:
        if side == 'buy':
            exchange.create_market_buy_order(symbol, qty)
        else:
            exchange.create_market_sell_order(symbol, qty)
    else:
        print(f"[DRY RUN] Simulated {side.upper()} order: {symbol}, size: {qty}")
        send_telegram_message(f"[DRY RUN] Simulated {side.upper()} order: {symbol}, size: {qty}", force=True)

def get_position_size(symbol):
    try:
        positions = exchange.fetch_positions()
        for pos in positions:
            if pos['symbol'] == symbol and float(pos['contracts']) > 0:
                return float(pos['contracts'])
    except:
        pass
    return 0

def get_open_positions():
    try:
        positions = exchange.fetch_positions()
        open_positions = []
        for pos in positions:
            if float(pos['contracts']) > 0:
                open_positions.append({
                    'symbol': pos['symbol'],
                    'side': 'LONG' if float(pos['contracts']) > 0 and float(pos['entryPrice']) > 0 else 'SHORT',
                    'size': round(float(pos['contracts']), 2),
                    'entry_price': round(float(pos['entryPrice']), 4)
                })
        return open_positions
    except Exception as e:
        print(f"[ERROR] Failed to fetch open positions: {e}")
        return []

def enter_trade(symbol, side, qty):
    place_market_order(symbol, side, qty)
    entry_price = exchange.fetch_ticker(symbol)['last']

    if ENABLE_TRAILING:
        threading.Thread(
            target=run_trailing_stop,
            args=(symbol, side, entry_price, TRAILING_PERCENT),
            daemon=True
        ).start()

    if ENABLE_BREAKEVEN:
        threading.Thread(
            target=run_break_even,
            args=(symbol, side, entry_price, trade_stats['best_tp'][0]),
            daemon=True
        ).start()

    send_telegram_message(f"✅ Entered {side.upper()} on {symbol} @ {entry_price}", force=True)

def run_trailing_stop(symbol, side, entry_price, trailing_percent, check_interval=5):
    highest = entry_price
    lowest = entry_price
    while True:
        try:
            price = exchange.fetch_ticker(symbol)['last']
            if side == 'buy':
                if price > highest:
                    highest = price
                if price <= highest * (1 - trailing_percent):
                    send_telegram_message(f"📉 Trailing Stop Hit (LONG) on {symbol} @ {price}", force=True)
                    if not DRY_RUN:
                        exchange.create_market_sell_order(symbol, get_position_size(symbol))
                    break
            else:
                if price < lowest:
                    lowest = price
                if price >= lowest * (1 + trailing_percent):
                    send_telegram_message(f"📈 Trailing Stop Hit (SHORT) on {symbol} @ {price}", force=True)
                    if not DRY_RUN:
                        exchange.create_market_buy_order(symbol, get_position_size(symbol))
                    break
            time.sleep(check_interval)
        except Exception as e:
            print(f"[ERROR] Trailing stop error for {symbol}: {e}")
            break

def run_break_even(symbol, side, entry_price, tp_percent, check_interval=5):
    target = entry_price * (1 + tp_percent) if side == 'buy' else entry_price * (1 - tp_percent)
    trigger = entry_price + (target - entry_price) * BREAKEVEN_TRIGGER if side == 'buy' else entry_price - (entry_price - target) * BREAKEVEN_TRIGGER

    while True:
        try:
            price = exchange.fetch_ticker(symbol)['last']
            if (side == 'buy' and price >= trigger) or (side == 'sell' and price <= trigger):
                send_telegram_message(f"🔒 Break-even triggered for {symbol}", force=True)
                if not DRY_RUN:
                    stop_price = round(entry_price, 4)
                    exchange.create_order(symbol, 'STOP_MARKET', 'sell' if side == 'buy' else 'buy', get_position_size(symbol), None, {
                        'stopPrice': stop_price,
                        'reduceOnly': True
                    })
                break
            time.sleep(check_interval)
        except Exception as e:
            print(f"[ERROR] Break-even error for {symbol}: {e}")
            break

def run_trading():
    while True:
        if pause_trading:
            time.sleep(5)
            continue

        for symbol in SYMBOLS_ACTIVE:
            try:
                df = fetch_data(symbol)
                signal = should_enter_trade(symbol, df)
                if signal in ['buy', 'sell']:
                    balance = exchange.fetch_balance()['total']['USDC']
                    risk = calculate_risk_amount(balance, ADAPTIVE_RISK_PERCENT)
                    entry = df['close'].iloc[-1]
                    stop = entry * 0.99 if signal == 'buy' else entry * 1.01
                    qty = calculate_position_size(entry, stop, risk)
                    if qty >= MIN_NOTIONAL:
                        enter_trade(symbol, signal, qty)
            except Exception as e:
                print(f"[ERROR] {symbol}: {e}")

        time.sleep(10)
