from fastapi.testclient import TestClient

from alphaforge.api.app import app


def test_portfolio_optimization_returns_performance_series_for_ui():
    response = TestClient(app).post(
        "/portfolio/analytics",
        json={
            "asset_returns": {
                "A": [0.01, 0.02, -0.01, 0.015],
                "B": [0.0, 0.01, 0.02, 0.005],
            },
            "optimization": "minimum_volatility",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["returns"]) == 4
    assert len(body["cumulative_returns"]) == 4
    assert body["annualized_volatility"] is not None
    assert body["optimization"]["weights"]


def test_api_rejects_oversized_requests_before_work():
    response = TestClient(app).post(
        "/analytics",
        json={"prices": [100] * 100_001},
    )
    assert response.status_code == 422
