import threading
import time

from core.exchange_init import exchange
from telegram.telegram_utils import send_telegram_message
from utils_logging import log

FUNDING_THRESHOLD = 0.0002  # 0.02%
CHECK_INTERVAL = 300  # seconds
USDC_SYMBOLS = ["ENA/USDC", "WIF/USDC", "TRUMP/USDC", "ORDI/USDC", "PEPE/USDC"]


def run_funding_monitor():
    log("[FundingMonitor] Started monitoring funding rates", level="INFO")
    while True:
        try:
            for symbol in USDC_SYMBOLS:
                try:
                    market = exchange.markets.get(symbol)
                    if not market or not market.get("id"):
                        continue

                    funding_info = exchange.fapiPublic_get_premiumindex({"symbol": market["id"]})
                    if isinstance(funding_info, list):
                        funding_info = funding_info[0]

                    rate = float(funding_info.get("lastFundingRate", 0))

                    if rate > FUNDING_THRESHOLD:
                        msg = f"💸 *Funding Alert:* `{symbol}` has `+{rate*100:.3f}%` funding rate."
                        log(f"[Funding] {symbol} funding = {rate:.4%}", level="INFO")
                        send_telegram_message(msg, force=True)

                except Exception as e:
                    log(f"[FundingMonitor] Error for {symbol}: {e}", level="ERROR")

        except Exception as e:
            log(f"[FundingMonitor] General error: {e}", level="ERROR")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    threading.Thread(target=run_funding_monitor, daemon=True).start()
