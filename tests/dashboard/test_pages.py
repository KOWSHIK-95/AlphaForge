import pytest

from dashboard.api_client import AlphaForgeApiClient, ApiResult, MarketDataResult
from dashboard.pages.backtesting import render_backtesting
from dashboard.pages.market_data import render_market_data
from dashboard.pages.portfolio_analysis import _validate_weights, prepare_asset_returns
from dashboard.pages.portfolio_analysis import render_portfolio_analysis
from dashboard.pages.system_status import render_system_status


def test_dashboard_page_imports_and_client_exports_are_available():
    assert MarketDataResult.__name__ == "MarketDataResult"
    assert ApiResult.__name__ == "ApiResult"
    assert callable(AlphaForgeApiClient.health)
    assert callable(AlphaForgeApiClient.market_data_history)
    assert callable(AlphaForgeApiClient.portfolio_analytics)
    assert callable(AlphaForgeApiClient.run_backtest)
    assert callable(render_market_data)
    assert callable(render_backtesting)
    assert callable(render_portfolio_analysis)
    assert callable(render_system_status)


def test_prepare_asset_returns_aligns_prices_and_reports_incomplete_rows():
    returns, dropped = prepare_asset_returns(
        [
            {"date": "2025-01-01", "ticker": "AAPL", "close": 100},
            {"date": "2025-01-01", "ticker": "MSFT", "close": 200},
            {"date": "2025-01-02", "ticker": "AAPL", "close": 110},
            {"date": "2025-01-03", "ticker": "AAPL", "close": 121},
            {"date": "2025-01-03", "ticker": "MSFT", "close": 220},
            {"date": "2025-01-04", "ticker": "AAPL", "close": 133.1},
            {"date": "2025-01-04", "ticker": "MSFT", "close": 242},
        ],
        ["AAPL", "MSFT"],
    )
    assert dropped == 3
    assert returns["AAPL"] == pytest.approx([0.1])
    assert returns["MSFT"] == pytest.approx([0.1])


def test_prepare_asset_returns_rejects_empty_aligned_data():
    with pytest.raises(ValueError, match="not enough"):
        prepare_asset_returns(
            [{"date": "2025-01-01", "ticker": "AAPL", "close": 100}],
            ["AAPL"],
        )


def test_validate_weights_requires_matching_long_only_weights():
    assert _validate_weights(["AAPL", "MSFT"], {"AAPL": 1.0}) is not None
    assert _validate_weights(["AAPL"], {"AAPL": -0.1}) is not None
    assert _validate_weights(["AAPL"], {"AAPL": 0.5}) is not None
    assert _validate_weights(["AAPL"], {"AAPL": 1.0}) is None
