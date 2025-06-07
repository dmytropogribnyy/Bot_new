from core.exchange_init import exchange
from telegram.telegram_utils import send_telegram_message
from utils_logging import log

SYMBOL = "TRUMP/USDC"
GRID_LEVELS = 5
GRID_SPREAD = 0.005  # 0.5%
BASE_ORDER_SIZE = 10  # Adjust per pair and balance


def get_grid_prices(base_price, levels, spread):
    return [(base_price * (1 - spread * (i + 1)), base_price * (1 + spread * (i + 1))) for i in range(levels)]


def place_grid_orders(symbol, base_price):
    precision = exchange.markets[symbol]["precision"]["price"]
    qty_precision = exchange.markets[symbol]["precision"]["amount"]

    orders = get_grid_prices(base_price, GRID_LEVELS, GRID_SPREAD)

    for buy_price, sell_price in orders:
        try:
            buy_price = round(buy_price, precision)
            sell_price = round(sell_price, precision)
            qty = round(BASE_ORDER_SIZE, qty_precision)

            exchange.create_limit_buy_order(symbol, qty, buy_price)
            exchange.create_limit_sell_order(symbol, qty, sell_price)

            log(f"[GRID] Set buy {buy_price}, sell {sell_price} on {symbol}", level="INFO")
        except Exception as e:
            log(f"[GRID] Failed to place order on {symbol}: {e}", level="ERROR")


def run_grid_trader():
    try:
        ticker = exchange.fetch_ticker(SYMBOL)
        price = ticker["last"]
        place_grid_orders(SYMBOL, price)
        send_telegram_message(f"📈 Grid strategy initialized for {SYMBOL} around {price:.4f}", force=True)
    except Exception as e:
        log(f"[GRID] Error initializing grid: {e}", level="ERROR")


if __name__ == "__main__":
    run_grid_trader()
