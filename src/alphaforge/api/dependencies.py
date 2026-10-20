"""FastAPI dependency providers."""

from alphaforge.data.engine import MarketDataEngine
from alphaforge.data.providers import YFinanceProvider


def get_market_data_engine() -> MarketDataEngine:
    """Build the default provider-backed engine for one request."""
    return MarketDataEngine(YFinanceProvider())
