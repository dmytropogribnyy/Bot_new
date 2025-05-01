# test_api.py
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
        "urls": {
            "api": {
                "public": "https://fapi.binance.com/fapi/v1",
                "private": "https://fapi.binance.com/fapi/v1",
            }
        },
    }
)

try:
    markets = exchange.load_markets()
    print(f"Loaded {len(markets)} markets")
    print(f"Sample markets: {list(markets.keys())[:5]}")

    # Проверяем пары с USDC
    usdc_symbols = [
        symbol for symbol in markets.keys() if symbol.endswith("/USDC") or symbol.endswith("USDC")
    ]
    print(f"Found {len(usdc_symbols)} USDC symbols: {usdc_symbols[:5]}...")

    # Проверяем пары с USDT
    usdt_symbols = [
        symbol for symbol in markets.keys() if symbol.endswith("/USDT") or symbol.endswith("USDT")
    ]
    print(f"Found {len(usdt_symbols)} USDT symbols: {usdt_symbols[:5]}...")

    # Выводим типы первых 5 пар
    for symbol in list(markets.keys())[:5]:
        print(
            f"Symbol: {symbol}, Type: {markets[symbol]['type']}, Active: {markets[symbol]['active']}"
        )
except Exception as e:
    print(f"Error: {str(e)}")
