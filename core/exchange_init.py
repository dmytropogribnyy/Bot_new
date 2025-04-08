# core/exchange_init.py

import ccxt

from config import API_KEY, API_SECRET

exchange = ccxt.binanceusdm(
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
