"""Small HTTP client for the AlphaForge API."""

from dataclasses import dataclass
from typing import Any

import httpx

from dashboard.config import get_api_url


@dataclass(frozen=True)
class HealthResult:
    """Outcome of an AlphaForge API health check."""

    reachable: bool
    status: str | None
    message: str


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

    def close(self) -> None:
        """Close the underlying HTTP client when it is owned by this instance."""
        if self._owns_client:
            self._client.close()
