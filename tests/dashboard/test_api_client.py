import httpx
import pytest
from datetime import date
import json

from dashboard.api_client import AlphaForgeApiClient


def make_client(handler, *, timeout=1.0):
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(base_url="http://testserver", transport=transport)
    return AlphaForgeApiClient(timeout=timeout, client=http_client), http_client


def test_health_reports_successful_api_response():
    def handler(request):
        assert request.method == "GET"
        assert request.url.path == "/health"
        return httpx.Response(200, json={"status": "ok"})

    client, http_client = make_client(handler)
    try:
        result = client.health()
    finally:
        http_client.close()

    assert result.reachable is True
    assert result.status == "ok"
    assert result.message == "AlphaForge API is reachable."


def test_health_reports_unsuccessful_http_response():
    client, http_client = make_client(
        lambda request: httpx.Response(503, json={"detail": "unavailable"})
    )
    try:
        result = client.health()
    finally:
        http_client.close()

    assert result.reachable is False
    assert result.status is None
    assert result.message == "AlphaForge API returned HTTP 503."


def test_health_reports_connection_error():
    def handler(request):
        raise httpx.ConnectError("connection refused", request=request)

    client, http_client = make_client(handler)
    try:
        result = client.health()
    finally:
        http_client.close()

    assert result.reachable is False
    assert result.message == "AlphaForge API is unavailable. Check that the API is running."


def test_health_reports_invalid_success_payload():
    client, http_client = make_client(
        lambda request: httpx.Response(200, json={"status": "degraded"})
    )
    try:
        result = client.health()
    finally:
        http_client.close()

    assert result.reachable is False
    assert result.message == "AlphaForge API returned an unexpected health response."


def test_client_rejects_non_positive_timeout():
    with pytest.raises(ValueError, match="timeout"):
        AlphaForgeApiClient(timeout=0)


def test_market_data_history_sends_normalized_multiple_tickers_and_returns_flag():
    def handler(request):
        assert request.method == "POST"
        assert request.url.path == "/market-data/history"
        assert json.loads(request.content) == {
            "tickers": ["AAPL", "MSFT"],
            "start": "2025-01-01",
            "end": "2025-02-01",
            "include_returns": True,
        }
        return httpx.Response(
            200,
            json={
                "count": 2,
                "data": [
                    {"date": "2025-01-02", "ticker": "AAPL", "close": 100.0},
                    {"date": "2025-01-02", "ticker": "MSFT", "close": 200.0},
                ],
            },
        )

    client, http_client = make_client(handler)
    try:
        result = client.market_data_history(
            [" aapl ", "MSFT", "AAPL"],
            date(2025, 1, 1),
            date(2025, 2, 1),
            include_returns=True,
        )
    finally:
        http_client.close()

    assert result.successful is True
    assert result.count == 2
    assert {row["ticker"] for row in result.data} == {"AAPL", "MSFT"}


@pytest.mark.parametrize(
    ("tickers", "start", "end", "message"),
    [
        ([], date(2025, 1, 1), date(2025, 2, 1), "at least one ticker"),
        ([" "], date(2025, 1, 1), date(2025, 2, 1), "must not be empty"),
        (["AAPL"], date(2025, 2, 1), date(2025, 1, 1), "earlier"),
    ],
)
def test_market_data_history_validates_request_before_http_call(
    tickers,
    start,
    end,
    message,
):
    client, http_client = make_client(
        lambda request: pytest.fail("HTTP request should not be sent")
    )
    try:
        with pytest.raises((TypeError, ValueError), match=message):
            client.market_data_history(tickers, start, end)
    finally:
        http_client.close()


def test_market_data_history_handles_no_data_and_provider_failure():
    no_data_client, no_data_http_client = make_client(
        lambda request: httpx.Response(404, json={"detail": {"code": "no_data"}})
    )
    try:
        no_data = no_data_client.market_data_history(
            ["AAPL"], date(2025, 1, 1), date(2025, 2, 1)
        )
    finally:
        no_data_http_client.close()

    provider_client, provider_http_client = make_client(
        lambda request: httpx.Response(
            502,
            json={"detail": {"code": "provider_failure"}},
        )
    )
    try:
        provider_failure = provider_client.market_data_history(
            ["AAPL"], date(2025, 1, 1), date(2025, 2, 1)
        )
    finally:
        provider_http_client.close()

    assert no_data.successful is False
    assert no_data.status_code == 404
    assert "No market data" in no_data.message
    assert provider_failure.successful is False
    assert provider_failure.status_code == 502
    assert "provider failed" in provider_failure.message


def test_market_data_history_handles_connection_failure_and_invalid_payload():
    def connection_failure(request):
        raise httpx.ConnectError("connection refused", request=request)

    client, http_client = make_client(connection_failure)
    try:
        unavailable = client.market_data_history(
            ["AAPL"], date(2025, 1, 1), date(2025, 2, 1)
        )
    finally:
        http_client.close()

    invalid_client, invalid_http_client = make_client(
        lambda request: httpx.Response(200, json={"data": [], "count": 1})
    )
    try:
        invalid = invalid_client.market_data_history(
            ["AAPL"], date(2025, 1, 1), date(2025, 2, 1)
        )
    finally:
        invalid_http_client.close()

    assert unavailable.status_code is None
    assert "unavailable" in unavailable.message
    assert invalid.successful is False
    assert "invalid response" in invalid.message


def test_portfolio_analytics_sends_supported_payload():
    def handler(request):
        assert request.url.path == "/portfolio/analytics"
        payload = json.loads(request.content)
        assert payload["asset_returns"] == {"AAPL": [0.1, 0.0], "MSFT": [0.05, 0.02]}
        assert payload["weights"] == {"AAPL": 0.5, "MSFT": 0.5}
        return httpx.Response(200, json={"volatility": 0.1, "correlation": {}})

    client, http_client = make_client(handler)
    try:
        result = client.portfolio_analytics(
            {"AAPL": [0.1, 0.0], "MSFT": [0.05, 0.02]},
            weights={"AAPL": 0.5, "MSFT": 0.5},
        )
    finally:
        http_client.close()
    assert result.successful is True
    assert result.data["volatility"] == 0.1


def test_portfolio_analytics_validates_before_http_and_handles_connection_failure():
    client, http_client = make_client(lambda request: pytest.fail("HTTP should not be sent"))
    try:
        with pytest.raises(ValueError, match="sum to one"):
            client.portfolio_analytics(
                {"AAPL": [0.1, 0.0]},
                weights={"AAPL": 0.2},
            )
    finally:
        http_client.close()

    unavailable_client, unavailable_http_client = make_client(
        lambda request: (_ for _ in ()).throw(httpx.ConnectError("offline", request=request))
    )
    try:
        result = unavailable_client.portfolio_analytics(
            {"AAPL": [0.1, 0.0]},
            weights={"AAPL": 1.0},
        )
    finally:
        unavailable_http_client.close()
    assert result.successful is False
    assert result.status_code is None


def test_run_backtest_constructs_request_and_parses_response():
    def handler(request):
        assert request.url.path == "/backtests/run"
        payload = json.loads(request.content)
        assert payload["strategy"] == {
            "type": "moving_average_crossover",
            "short_window": 2,
            "long_window": 5,
        }
        assert payload["benchmark_ticker"] == "SPY"
        return httpx.Response(
            200,
            json={
                "metrics": {},
                "equity": [],
                "cash": [],
                "positions": [],
                "trades": [],
            },
        )

    client, http_client = make_client(handler)
    try:
        result = client.run_backtest(
            ["aapl", "spy"],
            date(2025, 1, 1),
            date(2025, 2, 1),
            initial_capital=1000,
            short_window=2,
            long_window=5,
            benchmark_ticker="spy",
        )
    finally:
        http_client.close()
    assert result.successful is True
    assert result.data["metrics"] == {}


def test_run_backtest_rejects_invalid_windows_and_provider_errors():
    client, http_client = make_client(lambda request: pytest.fail("HTTP should not be sent"))
    try:
        with pytest.raises(ValueError, match="smaller"):
            client.run_backtest(
                ["AAPL"],
                date(2025, 1, 1),
                date(2025, 2, 1),
                initial_capital=1000,
                short_window=5,
                long_window=2,
            )
    finally:
        http_client.close()

    failed_client, failed_http_client = make_client(
        lambda request: httpx.Response(502, json={"detail": "provider failure"})
    )
    try:
        result = failed_client.run_backtest(
            ["AAPL"],
            date(2025, 1, 1),
            date(2025, 2, 1),
            initial_capital=1000,
            short_window=2,
            long_window=5,
        )
    finally:
        failed_http_client.close()
    assert result.status_code == 502
    assert "provider" in result.message
