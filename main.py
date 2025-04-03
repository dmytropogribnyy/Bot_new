import time
import json
import os
from datetime import datetime
from config import (
    exchange,
    ADAPTIVE_RISK_PERCENT,
    MIN_NOTIONAL,
    SL_PERCENT,
    trade_stats,
    DRY_RUN,
    is_aggressive,
    MAX_HOLD_MINUTES,
    TIMEZONE,
    EXPORT_PATH,
    FIXED_PAIRS,
    VERBOSE,
)
from core.strategy import fetch_data, should_enter_trade
from core.trade_engine import (
    enter_trade,
    calculate_risk_amount,
    calculate_position_size,
    get_position_size,
)
from telegram_handler import send_telegram_message
from utils import log, notify_error, log_dry_entry, now, escape_markdown_v2
from tp_logger import log_trade_result

STATE_FILE = "data/bot_state.json"
SYMBOLS_FILE = "data/dynamic_symbols.json"


def load_symbols():
    if DRY_RUN:
        return FIXED_PAIRS
    if os.path.exists(SYMBOLS_FILE):
        with open(SYMBOLS_FILE, "r") as f:
            return json.load(f)
    from pair_selector import select_active_symbols

    return select_active_symbols()


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {
        "pause": False,
        "stopping": False,
        "shutdown": False,
        "allowed_user_id": 383821734,
    }


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def start_trading_loop():
    state = load_state()

    mode = "DRY_RUN" if DRY_RUN else "REAL_RUN"
    log(f"Starting bot in {mode} mode...", important=True)
    # Construct the full message first, then escape it for MarkdownV2
    message = (
        f"Bot started in {mode} mode\n"
        f"Mode: {'SAFE' if not is_aggressive else 'AGGRESSIVE'}\n"
        f"DRY_RUN: {str(DRY_RUN)}, VERBOSE: {str(VERBOSE)}"
    )
    send_telegram_message(escape_markdown_v2(message), force=True)
    log("Telegram start message sent (or attempted)", important=True)

    symbols = load_symbols()
    log(f"Loaded symbols: {symbols}", important=True)

    last_balance = 0
    position_timestamps = {}
    last_loop_log_time = time.time()

    while True:
        try:
            balance = exchange.fetch_balance()["total"]["USDC"]

            if last_balance == 0:
                trade_stats["initial_balance"] = balance
            elif balance > last_balance + 0.5:
                delta = round(balance - last_balance, 2)
                trade_stats["deposits_today"] += delta
                trade_stats["deposits_week"] += delta
                send_telegram_message(f"Deposit detected: +{delta} USDC")
            elif balance < last_balance - 0.5:
                delta = round(last_balance - balance, 2)
                trade_stats["withdrawals"] += delta
                send_telegram_message(f"Withdrawal detected: -{delta} USDC")

            last_balance = balance

            if state.get("pause") or state.get("stopping"):
                if state.get("stopping"):
                    open_trades = sum(get_position_size(sym) > 0 for sym in symbols)
                    if open_trades == 0:
                        send_telegram_message(
                            "All positions closed. Bot stopped.", force=True
                        )
                        break
                    else:
                        log(f"Waiting for {open_trades} open positions...")
                time.sleep(10)
                continue

            now_time = time.time()
            if DRY_RUN or (now_time - last_loop_log_time > 600):
                log("Starting symbol loop...")
                last_loop_log_time = now_time

            for sym in list(position_timestamps):
                opened_at = position_timestamps[sym]
                mins_open = (now() - opened_at).total_seconds() / 60
                if mins_open > MAX_HOLD_MINUTES:
                    df = fetch_data(sym)
                    price = df["close"].iloc[-1]
                    target = df["close"].max() if df["close"].max() > price else price
                    if target > price * (1 + SL_PERCENT * 0.6):
                        position_timestamps[sym] = now()
                        send_telegram_message(
                            f"Trade on {sym} extended due to near-target move.",
                            force=True,
                        )
                    else:
                        size = get_position_size(sym)
                        if size > 0:
                            side = (
                                "sell"
                                if df["close"].iloc[-1] > df["open"].iloc[-1]
                                else "buy"
                            )
                            exchange.create_market_order(sym, side, size)
                            send_telegram_message(
                                f"Position forcibly closed on {sym} after timeout.",
                                force=True,
                            )
                            log_trade_result(
                                sym,
                                side,
                                df["close"].iloc[-2],
                                price,
                                False,
                                False,
                                False,
                                0,
                                "TIMEOUT",
                                int(mins_open),
                            )
                        del position_timestamps[sym]

            for symbol in symbols:
                if get_position_size(symbol) > 0:
                    continue

                df = fetch_data(symbol)
                result = should_enter_trade(symbol, df)

                if result in ["buy", "sell"]:
                    entry = df["close"].iloc[-1]
                    stop = (
                        entry * (1 - SL_PERCENT)
                        if result == "buy"
                        else entry * (1 + SL_PERCENT)
                    )
                    risk = calculate_risk_amount(balance, ADAPTIVE_RISK_PERCENT)
                    qty = calculate_position_size(entry, stop, risk)

                    if qty * entry >= MIN_NOTIONAL:
                        if DRY_RUN:
                            log(
                                f"[DRY] Entering {result.upper()} on {symbol} at {entry:.5f} (qty: {qty:.2f})"
                            )
                            log_dry_entry(
                                f"{result.upper()} on {symbol} at {entry:.5f} (qty: {qty:.2f})"
                            )
                            send_telegram_message(
                                f"[DRY_RUN] {result.upper()} {symbol}\nPrice: {entry:.5f}\nQty: {qty:.2f}",
                                force=True,
                            )
                        else:
                            enter_trade(symbol, result, qty)
                            position_timestamps[symbol] = now()

            save_state(state)

        except Exception as e:
            notify_error("main_loop", e)

        time.sleep(10)


if __name__ == "__main__":
    try:
        # Start Telegram command polling
        from telegram_handler import process_telegram_commands
        from telegram_commands import handle_telegram_command
        import threading

        state = load_state()
        threading.Thread(
            target=lambda: process_telegram_commands(state, handle_telegram_command),
            daemon=True,
        ).start()

        # Start trading loop
        start_trading_loop()

    except KeyboardInterrupt:
        log("Bot manually stopped via console (Ctrl+C)", important=True)
        send_telegram_message(
            "🛑 *Bot manually stopped via console \\(Ctrl\\+C\\)*",  # Escaped parentheses
            force=True,
        )
