import math
import sys
from pathlib import Path

import pytest

# Ensure project root is on sys.path for direct 'core.*' imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.precision import normalize, PrecisionError, round_to_step, extract_binance_filters, fallback_from_precision


@pytest.fixture()
def market_stub():
    return {
        "precision": {"price": 4, "amount": 3},
        "limits": {"cost": {"min": 5}},
        "info": {
            "filters": [
                {
                    "filterType": "PRICE_FILTER",
                    "tickSize": "0.0001",
                    "minPrice": "0.0001",
                    "maxPrice": "100000",
                },
                {
                    "filterType": "LOT_SIZE",
                    "stepSize": "0.001",
                    "minQty": "0.001",
                    "maxQty": "100000",
                },
                {"filterType": "MIN_NOTIONAL", "notional": "5"},
            ]
        },
    }


def test_extract_filters_and_fallback(market_stub):
    f = extract_binance_filters(market_stub)
    assert f["tick"] == pytest.approx(0.0001)
    assert f["step"] == pytest.approx(0.001)
    assert f["minNotional"] == pytest.approx(5)

    # If filters missing, fallback to precision digits
    ms = {"precision": {"price": 2, "amount": 1}, "info": {"filters": []}}
    f2 = extract_binance_filters(ms)
    assert f2["tick"] is None and f2["step"] is None
    fb_tick, fb_step = fallback_from_precision(ms)
    assert fb_tick == pytest.approx(10**-2)
    assert fb_step == pytest.approx(10**-1)


def test_success_normalization_passes_filters(market_stub):
    price = 100.12345  # will normalize to 100.1234
    qty = 0.12345  # will normalize to 0.123
    price_n, qty_n, min_notional = normalize(price, qty, market_stub)
    assert price_n == pytest.approx(100.1234)
    assert qty_n == pytest.approx(0.123)
    assert min_notional == pytest.approx(5)
    assert price_n * qty_n >= 5


def test_fail_min_notional(market_stub):
    # Notional will be < 5
    price = 10.0
    qty = 0.01
    with pytest.raises(PrecisionError) as ei:
        normalize(price, qty, market_stub)
    assert "MIN_NOTIONAL" in str(ei.value)


def test_market_order_requires_current_price(market_stub):
    with pytest.raises(PrecisionError) as ei:
        normalize(None, 1.0, market_stub, current_price=None)
    assert "current_price required for market order" in str(ei.value)


def test_fail_min_qty_and_min_price(market_stub):
    # Below min price after normalization
    with pytest.raises(PrecisionError) as ei1:
        normalize(0.00005, 0.01, market_stub)
    assert "price below minPrice" in str(ei1.value)

    # Below min qty after normalization
    with pytest.raises(PrecisionError) as ei2:
        normalize(1.0, 0.0005, market_stub)
    assert "qty below minQty" in str(ei2.value)


def test_round_to_step_basic():
    assert round_to_step(1.2374, 0.001) == pytest.approx(1.237)
    assert round_to_step(5.0, 0.5) == pytest.approx(5.0)
