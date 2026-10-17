import pandas as pd


def _validate_prices(prices: pd.Series) -> None:
    if not isinstance(prices, pd.Series):
        raise TypeError("prices must be a pandas Series.")

    if (
        not pd.api.types.is_numeric_dtype(prices.dtype)
        or pd.api.types.is_bool_dtype(prices.dtype)
        or pd.api.types.is_complex_dtype(prices.dtype)
    ):
        raise TypeError("prices must contain real numeric values.")

    observed_prices = prices.dropna()
    if observed_prices.isin([float("inf"), float("-inf")]).any():
        raise ValueError("prices must not contain infinite values.")
    if observed_prices.le(0).any():
        raise ValueError("prices must be strictly positive; zero and negative prices are invalid.")


def calculate_drawdown(prices: pd.Series) -> pd.Series:
    """Calculate each price's decline from its running historical peak.

    Drawdown is ``(price / running_peak) - 1``. Missing prices remain missing;
    they are skipped when tracking the peak, so later observations use the
    most recent peak among valid prices.
    """
    _validate_prices(prices)

    running_peak = prices.cummax(skipna=True)
    return prices.div(running_peak).sub(1)


def calculate_max_drawdown(prices: pd.Series) -> float:
    """Return the minimum drawdown, ignoring missing drawdown observations.

    If every observation is missing, the result is ``nan``. Otherwise, the
    minimum is taken over the valid drawdowns returned by
    :func:`calculate_drawdown`.
    """
    drawdowns = calculate_drawdown(prices)
    return float(drawdowns.min(skipna=True))
