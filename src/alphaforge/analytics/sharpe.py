import math
from numbers import Integral, Real

import pandas as pd


def calculate_sharpe_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """Calculate the annualized Sharpe ratio from periodic returns.

    The ratio is ``(mean(return) - periodic_risk_free_rate) / sample_std
    * sqrt(periods_per_year)``. The annual effective risk-free rate is
    converted to a periodic rate as
    ``(1 + risk_free_rate) ** (1 / periods_per_year) - 1``.
    Missing returns are ignored, and sample standard deviation uses
    ``ddof=1``.
    """
    if not isinstance(returns, pd.Series):
        raise TypeError("returns must be a pandas Series.")
    if (
        not isinstance(risk_free_rate, Real)
        or isinstance(risk_free_rate, bool)
    ):
        raise TypeError("risk_free_rate must be a real number.")
    if not math.isfinite(risk_free_rate) or risk_free_rate <= -1:
        raise ValueError("risk_free_rate must be finite and greater than -1.")
    if (
        not isinstance(periods_per_year, Integral)
        or isinstance(periods_per_year, bool)
    ):
        raise TypeError("periods_per_year must be a positive integer.")
    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be a positive integer.")

    if (
        not pd.api.types.is_numeric_dtype(returns.dtype)
        or pd.api.types.is_bool_dtype(returns.dtype)
        or pd.api.types.is_complex_dtype(returns.dtype)
    ):
        raise TypeError("returns must contain real numeric values.")

    observed_returns = returns.dropna()
    if observed_returns.isin([float("inf"), float("-inf")]).any():
        raise ValueError("returns must not contain infinite values.")
    if len(observed_returns) < 2:
        raise ValueError("at least two valid return observations are required.")

    volatility = float(observed_returns.std(ddof=1))
    if volatility == 0:
        raise ValueError("volatility must be greater than zero to calculate the Sharpe ratio.")

    risk_free_rate_per_period = (1 + risk_free_rate) ** (1 / periods_per_year) - 1
    mean_excess_return = float(observed_returns.mean()) - risk_free_rate_per_period
    return mean_excess_return / volatility * math.sqrt(periods_per_year)
