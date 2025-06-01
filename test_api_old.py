import json
from pathlib import Path
from time import sleep

import ccxt

API_KEY = "w2LwaYZq0x1t50ARb3IP69y9XQLssukr78dSnFcQF9XfbngkELA8hprvtTPAhX5S"
API_SECRET = "hmG7FVUeyQ8wK09596iDJE8ipQqWvpdlRZ8obwAnCwOa8qlZyHyO9fTvr6oQvMFD"

exchange = ccxt.binance(
    {
        "apiKey": API_KEY,
        "secret": API_SECRET,
        "enableRateLimit": True,
        "options": {
            "defaultType": "future",
            "adjustForTimeDifference": True,
        },
    }
)


def test_fetch_ohlcv(symbol, tf="3m", limit=300):
    """
    Пытается получить OHLCV-данные для символа на указанном таймфрейме.
    Возвращает количество свечей (int) или 0 при ошибке.
    """
    try:
        candles = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=limit)
        return len(candles)
    except Exception as e:
        print(f"   ❌ {symbol} [{tf}] — error: {str(e)}")
        return 0


def main():
    # Загружаем список рынков
    markets = exchange.load_markets()
    print(f"\n✅ Loaded {len(markets)} markets total on Binance Futures (USDC)\n")

    # Фильтруем только USDC-фьючерсы
    usdc_symbols = [
        s
        for s in markets
        if "USDC" in s and "/USDC" in s and markets[s].get("contract")  # Это признак фьючерсного рынка
    ]
    print(f"🧩 Found {len(usdc_symbols)} USDC futures symbols (raw)\n")

    valid_symbols = []

    total_usdc = len(usdc_symbols)
    for i, symbol in enumerate(usdc_symbols, start=1):
        print(f"[{i}/{total_usdc}] Checking {symbol} ...", end="")
        count_3m = test_fetch_ohlcv(symbol, tf="3m")
        count_5m = test_fetch_ohlcv(symbol, tf="5m")
        count_15m = test_fetch_ohlcv(symbol, tf="15m")

        # Критерий достаточности данных — минимум 30 свечей
        if min(count_3m, count_5m, count_15m) >= 30:
            print(f"   ✅ OK (3m={count_3m}, 5m={count_5m}, 15m={count_15m})")
            valid_symbols.append(symbol)
        else:
            print(f"   ⚠️ INSUFFICIENT DATA (3m={count_3m}, 5m={count_5m}, 15m={count_15m})")

        # Небольшая пауза, чтобы не упереться в rate limit
        sleep(0.5)

    # === Сохраняем результаты в файл ===
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    path = data_dir / "valid_usdc_symbols.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(valid_symbols, f, indent=2)

    # === Финальная сводка ===
    total = len(usdc_symbols)
    valid = len(valid_symbols)
    skipped = total - valid

    print(f"\n🎯 Проверено: {total} USDC-пар")
    print(f"   ✔ Валидных: {valid}")
    print(f"   ✖ Пропущено: {skipped}")
    print(f"📁 Список валидных символов сохранён в: {path.resolve()}\n")


if __name__ == "__main__":
    main()
