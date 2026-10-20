import httpx
import pytest

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
