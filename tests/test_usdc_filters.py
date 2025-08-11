import pytest

from core.config import TradingConfig
from core.exchange_client import OptimizedExchangeClient


class FakeLogger:
    def log_event(self, *_args, **_kwargs):
        pass


@pytest.mark.asyncio
async def test_get_usdc_futures_symbols_filters_by_usdc_and_contract():
    config = TradingConfig()
    logger = FakeLogger()
    client = OptimizedExchangeClient(config, logger)

    fake_markets = {
        # valid USDC perpetual
        "BTC/USDC:USDC": {
            "symbol": "BTC/USDC:USDC",
            "type": "swap",
            "quote": "USDC",
            "settle": "USDC",
            "contract": True,
            "active": True,
        },
        # valid, market.type None but contract+settle USDC
        "ETH/USDC:USDC": {
            "symbol": "ETH/USDC:USDC",
            "type": None,
            "quote": "USDC",
            "settle": "USDC",
            "contract": True,
            "active": True,
        },
        # invalid: USDT quote
        "BNB/USDT:USDT": {
            "symbol": "BNB/USDT:USDT",
            "type": "swap",
            "quote": "USDT",
            "settle": "USDT",
            "contract": True,
            "active": True,
        },
        # invalid: not a contract
        "ADA/USDC": {
            "symbol": "ADA/USDC",
            "type": "spot",
            "quote": "USDC",
            "settle": None,
            "contract": False,
            "active": True,
        },
    }

    # monkeypatch get_markets to avoid network
    async def fake_get_markets():
        return fake_markets

    client.get_markets = fake_get_markets  # type: ignore

    symbols = await client.get_usdc_futures_symbols()
    assert "BTC/USDC:USDC" in symbols
    assert "ETH/USDC:USDC" in symbols
    assert "BNB/USDT:USDT" not in symbols
    assert "ADA/USDC" not in symbols


@pytest.mark.asyncio
async def test_symbol_manager_uses_usdc_contracts_only():
    from core.symbol_manager import SymbolManager

    config = TradingConfig()
    # Explicitly test PRODUCTION branch (USDC perpetuals)
    config.testnet = False

    logger = FakeLogger()
    client = OptimizedExchangeClient(config, logger)
    client.is_initialized = True

    fake_markets = {
        "BTC/USDC:USDC": {
            "symbol": "BTC/USDC:USDC",
            "type": "swap",
            "quote": "USDC",
            "settle": "USDC",
            "contract": True,
            "active": True,
        },
        "SOL/USDT:USDT": {
            "symbol": "SOL/USDT:USDT",
            "type": "swap",
            "quote": "USDT",
            "settle": "USDT",
            "contract": True,
            "active": True,
        },
    }

    async def fake_get_markets():
        return fake_markets

    client.get_markets = fake_get_markets  # type: ignore

    sm = SymbolManager(config, client, logger)  # type: ignore
    symbols = await sm.get_available_symbols()
    assert symbols and all(s.endswith(":USDC") for s in symbols)
