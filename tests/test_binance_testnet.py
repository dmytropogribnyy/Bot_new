import ccxt

api_key = "e5acf38c4584f2aaa4fac8ac2c4f823caed9334881d299b8dea0f5c5c3fa0d7a"
api_secret = "39f31af92b87201f9bb2dea96c75d76ea8298f056d385d8450a3b04738f65546"

# Testnet config
exchange = ccxt.binance(
    {
        "apiKey": api_key,
        "secret": api_secret,
        "options": {
            "defaultType": "future",
        },
    }
)

# Включить testnet
exchange.set_sandbox_mode(True)

try:
    # Проверить баланс
    balance = exchange.fetch_balance()
    print(f"✅ Connected! Balance: {balance['USDT']['free']} USDT")

    # Проверить тикер
    ticker = exchange.fetch_ticker("BTC/USDT")
    print(f"✅ BTC/USDT price: {ticker['last']}")
except Exception as e:
    print(f"❌ Error: {e}")
