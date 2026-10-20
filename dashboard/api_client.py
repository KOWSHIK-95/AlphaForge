"""Small HTTP client for the AlphaForge API."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx

from dashboard.config import get_api_url


@dataclass(frozen=True)
class HealthResult:
    """Outcome of an AlphaForge API health check."""

    reachable: bool
    status: str | None
    message: str


@dataclass(frozen=True)
class MarketDataResult:
    """Outcome of a market-data history request."""

    data: list[dict[str, Any]]
    count: int
    status_code: int | None
    message: str

    @property
    def successful(self) -> bool:
        """Whether the API returned usable market data."""
        return self.status_code == 200 and bool(self.data)


class AlphaForgeApiClient:
    """Call the public AlphaForge API endpoints used by the dashboard."""

    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout: float = 5.0,
        client: httpx.Client | None = None,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive.")
        self.base_url = (base_url or get_api_url()).rstrip("/")
        self._timeout = timeout
        self._client = client or httpx.Client(base_url=self.base_url)
        self._owns_client = client is None

    def health(self) -> HealthResult:
        """Return a user-safe result for the API health endpoint."""
        try:
            response = self._client.get("/health", timeout=self._timeout)
            response.raise_for_status()
            payload: Any = response.json()
        except httpx.RequestError:
            return HealthResult(
                reachable=False,
                status=None,
                message="AlphaForge API is unavailable. Check that the API is running.",
            )
        except httpx.HTTPStatusError as error:
            return HealthResult(
                reachable=False,
                status=None,
                message=f"AlphaForge API returned HTTP {error.response.status_code}.",
            )
        except (TypeError, ValueError):
            return HealthResult(
                reachable=False,
                status=None,
                message="AlphaForge API returned an invalid health response.",
            )

        if not isinstance(payload, dict) or payload.get("status") != "ok":
            return HealthResult(
                reachable=False,
                status=None,
                message="AlphaForge API returned an unexpected health response.",
            )
        return HealthResult(
            reachable=True,
            status="ok",
            message="AlphaForge API is reachable.",
        )

    def market_data_history(
        self,
        tickers: Sequence[str],
        start: date,
        end: date,
        *,
        include_returns: bool = False,
    ) -> MarketDataResult:
        """Fetch validated historical market data from the API."""
        normalized_tickers = _normalize_request_tickers(tickers)
        if start >= end:
            raise ValueError("start must be earlier than end.")

        try:
            response = self._client.post(
                "/market-data/history",
                json={
                    "tickers": normalized_tickers,
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "include_returns": include_returns,
                },
                timeout=self._timeout,
            )
            if response.status_code == 404:
                return MarketDataResult(
                    data=[],
                    count=0,
                    status_code=404,
                    message="No market data was returned for the requested range.",
                )
            response.raise_for_status()
            payload: Any = response.json()
        except httpx.RequestError:
            return MarketDataResult(
                data=[],
                count=0,
                status_code=None,
                message="Market-data API is unavailable. Check that the API is running.",
            )
        except httpx.HTTPStatusError as error:
            return MarketDataResult(
                data=[],
                count=0,
                status_code=error.response.status_code,
                message=_market_data_error_message(error.response),
            )
        except (TypeError, ValueError):
            return MarketDataResult(
                data=[],
                count=0,
                status_code=response.status_code if "response" in locals() else None,
                message="Market-data API returned an invalid response.",
            )

        if not isinstance(payload, dict):
            return MarketDataResult(
                data=[],
                count=0,
                status_code=200,
                message="Market-data API returned an invalid response.",
            )
        records = payload.get("data")
        count = payload.get("count")
        if (
            not isinstance(records, list)
            or not all(isinstance(record, dict) for record in records)
            or not isinstance(count, int)
            or count != len(records)
        ):
            return MarketDataResult(
                data=[],
                count=0,
                status_code=200,
                message="Market-data API returned an invalid response.",
            )
        if not records:
            return MarketDataResult(
                data=[],
                count=0,
                status_code=200,
                message="No market data was returned for the requested range.",
            )
        return MarketDataResult(
            data=records,
            count=count,
            status_code=200,
            message="Market data loaded successfully.",
        )

    def close(self) -> None:
        """Close the underlying HTTP client when it is owned by this instance."""
        if self._owns_client:
            self._client.close()


def _normalize_request_tickers(tickers: Sequence[str]) -> list[str]:
    if isinstance(tickers, str):
        raise TypeError("tickers must be a sequence of ticker strings.")
    normalized: list[str] = []
    for ticker in tickers:
        if not isinstance(ticker, str):
            raise TypeError("each ticker must be a string.")
        symbol = ticker.strip().upper()
        if not symbol:
            raise ValueError("ticker symbols must not be empty.")
        if len(symbol) > 32:
            raise ValueError("ticker symbols must not exceed 32 characters.")
        if symbol not in normalized:
            normalized.append(symbol)
    if not normalized:
        raise ValueError("at least one ticker is required.")
    return normalized


def _market_data_error_message(response: httpx.Response) -> str:
    if response.status_code == 422:
        return "The market-data request was rejected. Check the tickers and dates."
    if response.status_code == 502:
        return "The market-data provider failed. Try again later."
    if response.status_code >= 500:
        return "The market-data API encountered a server error."
    return f"Market-data API returned HTTP {response.status_code}."
