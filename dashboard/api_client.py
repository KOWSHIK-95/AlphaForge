"""Small HTTP client for the AlphaForge API."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
import math
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


@dataclass(frozen=True)
class ApiResult:
    """Outcome of a JSON API request."""

    data: dict[str, Any]
    status_code: int | None
    message: str

    @property
    def successful(self) -> bool:
        """Whether the API returned a usable JSON object."""
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

    def portfolio_analytics(
        self,
        asset_returns: dict[str, list[float]],
        *,
        weights: dict[str, float] | None = None,
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252,
        confidence_level: float = 0.95,
        optimization: str = "none",
    ) -> ApiResult:
        """Calculate portfolio analytics through the existing API endpoint."""
        _validate_portfolio_request(
            asset_returns,
            weights=weights,
            risk_free_rate=risk_free_rate,
            periods_per_year=periods_per_year,
            confidence_level=confidence_level,
            optimization=optimization,
        )
        payload: dict[str, Any] = {
            "asset_returns": asset_returns,
            "risk_free_rate": risk_free_rate,
            "periods_per_year": periods_per_year,
            "confidence_level": confidence_level,
            "optimization": optimization,
        }
        if weights is not None:
            payload["weights"] = weights
        return self._post_json(
            "/portfolio/analytics",
            payload,
            unavailable_message="Portfolio analytics API is unavailable. Check that the API is running.",
            validation_message="The portfolio request was rejected. Check the assets and weights.",
            provider_message="The portfolio analytics API encountered a server error.",
        )

    def run_backtest(
        self,
        tickers: Sequence[str],
        start: date,
        end: date,
        *,
        initial_capital: float,
        short_window: int,
        long_window: int,
        transaction_cost_rate: float = 0.0,
        slippage_rate: float = 0.0,
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252,
        benchmark_ticker: str | None = None,
    ) -> ApiResult:
        """Run the supported moving-average crossover backtest."""
        normalized_tickers = _normalize_request_tickers(tickers)
        if start >= end:
            raise ValueError("start must be earlier than end.")
        if initial_capital <= 0:
            raise ValueError("initial_capital must be positive.")
        if short_window <= 0 or long_window <= 0 or short_window >= long_window:
            raise ValueError("short_window must be positive and smaller than long_window.")
        if not 0 <= transaction_cost_rate < 1:
            raise ValueError("transaction_cost_rate must be between zero and one.")
        if not 0 <= slippage_rate < 1:
            raise ValueError("slippage_rate must be between zero and one.")
        if periods_per_year <= 0:
            raise ValueError("periods_per_year must be positive.")
        normalized_benchmark = None
        if benchmark_ticker is not None:
            normalized_benchmark = _normalize_request_tickers([benchmark_ticker])[0]
            if normalized_benchmark not in normalized_tickers:
                raise ValueError("benchmark ticker must be included in the ticker list.")
        result = self._post_json(
            "/backtests/run",
            {
                "tickers": normalized_tickers,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "initial_capital": initial_capital,
                "strategy": {
                    "type": "moving_average_crossover",
                    "short_window": short_window,
                    "long_window": long_window,
                },
                "transaction_cost_rate": transaction_cost_rate,
                "slippage_rate": slippage_rate,
                "risk_free_rate": risk_free_rate,
                "periods_per_year": periods_per_year,
                "benchmark_ticker": normalized_benchmark,
            },
            unavailable_message="Backtesting API is unavailable. Check that the API is running.",
            validation_message="The backtest request was rejected. Check the parameters and data range.",
            provider_message="The market-data provider failed while running the backtest.",
        )
        if result.successful and not {"metrics", "equity", "cash", "positions", "trades"}.issubset(result.data):
            return ApiResult({}, result.status_code, "Backtest API returned an incomplete response.")
        return result

    def _post_json(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        unavailable_message: str,
        validation_message: str,
        provider_message: str,
    ) -> ApiResult:
        try:
            response = self._client.post(path, json=payload, timeout=self._timeout)
            response.raise_for_status()
            body: Any = response.json()
        except httpx.RequestError:
            return ApiResult({}, None, unavailable_message)
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 422:
                message = validation_message
            elif error.response.status_code == 502:
                message = provider_message
            elif error.response.status_code >= 500:
                message = "AlphaForge API encountered a server error."
            else:
                message = f"AlphaForge API returned HTTP {error.response.status_code}."
            return ApiResult({}, error.response.status_code, message)
        except (TypeError, ValueError):
            return ApiResult({}, response.status_code if "response" in locals() else None, "AlphaForge API returned an invalid response.")
        if not isinstance(body, dict):
            return ApiResult({}, 200, "AlphaForge API returned an invalid response.")
        return ApiResult(body, 200, "Request completed successfully.")


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


def _validate_portfolio_request(
    asset_returns: dict[str, list[float]],
    *,
    weights: dict[str, float] | None,
    risk_free_rate: float,
    periods_per_year: int,
    confidence_level: float,
    optimization: str,
) -> None:
    if not asset_returns or any(not name.strip() for name in asset_returns):
        raise ValueError("asset_returns must contain non-empty asset names.")
    lengths = {len(values) for values in asset_returns.values()}
    if len(lengths) != 1 or not next(iter(lengths), 0):
        raise ValueError("asset return series must have equal, non-empty lengths.")
    if optimization not in {"none", "minimum_volatility", "maximum_sharpe"}:
        raise ValueError("optimization is not supported.")
    if optimization == "none" and weights is None:
        raise ValueError("weights are required when optimization is none.")
    if weights is not None:
        if set(weights) != set(asset_returns):
            raise ValueError("weights must match the asset return names.")
        if any(
            not isinstance(value, (int, float)) or not math.isfinite(value)
            for value in weights.values()
        ):
            raise ValueError("weights must be numeric.")
        if abs(sum(weights.values()) - 1.0) > 1e-8:
            raise ValueError("weights must sum to one.")
    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive.")
    if not 0 < confidence_level < 1:
        raise ValueError("confidence_level must be between zero and one.")
    if (
        not isinstance(risk_free_rate, (int, float))
        or not math.isfinite(risk_free_rate)
        or risk_free_rate <= -1
    ):
        raise ValueError("risk_free_rate must be numeric.")
