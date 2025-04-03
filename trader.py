import time
from core.strategy import fetch_data, should_enter_trade
from core.trade_engine import enter_trade, calculate_risk_amount, calculate_position_size, get_position_size
from config import (
    exchange, MIN_NOTIONAL, SYMBOLS_ACTIVE, SL_PERCENT,
    trade_stats, DRY_RUN, RISK_DRAWDOWN_THRESHOLD, VOLATILITY_ATR_THRESHOLD
)
from utils import log, notify_error, send_telegram_message, log_dry_entry

def get_adaptive_risk_percent(balance):
    if balance < 100:
        return 0.03
    elif balance < 300:
        return 0.05
    else:
        return 0.07

def start_trading_loop(state):
    last_balance = 0

    while True:
        try:
            balance = exchange.fetch_balance()['total']['USDC']

            if last_balance == 0:
                trade_stats['initial_balance'] = balance
            elif balance > last_balance + 0.5:
                delta = round(balance - last_balance, 2)
                trade_stats['deposits_today'] += delta
                trade_stats['deposits_week'] += delta
                send_telegram_message(f"💰 Deposit detected: +{delta} USDC")

            last_balance = balance

            if state.get('pause') or state.get('stopping'):
                if state.get('stopping'):
                    open_trades = sum(get_position_size(sym) > 0 for sym in SYMBOLS_ACTIVE)
                    if open_trades == 0:
                        send_telegram_message("✅ All positions closed. Bot stopped.", force=True)
                        break
                    else:
                        log(f"⏳ Waiting for {open_trades} open positions...")
                time.sleep(10)
                continue

            log("🔁 Starting symbol loop...")
            for symbol in SYMBOLS_ACTIVE:
                df = fetch_data(symbol)
                result = should_enter_trade(symbol, df)
                if not result:
                    continue
                side, score = result
                if side in ['buy', 'sell']:
                    risk_percent = get_adaptive_risk_percent(balance)

                    # 🛡 Adaptive Risk: при просадке и снижении капитала
                    if trade_stats['pnl'] < -RISK_DRAWDOWN_THRESHOLD:
                        risk_percent *= 0.5
                        log(f"⚠️ Risk lowered due to drawdown: {risk_percent*100:.1f}%")
                    elif balance < trade_stats['initial_balance'] * 0.85:
                        risk_percent *= 0.6
                        log(f"⚠️ Risk lowered due to capital drop: {risk_percent*100:.1f}%")

                    base_risk = risk_percent
                    if score == 3:
                        risk_percent *= 0.7
                        log(f"⚠️ Entry score {score}/4 → reduced risk")
                    elif score == 4:
                        log(f"📈 Entry score {score}/4 → full risk")

                    log(f"🔄 Risk adjusted: base {base_risk*100:.1f}% → effective {risk_percent*100:.1f}% (balance: {balance:.2f} USDC)")

                    risk = calculate_risk_amount(balance, risk_percent)
                    entry = df['close'].iloc[-1]
                    stop = entry * (1 - SL_PERCENT) if side == 'buy' else entry * (1 + SL_PERCENT)
                    qty = calculate_position_size(entry, stop, risk)

                    if qty * entry >= MIN_NOTIONAL:
                        if DRY_RUN:
                            log(f"✅ [DRY] Entering {side.upper()} on {symbol} at {entry:.5f} (qty: {qty:.2f})")
                            log_dry_entry(symbol, side, entry)
                            send_telegram_message(
                                f"📘 [DRY_RUN] {side.upper()} {symbol}\nPrice: {entry:.5f}\nQty: {qty:.2f}\nScore: {score}/4",
                                force=True
                            )
                        else:
                            enter_trade(symbol, side, qty, score)

        except Exception as e:
            notify_error("trader", e)
            trade_stats['api_errors'] += 1
            if trade_stats['api_errors'] >= 5:
                send_telegram_message("⚠️ 5+ API errors — pausing for 5 minutes", force=True)
                time.sleep(300)
                trade_stats['api_errors'] = 0

        time.sleep(10)
