from collections.abc import Sequence
from datetime import date, datetime

import pandas as pd

from alphaforge.analytics.returns import calculate_returns
from alphaforge.data.providers import MarketDataProvider
from alphaforge.data.validation import normalize_tickers, validate_market_data
from alphaforge.database.market_data_repository import MarketDataRepository


class MarketDataEngine:
    """Coordinate provider access, market-data validation, and storage."""

    def __init__(
        self,
        provider: MarketDataProvider,
        repository: MarketDataRepository | None = None,
    ) -> None:
        self._provider = provider
        self._repository = repository

    def fetch_history(
        self,
        tickers: Sequence[str],
        start: date | datetime | str,
        end: date | datetime | str,
        *,
        include_returns: bool = False,
    ) -> pd.DataFrame:
        """Fetch and validate daily bars; yfinance-style end dates are exclusive."""
        symbols = normalize_tickers(tickers)
        start_date, end_date = _validate_date_range(start, end)
        raw_data = self._provider.fetch_history(symbols, start_date, end_date)
        history = validate_market_data(raw_data)
        unexpected_tickers = set(history["ticker"]).difference(symbols)
        if unexpected_tickers:
            unexpected = ", ".join(sorted(unexpected_tickers))
            raise ValueError(f"provider returned unrequested tickers: {unexpected}.")
        if not history.empty and (
            history["date"].lt(pd.Timestamp(start_date)).any()
            or history["date"].ge(pd.Timestamp(end_date)).any()
        ):
            raise ValueError("provider returned market data outside the requested date range.")
        return _add_returns(history) if include_returns else history

    def fetch_and_store(
        self,
        tickers: Sequence[str],
        start: date | datetime | str,
        end: date | datetime | str,
        *,
        include_returns: bool = False,
    ) -> pd.DataFrame:
        """Fetch and validate bars, persist them, and optionally append returns."""
        repository = self._require_repository()
        history = self.fetch_history(tickers, start, end)
        repository.upsert_history(history)
        return _add_returns(history) if include_returns else history

    def get_history(
        self,
        tickers: Sequence[str],
        start: date | datetime | str,
        end: date | datetime | str,
        *,
        include_returns: bool = False,
    ) -> pd.DataFrame:
        """Read stored bars and optionally append per-ticker returns."""
        repository = self._require_repository()
        symbols = normalize_tickers(tickers)
        start_date, end_date = _validate_date_range(start, end)
        history = validate_market_data(repository.get_history(symbols, start_date, end_date))
        return _add_returns(history) if include_returns else history

    def _require_repository(self) -> MarketDataRepository:
        if self._repository is None:
            raise RuntimeError("a MarketDataRepository is required for storage operations.")
        return self._repository


def _validate_date_range(
    start: date | datetime | str,
    end: date | datetime | str,
) -> tuple[date, date]:
    if start is None or end is None:
        raise ValueError("start and end must be valid dates.")
    try:
        start_timestamp = pd.Timestamp(start)
        end_timestamp = pd.Timestamp(end)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("start and end must be valid dates.") from error
    if pd.isna(start_timestamp) or pd.isna(end_timestamp):
        raise ValueError("start and end must be valid dates.")
    start_date = start_timestamp.date()
    end_date = end_timestamp.date()
    if start_date >= end_date:
        raise ValueError("start must be earlier than end.")
    return start_date, end_date


def _add_returns(history: pd.DataFrame) -> pd.DataFrame:
    result = history.copy()
    result["returns"] = float("nan")
    for _, group in result.groupby("ticker", sort=False):
        price_column = "adj_close" if group["adj_close"].notna().any() else "close"
        result.loc[group.index, "returns"] = calculate_returns(group[price_column])
    return result
