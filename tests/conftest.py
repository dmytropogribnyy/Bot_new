import sys
from pathlib import Path

import pytest

# Ensure project root on sys.path for core imports when running from tests dir
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def symbol() -> str:
    """Provide a default symbol for tests expecting a 'symbol' fixture."""
    return "BTC/USDT:USDT"
