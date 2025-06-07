import threading
import time

from core.exchange_init import exchange
from core.trade_engine import trade_manager
from telegram.telegram_utils import send_telegram_message
from utils_logging import log

CHECK_INTERVAL = 15
REENTRY_DELTA = 0.001  # Entry +-0.1%


def run_tp1_sniping():
    log("[Sniper] Started TP1 re-entry watcher", level="INFO")
    while True:
        try:
            trades = trade_manager._trades.copy()
            for symbol, trade in trades.items():
                if trade.get("tp1_hit") and not trade.get("tp2_hit") and not trade.get("sniping_started"):
                    entry_price = trade["entry"]
                    side = trade["side"]
                    qty = trade["qty"] * 0.5  # re-enter with 50%

                    try:
                        ticker = exchange.fetch_ticker(symbol)
                        current_price = ticker["last"]
                        diff = abs(current_price - entry_price) / entry_price

                        if diff < REENTRY_DELTA:
                            order_side = "buy" if side.lower() == "buy" else "sell"
                            exchange.create_market_order(symbol, order_side, qty)
                            trade_manager.update_trade(symbol, "sniping_started", True)
                            send_telegram_message(f"🔄 TP1 Sniper Re-entry: {symbol} at {current_price:.4f}")
                            log(f"[Sniper] Re-entry for {symbol} at {current_price:.4f}", level="INFO")

                    except Exception as e:
                        log(f"[Sniper] Error for {symbol}: {e}", level="ERROR")

            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            log(f"[Sniper] Global error: {e}", level="ERROR")
            time.sleep(10)


if __name__ == "__main__":
    threading.Thread(target=run_tp1_sniping, daemon=True).start()
