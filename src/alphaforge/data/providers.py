from collections.abc import Sequence
from datetime import date, datetime
from typing import Protocol

import pandas as pd
import yfinance as yf

from alphaforge.data.validation import MARKET_DATA_COLUMNS, normalize_tickers


class MarketDataProvider(Protocol):
    """Provider interface returning standardized, not-yet-validated bars."""

    def fetch_history(
        self,
        tickers: Sequence[str],
        start: date | datetime | str,
        end: date | datetime | str,
    ) -> pd.DataFrame:
        """Fetch daily history with an inclusive start and exclusive end."""


class YFinanceProvider:
    """Fetch and reshape daily bars from yfinance."""

    _TIMEOUT_SECONDS = 10
    _MAX_ATTEMPTS = 2

    def fetch_history(
        self,
        tickers: Sequence[str],
        start: date | datetime | str,
        end: date | datetime | str,
    ) -> pd.DataFrame:
        symbols = normalize_tickers(tickers)
        last_error: Exception | None = None
        for _ in range(self._MAX_ATTEMPTS):
            try:
                downloaded = yf.download(
                    tickers=symbols,
                    start=start,
                    end=end,
                    auto_adjust=False,
                    group_by="ticker",
                    progress=False,
                    timeout=self._TIMEOUT_SECONDS,
                )
                break
            except Exception as error:
                last_error = error
        else:
            raise RuntimeError(f"yfinance failed to download history for {symbols}.") from last_error

        if downloaded.empty:
            return pd.DataFrame(columns=MARKET_DATA_COLUMNS)

        if isinstance(downloaded.columns, pd.MultiIndex):
            return self._reshape_multi_ticker(downloaded, symbols)
        if len(symbols) != 1:
            raise ValueError("yfinance returned ungrouped columns for multiple tickers.")
        return self._reshape_single_ticker(downloaded, symbols[0])

    @staticmethod
    def _reshape_single_ticker(data: pd.DataFrame, ticker: str) -> pd.DataFrame:
        result = data.rename(columns=_standardize_field).reset_index()
        date_column = result.columns[0]
        result = result.rename(columns={date_column: "date"})
        result.insert(1, "ticker", ticker)
        return result

    @classmethod
    def _reshape_multi_ticker(
        cls,
        data: pd.DataFrame,
        tickers: list[str],
    ) -> pd.DataFrame:
        ticker_level = _find_ticker_level(data.columns, tickers)
        if ticker_level is None:
            raise ValueError("yfinance response did not include requested ticker columns.")

        level_values = data.columns.get_level_values(ticker_level)
        ticker_names = {str(value).upper(): value for value in level_values}
        frames = []
        for ticker in tickers:
            provider_name = ticker_names.get(ticker)
            if provider_name is None:
                continue
            ticker_data = data.xs(provider_name, axis=1, level=ticker_level)
            frames.append(cls._reshape_single_ticker(ticker_data, ticker))
        if not frames:
            return pd.DataFrame(columns=MARKET_DATA_COLUMNS)
        return pd.concat(frames, ignore_index=True)


def _find_ticker_level(columns: pd.MultiIndex, tickers: list[str]) -> int | None:
    requested = set(tickers)
    for level in range(columns.nlevels):
        values = {str(value).upper() for value in columns.get_level_values(level)}
        if requested.intersection(values):
            return level
    return None


def _standardize_field(value: object) -> str:
    return str(value).strip().lower().replace(" ", "_")
