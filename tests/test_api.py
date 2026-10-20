import pandas as pd
import pytest
from fastapi.testclient import TestClient

from alphaforge.api.app import app
from alphaforge.api.dependencies import get_market_data_engine
from alphaforge.data.engine import MarketDataEngine


class FakeProvider:
    def __init__(self, history=None, error=None):
        self.history = history
        self.error = error

    def fetch_history(self, tickers, start, end):
        if self.error:
            raise self.error
        return self.history.copy()


def client_for(history=None, error=None):
    app.dependency_overrides[get_market_data_engine] = lambda: MarketDataEngine(
        FakeProvider(history, error)
    )
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def test_health_is_independent_of_market_data_provider():
    response = client_for(error=RuntimeError("provider unavailable")).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("origin", ["http://localhost:3000", "http://127.0.0.1:3000"])
def test_cors_allows_frontend_origins(origin):
    response = client_for().options(
        "/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert "GET" in response.headers["access-control-allow-methods"]
    assert response.headers.get("access-control-allow-credentials") is None


def test_cors_rejects_unconfigured_origin():
    response = client_for().get("/health", headers={"Origin": "http://localhost:4000"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_market_data_serializes_validated_history_and_returns():
    history = pd.DataFrame(
        {
            "date": ["2025-01-02", "2025-01-03"],
            "ticker": ["AAPL", "AAPL"],
            "open": [99, 109],
            "close": [100, 110],
            "adj_close": [100, 110],
        }
    )
    response = client_for(history).post(
        "/market-data/history",
        json={
            "tickers": ["aapl"],
            "start": "2025-01-01",
            "end": "2025-02-01",
            "include_returns": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["data"][1]["returns"] == pytest.approx(0.1)


def test_market_data_provider_failure_and_empty_data_are_explicit():
    assert client_for(error=RuntimeError("network")).post(
        "/market-data/history",
        json={"tickers": ["AAPL"], "start": "2025-01-01", "end": "2025-02-01"},
    ).status_code == 502
    assert client_for(pd.DataFrame()).post(
        "/market-data/history",
        json={"tickers": ["AAPL"], "start": "2025-01-01", "end": "2025-02-01"},
    ).status_code == 404


def test_analytics_reuses_existing_calculations_and_validates_empty_prices():
    response = client_for().post("/analytics", json={"prices": [100, 110, 99]})
    assert response.status_code == 200
    assert response.json()["returns"][1] == pytest.approx(0.1)
    assert response.json()["max_drawdown"] < 0
    assert client_for().post("/analytics", json={"prices": [None, None]}).status_code == 422


def test_portfolio_rejects_invalid_weights_and_returns_risk_metrics():
    payload = {
        "asset_returns": {"A": [0.01, 0.02, -0.01], "B": [0.0, 0.01, 0.02]},
        "weights": {"A": 0.5, "B": 0.5},
    }
    response = client_for().post("/portfolio/analytics", json=payload)
    assert response.status_code == 200
    assert "correlation" in response.json()
    payload["weights"]["B"] = 0.2
    assert client_for().post("/portfolio/analytics", json=payload).status_code == 422


def test_backtest_accepts_inline_history_and_preserves_engine_output_shape():
    history = [
        {"date": "2025-01-02", "ticker": "AAA", "open": 10, "close": 10},
        {"date": "2025-01-03", "ticker": "AAA", "open": 11, "close": 11},
        {"date": "2025-01-04", "ticker": "AAA", "open": 12, "close": 12},
    ]
    response = client_for().post(
        "/backtests/run",
        json={
            "history": history,
            "initial_capital": 1000,
            "strategy": {"short_window": 1, "long_window": 2},
        },
    )
    assert response.status_code == 200
    assert len(response.json()["equity"]) == 3
    assert "max_drawdown" in response.json()["metrics"]


def test_backtest_rejects_invalid_strategy_configuration():
    response = client_for().post(
        "/backtests/run",
        json={
            "history": [
                {"date": "2025-01-02", "ticker": "AAA", "open": 10, "close": 10},
            ],
            "initial_capital": 1000,
            "strategy": {"short_window": 2, "long_window": 1},
        },
    )
    assert response.status_code == 422
