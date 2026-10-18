"""Portfolio performance, historical risk, and long-only optimization."""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Integral, Real

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from alphaforge.analytics.drawdown import calculate_max_drawdown
from alphaforge.analytics.sharpe import calculate_sharpe_ratio
from alphaforge.analytics.volatility import calculate_volatility


@dataclass(frozen=True)
class PortfolioOptimizationResult:
    """Optimized allocations and annualized in-sample performance estimates.

    ``expected_annual_return`` annualizes the arithmetic mean of periodic
    returns. ``annualized_volatility`` uses sample standard deviation.
    ``sharpe_ratio`` is ``None`` when volatility is zero.
    """

    weights: pd.Series
    expected_annual_return: float
    annualized_volatility: float
    sharpe_ratio: float | None


def _validate_asset_returns(
    asset_returns: pd.DataFrame,
    *,
    minimum_observations: int = 1,
    minimum_assets: int = 1,
) -> np.ndarray:
    if not isinstance(asset_returns, pd.DataFrame):
        raise TypeError("asset_returns must be a pandas DataFrame.")
    if asset_returns.empty or asset_returns.shape[1] < minimum_assets:
        raise ValueError(
            f"asset_returns must contain at least {minimum_assets} asset(s)."
        )
    if len(asset_returns) < minimum_observations:
        raise ValueError(
            f"at least {minimum_observations} return observations are required."
        )
    if not asset_returns.columns.is_unique:
        raise ValueError("asset_returns must have unique asset column names.")
    if asset_returns.isna().any().any():
        raise ValueError("asset_returns must not contain missing values.")
    if any(
        not pd.api.types.is_numeric_dtype(dtype)
        or pd.api.types.is_bool_dtype(dtype)
        or pd.api.types.is_complex_dtype(dtype)
        for dtype in asset_returns.dtypes
    ):
        raise TypeError("asset_returns must contain real numeric values.")

    values = asset_returns.to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("asset_returns must not contain infinite values.")
    if (values <= -1).any():
        raise ValueError("simple asset returns must be greater than -1.")
    return values


def _validate_return_series(
    returns: pd.Series,
    *,
    minimum_observations: int = 1,
) -> None:
    if not isinstance(returns, pd.Series):
        raise TypeError("returns must be a pandas Series.")
    if (
        not pd.api.types.is_numeric_dtype(returns.dtype)
        or pd.api.types.is_bool_dtype(returns.dtype)
        or pd.api.types.is_complex_dtype(returns.dtype)
    ):
        raise TypeError("returns must contain real numeric values.")
    if returns.isna().any():
        raise ValueError("returns must not contain missing values.")
    values = returns.to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("returns must not contain infinite values.")
    if (values <= -1).any():
        raise ValueError("simple returns must be greater than -1.")
    if len(returns) < minimum_observations:
        raise ValueError(
            f"at least {minimum_observations} return observations are required."
        )


def _validate_periods_per_year(periods_per_year: int) -> None:
    if (
        not isinstance(periods_per_year, Integral)
        or isinstance(periods_per_year, bool)
    ):
        raise TypeError("periods_per_year must be a positive integer.")
    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be a positive integer.")


def _validate_risk_free_rate(risk_free_rate: float) -> None:
    if not isinstance(risk_free_rate, Real) or isinstance(risk_free_rate, bool):
        raise TypeError("risk_free_rate must be a real number.")
    if not math.isfinite(risk_free_rate) or risk_free_rate <= -1:
        raise ValueError("risk_free_rate must be finite and greater than -1.")


def _validated_weights(
    asset_returns: pd.DataFrame,
    weights: pd.Series | np.ndarray,
) -> np.ndarray:
    if isinstance(weights, pd.Series):
        if not weights.index.is_unique:
            raise ValueError("weights must have unique asset labels.")
        if len(weights) != len(asset_returns.columns) or set(weights.index) != set(
            asset_returns.columns
        ):
            raise ValueError("weights must contain exactly one value for each asset.")
        weights = weights.reindex(asset_returns.columns)
        if (
            not pd.api.types.is_numeric_dtype(weights.dtype)
            or pd.api.types.is_bool_dtype(weights.dtype)
            or pd.api.types.is_complex_dtype(weights.dtype)
        ):
            raise TypeError("weights must contain real numeric values.")
        if weights.isna().any():
            raise ValueError("weights must not contain missing values.")
        values = weights.to_numpy(dtype=float)
    elif isinstance(weights, np.ndarray):
        if weights.ndim != 1 or weights.shape[0] != len(asset_returns.columns):
            raise ValueError("weights must be a one-dimensional array matching the assets.")
        if (
            not np.issubdtype(weights.dtype, np.number)
            or np.issubdtype(weights.dtype, np.bool_)
            or np.issubdtype(weights.dtype, np.complexfloating)
        ):
            raise TypeError("weights must contain real numeric values.")
        values = weights.astype(float, copy=False)
    else:
        raise TypeError("weights must be a pandas Series or NumPy array.")

    if not np.isfinite(values).all():
        raise ValueError("weights must be finite.")
    if not math.isclose(float(values.sum()), 1.0, rel_tol=1e-9, abs_tol=1e-9):
        raise ValueError("weights must sum to 1.")
    return values


def calculate_portfolio_returns(
    asset_returns: pd.DataFrame,
    weights: pd.Series | np.ndarray,
) -> pd.Series:
    """Calculate one-period weighted returns from aligned asset observations.

    Rows are treated as aligned periods; missing observations are rejected
    rather than forward-filled or dropped. Weights must sum to one, but may
    be negative for leveraged or short portfolios.
    """
    values = _validate_asset_returns(asset_returns)
    weight_values = _validated_weights(asset_returns, weights)
    portfolio_returns = values @ weight_values
    if not np.isfinite(portfolio_returns).all() or (portfolio_returns <= -1).any():
        raise ValueError("portfolio returns must be finite and greater than -1.")
    return pd.Series(
        portfolio_returns,
        index=asset_returns.index,
        name="portfolio_return",
    )


def calculate_cumulative_returns(portfolio_returns: pd.Series) -> pd.Series:
    """Compound periodic simple returns, without adding an initial capital row."""
    _validate_return_series(portfolio_returns)
    cumulative = (1 + portfolio_returns).cumprod() - 1
    if not np.isfinite(cumulative.to_numpy(dtype=float)).all():
        raise ValueError("cumulative returns overflowed to non-finite values.")
    cumulative.name = "cumulative_return"
    return cumulative


def calculate_portfolio_volatility(
    portfolio_returns: pd.Series,
    annualize: bool = False,
) -> float:
    """Calculate sample portfolio volatility, optionally annualized by sqrt(252)."""
    _validate_return_series(portfolio_returns, minimum_observations=2)
    return calculate_volatility(portfolio_returns, annualize=annualize)


def calculate_portfolio_sharpe_ratio(
    portfolio_returns: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """Calculate the existing analytics module's annualized Sharpe convention."""
    _validate_return_series(portfolio_returns, minimum_observations=2)
    return calculate_sharpe_ratio(
        portfolio_returns,
        risk_free_rate=risk_free_rate,
        periods_per_year=periods_per_year,
    )


def calculate_portfolio_max_drawdown(portfolio_returns: pd.Series) -> float:
    """Return the worst signed peak-to-trough drawdown of compounded wealth.

    Drawdowns follow ``(wealth / running_peak) - 1`` and are therefore
    non-positive, matching :func:`calculate_max_drawdown`.
    """
    _validate_return_series(portfolio_returns)
    wealth = (1 + portfolio_returns).cumprod()
    wealth_with_initial_capital = pd.concat(
        [pd.Series([1.0]), wealth.reset_index(drop=True)],
        ignore_index=True,
    )
    return calculate_max_drawdown(wealth_with_initial_capital)


def calculate_asset_correlation(asset_returns: pd.DataFrame) -> pd.DataFrame:
    """Calculate the sample Pearson correlation matrix of complete asset returns."""
    _validate_asset_returns(
        asset_returns,
        minimum_observations=2,
        minimum_assets=2,
    )
    return asset_returns.corr()


def _validate_confidence_level(confidence_level: float) -> None:
    if not isinstance(confidence_level, Real) or isinstance(confidence_level, bool):
        raise TypeError("confidence_level must be a real number.")
    if not math.isfinite(confidence_level) or not 0 < confidence_level < 1:
        raise ValueError("confidence_level must be greater than 0 and less than 1.")


def calculate_historical_var(
    returns: pd.Series,
    confidence_level: float = 0.95,
) -> float:
    """Estimate historical VaR as a nonnegative loss amount.

    The empirical ``(1 - confidence_level)`` return quantile is negated and
    floored at zero, so the result is never a gain. Inputs are periodic simple
    returns; the confidence level must be strictly between zero and one.
    """
    _validate_confidence_level(confidence_level)
    _validate_return_series(returns, minimum_observations=2)
    return max(0.0, -float(returns.quantile(1 - confidence_level)))


def calculate_historical_cvar(
    returns: pd.Series,
    confidence_level: float = 0.95,
) -> float:
    """Estimate historical CVaR as the nonnegative mean loss in the tail.

    The tail contains observations at or below the empirical
    ``(1 - confidence_level)`` return quantile. Its mean is negated and
    floored at zero, matching :func:`calculate_historical_var`'s loss
    convention.
    """
    _validate_confidence_level(confidence_level)
    _validate_return_series(returns, minimum_observations=2)
    cutoff = returns.quantile(1 - confidence_level)
    tail_mean = float(returns.loc[returns.le(cutoff)].mean())
    return max(0.0, -tail_mean)


def _optimization_result(
    asset_returns: pd.DataFrame,
    weights: np.ndarray,
    risk_free_rate: float,
    periods_per_year: int,
) -> PortfolioOptimizationResult:
    portfolio_returns = calculate_portfolio_returns(asset_returns, weights)
    annualized_volatility = calculate_volatility(
        portfolio_returns,
        annualize=True,
    )
    if annualized_volatility == 0:
        sharpe_ratio = None
    else:
        sharpe_ratio = calculate_sharpe_ratio(
            portfolio_returns,
            risk_free_rate=risk_free_rate,
            periods_per_year=periods_per_year,
        )
    return PortfolioOptimizationResult(
        weights=pd.Series(weights, index=asset_returns.columns, name="weight"),
        expected_annual_return=float(portfolio_returns.mean() * periods_per_year),
        annualized_volatility=annualized_volatility,
        sharpe_ratio=sharpe_ratio,
    )


def _optimize(
    asset_returns: pd.DataFrame,
    *,
    objective: str,
    risk_free_rate: float,
    periods_per_year: int,
) -> PortfolioOptimizationResult:
    values = _validate_asset_returns(
        asset_returns,
        minimum_observations=2,
        minimum_assets=1,
    )
    _validate_risk_free_rate(risk_free_rate)
    _validate_periods_per_year(periods_per_year)

    means = values.mean(axis=0)
    covariance = np.cov(values, rowvar=False, ddof=1)
    covariance = np.atleast_2d(covariance)
    if not np.isfinite(means).all() or not np.isfinite(covariance).all():
        raise ValueError("asset returns are too large for finite optimization estimates.")
    periodic_risk_free_rate = (1 + risk_free_rate) ** (1 / periods_per_year) - 1
    asset_count = values.shape[1]

    def volatility(weights: np.ndarray) -> float:
        variance = float(weights @ covariance @ weights)
        return math.sqrt(max(variance, 0.0))

    def target(weights: np.ndarray) -> float:
        standard_deviation = volatility(weights)
        if objective == "minimum_volatility":
            return standard_deviation
        if standard_deviation <= np.finfo(float).eps:
            return 1e100
        return -float((weights @ means - periodic_risk_free_rate) / standard_deviation)

    try:
        result = minimize(
            target,
            x0=np.full(asset_count, 1 / asset_count),
            method="SLSQP",
            bounds=[(0.0, 1.0)] * asset_count,
            constraints={
                "type": "eq",
                "fun": lambda weights: float(weights.sum() - 1),
            },
            options={"ftol": 1e-12, "maxiter": 1000},
        )
    except (ValueError, FloatingPointError, np.linalg.LinAlgError) as error:
        raise RuntimeError(f"{objective} optimization failed: {error}") from error
    if not result.success:
        raise RuntimeError(f"{objective} optimization failed: {result.message}")
    if not np.isfinite(result.x).all():
        raise RuntimeError(f"{objective} optimization returned non-finite weights.")
    weights = np.asarray(result.x, dtype=float)
    if (
        (weights < -1e-8).any()
        or (weights > 1 + 1e-8).any()
        or not math.isclose(float(weights.sum()), 1.0, abs_tol=1e-7)
    ):
        raise RuntimeError(f"{objective} optimization returned invalid weights.")
    weights = np.clip(weights, 0.0, 1.0)
    weights /= weights.sum()
    optimized = _optimization_result(
        asset_returns,
        weights,
        risk_free_rate,
        periods_per_year,
    )
    if objective == "maximum_sharpe" and optimized.sharpe_ratio is None:
        raise ValueError("maximum Sharpe ratio is undefined for zero-volatility portfolios.")
    return optimized


def optimize_minimum_volatility(
    asset_returns: pd.DataFrame,
    periods_per_year: int = 252,
) -> PortfolioOptimizationResult:
    """Find the long-only, fully invested minimum-volatility allocation.

    The estimate uses complete historical rows, sample covariance, and SLSQP.
    ``periods_per_year`` controls the annualized metrics in the result.
    """
    return _optimize(
        asset_returns,
        objective="minimum_volatility",
        risk_free_rate=0.0,
        periods_per_year=periods_per_year,
    )


def optimize_maximum_sharpe(
    asset_returns: pd.DataFrame,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> PortfolioOptimizationResult:
    """Find the long-only, fully invested maximum historical Sharpe allocation.

    The annual effective risk-free rate is converted to a periodic rate using
    ``periods_per_year``, consistent with :func:`calculate_sharpe_ratio`.
    Optimization uses complete historical rows and sample covariance.
    """
    return _optimize(
        asset_returns,
        objective="maximum_sharpe",
        risk_free_rate=risk_free_rate,
        periods_per_year=periods_per_year,
    )
