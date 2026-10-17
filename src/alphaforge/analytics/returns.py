import pandas as pd


def calculate_returns(prices: pd.Series) -> pd.Series:
    """Calculate simple returns as ``P[t] / P[t - 1] - 1``.

    Missing prices are not filled; returns are missing whenever either
    price in a consecutive pair is missing. Prices must be numeric, finite,
    and strictly positive. Zero prices are rejected because they make the
    return from that price undefined.

    Args:
        prices: A time series containing asset prices.

    Returns:
        Simple returns between consecutive prices.

    Raises:
        TypeError: If prices is not a Series of real numeric values.
        ValueError: If any non-missing price is infinite, zero, or negative.
    """
    if not isinstance(prices, pd.Series):
        raise TypeError("prices must be a pandas Series.")

    if prices.empty:
        return pd.Series(index=prices.index, dtype="float64", name=prices.name)

    observed_prices = prices.dropna()
    if observed_prices.empty:
        return pd.Series(float("nan"), index=prices.index, name=prices.name)

    if (
        not pd.api.types.is_numeric_dtype(prices.dtype)
        or pd.api.types.is_bool_dtype(prices.dtype)
        or pd.api.types.is_complex_dtype(prices.dtype)
    ):
        raise TypeError("prices must contain real numeric values.")

    if observed_prices.isin([float("inf"), float("-inf")]).any():
        raise ValueError("prices must not contain infinite values.")

    if observed_prices.le(0).any():
        raise ValueError("prices must be strictly positive; zero and negative prices are invalid.")

    return prices.pct_change(fill_method=None)