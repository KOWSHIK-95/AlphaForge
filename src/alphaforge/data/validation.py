from collections.abc import Sequence

import pandas as pd


MARKET_DATA_COLUMNS = [
    "date",
    "ticker",
    "open",
    "high",
    "low",
    "close",
    "adj_close",
    "volume",
]
PRICE_COLUMNS = ["open", "high", "low", "close", "adj_close"]
NUMERIC_COLUMNS = [*PRICE_COLUMNS, "volume"]


def normalize_tickers(tickers: Sequence[str]) -> list[str]:
    """Validate, uppercase, and de-duplicate ticker symbols."""
    if isinstance(tickers, str) or not isinstance(tickers, Sequence):
        raise TypeError("tickers must be a sequence of ticker strings.")

    normalized: list[str] = []
    for ticker in tickers:
        if not isinstance(ticker, str):
            raise TypeError("each ticker must be a string.")
        ticker = ticker.strip().upper()
        if not ticker:
            raise ValueError("ticker symbols must not be empty.")
        if ticker not in normalized:
            normalized.append(ticker)

    if not normalized:
        raise ValueError("at least one ticker is required.")
    return normalized


def _normalize_date(value: object) -> pd.Timestamp:
    if value is None or pd.isna(value):
        raise ValueError("market data dates must not be missing.")
    try:
        date = pd.Timestamp(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"invalid market data date: {value!r}.") from error

    if date.tzinfo is not None:
        date = date.tz_localize(None)
    return date.normalize()


def validate_market_data(data: pd.DataFrame) -> pd.DataFrame:
    """Return provider-neutral daily bars, sorted by ticker and date.

    Exact duplicate ticker/date records are dropped. Conflicting records for
    a ticker/date are rejected. Missing numeric observations remain missing;
    non-missing prices must be finite and positive and volume must be finite
    and non-negative.
    """
    if not isinstance(data, pd.DataFrame):
        raise TypeError("market data must be a pandas DataFrame.")

    if data.empty:
        return pd.DataFrame(
            {
                "date": pd.Series(dtype="datetime64[ns]"),
                "ticker": pd.Series(dtype="object"),
                **{column: pd.Series(dtype="float64") for column in NUMERIC_COLUMNS},
            }
        )

    required_columns = {"date", "ticker", "close"}
    missing_columns = required_columns.difference(data.columns)
    if missing_columns:
        missing_names = ", ".join(sorted(missing_columns))
        raise ValueError(f"market data is missing required columns: {missing_names}.")

    result = data.copy()
    for column in MARKET_DATA_COLUMNS:
        if column not in result.columns:
            result[column] = float("nan") if column in NUMERIC_COLUMNS else None
    result = result.loc[:, MARKET_DATA_COLUMNS]

    if result.empty:
        return pd.DataFrame(
            {
                "date": pd.Series(dtype="datetime64[ns]"),
                "ticker": pd.Series(dtype="object"),
                **{column: pd.Series(dtype="float64") for column in NUMERIC_COLUMNS},
            }
        )

    if result["ticker"].isna().any():
        raise ValueError("ticker symbols must not be missing.")
    if not result["ticker"].map(lambda ticker: isinstance(ticker, str)).all():
        raise TypeError("ticker symbols must be strings.")
    result["ticker"] = result["ticker"].str.strip().str.upper()
    if result["ticker"].eq("").any():
        raise ValueError("ticker symbols must not be empty.")
    if result["ticker"].str.len().gt(32).any():
        raise ValueError("ticker symbols must not exceed 32 characters.")

    result["date"] = result["date"].map(_normalize_date)
    for column in NUMERIC_COLUMNS:
        if not pd.api.types.is_numeric_dtype(result[column].dtype):
            raise TypeError(f"{column} values must be numeric.")
        if pd.api.types.is_bool_dtype(result[column].dtype) or pd.api.types.is_complex_dtype(
            result[column].dtype
        ):
            raise TypeError(f"{column} values must be real numeric values.")
        values = result[column].dropna()
        if not values.map(lambda value: pd.notna(value) and abs(value) != float("inf")).all():
            raise ValueError(f"{column} values must be finite.")
        if column in PRICE_COLUMNS and values.le(0).any():
            raise ValueError(f"{column} prices must be positive.")
        if column == "volume" and values.lt(0).any():
            raise ValueError("volume values must be non-negative.")
        result[column] = result[column].astype("float64")

    result = result.drop_duplicates()
    duplicate_keys = result.duplicated(["ticker", "date"], keep=False)
    if duplicate_keys.any():
        raise ValueError("conflicting market data rows have duplicate ticker/date keys.")

    return result.sort_values(["ticker", "date"], kind="stable").reset_index(drop=True)
