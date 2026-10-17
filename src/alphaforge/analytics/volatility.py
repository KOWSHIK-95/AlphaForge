import math

import pandas as pd


def calculate_volatility(returns: pd.Series, annualize: bool = False) -> float:
    """Calculate sample volatility from a series of returns.

    Volatility is the sample standard deviation,
    ``sqrt(sum((r[i] - mean(r)) ** 2) / (n - 1))``, using ``ddof=1``.
    Missing observations are ignored. When ``annualize`` is true, the
    daily volatility is multiplied by ``sqrt(252)``.

    Args:
        returns: A series of numeric returns.
        annualize: Whether to convert daily volatility to annual volatility.

    Returns:
        The sample standard deviation of the valid returns.

    Raises:
        TypeError: If returns is not a pandas Series of real numeric values.
        ValueError: If returns contains infinite values or fewer than two
            valid observations.
    """
    if not isinstance(returns, pd.Series):
        raise TypeError("returns must be a pandas Series.")

    observed_returns = returns.dropna()
    if observed_returns.empty:
        raise ValueError("at least two valid return observations are required.")

    if (
        not pd.api.types.is_numeric_dtype(returns.dtype)
        or pd.api.types.is_bool_dtype(returns.dtype)
        or pd.api.types.is_complex_dtype(returns.dtype)
    ):
        raise TypeError("returns must contain real numeric values.")

    if observed_returns.isin([float("inf"), float("-inf")]).any():
        raise ValueError("returns must not contain infinite values.")

    if len(observed_returns) < 2:
        raise ValueError("at least two valid return observations are required.")

    volatility = float(observed_returns.std(ddof=1))
    if annualize:
        volatility *= math.sqrt(252)

    return volatility
