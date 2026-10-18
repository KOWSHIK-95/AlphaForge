import math
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import alphaforge.analytics.portfolio as portfolio_analytics
from alphaforge.analytics.portfolio import (
    PortfolioOptimizationResult,
    calculate_asset_correlation,
    calculate_cumulative_returns,
    calculate_historical_cvar,
    calculate_historical_var,
    calculate_portfolio_max_drawdown,
    calculate_portfolio_returns,
    calculate_portfolio_sharpe_ratio,
    calculate_portfolio_volatility,
    optimize_maximum_sharpe,
    optimize_minimum_volatility,
)


@pytest.fixture
def asset_returns():
    return pd.DataFrame(
        {
            "A": [0.01, 0.02, -0.01, 0.03, 0.00],
            "B": [0.00, 0.01, 0.00, 0.01, 0.02],
        },
        index=pd.date_range("2025-01-01", periods=5),
    )


def test_calculate_portfolio_returns_preserves_index_and_aligns_labeled_weights(
    asset_returns,
):
    weights = pd.Series({"B": 0.25, "A": 0.75})

    actual = calculate_portfolio_returns(asset_returns, weights)

    expected = 0.75 * asset_returns["A"] + 0.25 * asset_returns["B"]
    expected.name = "portfolio_return"
    pd.testing.assert_series_equal(actual, expected)


def test_calculate_portfolio_returns_accepts_numpy_weights(asset_returns):
    actual = calculate_portfolio_returns(asset_returns, np.array([0.5, 0.5]))
    expected = (asset_returns["A"] + asset_returns["B"]) / 2

    assert actual.tolist() == pytest.approx(expected.tolist())


@pytest.mark.parametrize(
    ("weights", "exception", "message"),
    [
        (pd.Series([0.5]), ValueError, "exactly one"),
        (pd.Series([0.5, np.nan], index=["A", "B"]), ValueError, "missing"),
        (pd.Series([True, False], index=["A", "B"]), TypeError, "numeric"),
        (np.array([0.5]), ValueError, "matching"),
        (np.array([0.5, np.inf]), ValueError, "finite"),
        (np.array([0.2, 0.2]), ValueError, "sum to 1"),
        ([0.5, 0.5], TypeError, "Series or NumPy"),
    ],
)
def test_calculate_portfolio_returns_validates_weights(
    asset_returns,
    weights,
    exception,
    message,
):
    with pytest.raises(exception, match=message):
        calculate_portfolio_returns(asset_returns, weights)


@pytest.mark.parametrize(
    "invalid_returns",
    [
        pd.DataFrame({"A": [0.01, np.nan]}),
        pd.DataFrame({"A": [0.01, np.inf]}),
        pd.DataFrame({"A": [0.01, -1.0]}),
        pd.DataFrame({"A": [True, False]}),
        pd.DataFrame({"A": ["0.01", "0.02"]}),
        pd.DataFrame({"A": [0.01, 0.02], "B": [0.03, 0.04]}).set_axis(
            ["A", "A"], axis=1
        ),
    ],
)
def test_calculate_portfolio_returns_rejects_invalid_asset_data(invalid_returns):
    weights = np.full(invalid_returns.shape[1], 1 / invalid_returns.shape[1])

    with pytest.raises((TypeError, ValueError)):
        calculate_portfolio_returns(invalid_returns, weights)


def test_calculate_cumulative_returns_compounds_without_lookahead():
    returns = pd.Series([0.10, -0.10, 0.05], index=["t1", "t2", "t3"])

    actual = calculate_cumulative_returns(returns)

    expected = pd.Series([0.10, -0.01, 0.0395], index=returns.index)
    expected.name = "cumulative_return"
    pd.testing.assert_series_equal(actual, expected)


@pytest.mark.parametrize("function", [calculate_cumulative_returns])
def test_time_series_calculations_reject_missing_and_insufficient_data(function):
    with pytest.raises(ValueError, match="missing"):
        function(pd.Series([0.01, np.nan]))


def test_portfolio_volatility_reuses_sample_volatility_and_annualization():
    returns = pd.Series([0.01, -0.02, 0.04])

    assert calculate_portfolio_volatility(returns) == pytest.approx(
        returns.std(ddof=1)
    )
    assert calculate_portfolio_volatility(returns, annualize=True) == pytest.approx(
        returns.std(ddof=1) * math.sqrt(252)
    )


def test_portfolio_sharpe_uses_effective_annual_risk_free_rate():
    returns = pd.Series([0.01, 0.03, -0.01])
    periods_per_year = 12
    periodic_rf = (1.05) ** (1 / periods_per_year) - 1
    expected = (
        (returns.mean() - periodic_rf)
        / returns.std(ddof=1)
        * math.sqrt(periods_per_year)
    )

    assert calculate_portfolio_sharpe_ratio(
        returns,
        risk_free_rate=0.05,
        periods_per_year=periods_per_year,
    ) == pytest.approx(expected)


def test_portfolio_max_drawdown_includes_initial_capital():
    returns = pd.Series([-0.10, 0.05])

    assert calculate_portfolio_max_drawdown(returns) == pytest.approx(-0.10)


def test_asset_correlation_matches_sample_correlation(asset_returns):
    pd.testing.assert_frame_equal(
        calculate_asset_correlation(asset_returns),
        asset_returns.corr(),
    )


def test_historical_var_and_cvar_are_positive_tail_losses():
    returns = pd.Series([-0.10, -0.05, 0.0, 0.02, 0.04])

    assert calculate_historical_var(returns, confidence_level=0.6) == pytest.approx(
        0.02
    )
    assert calculate_historical_cvar(returns, confidence_level=0.6) == pytest.approx(
        0.075
    )


def test_historical_risk_is_zero_if_the_selected_tail_has_no_losses():
    returns = pd.Series([0.01, 0.02, 0.03])

    assert calculate_historical_var(returns, confidence_level=0.95) == 0
    assert calculate_historical_cvar(returns, confidence_level=0.95) == 0


@pytest.mark.parametrize(
    "confidence_level",
    [0, 1, -0.1, 1.1, np.nan, np.inf],
)
def test_historical_risk_rejects_invalid_confidence_levels(confidence_level):
    with pytest.raises(ValueError, match="confidence_level"):
        calculate_historical_var(pd.Series([-0.1, 0.1]), confidence_level)
    with pytest.raises(ValueError, match="confidence_level"):
        calculate_historical_cvar(pd.Series([-0.1, 0.1]), confidence_level)


@pytest.mark.parametrize(
    "optimizer",
    [optimize_minimum_volatility, optimize_maximum_sharpe],
)
def test_optimizers_return_long_only_fully_invested_weights(asset_returns, optimizer):
    result = optimizer(asset_returns)

    assert isinstance(result, PortfolioOptimizationResult)
    assert result.weights.index.equals(asset_returns.columns)
    assert (result.weights >= 0).all()
    assert (result.weights <= 1).all()
    assert result.weights.sum() == pytest.approx(1)
    assert math.isfinite(result.expected_annual_return)
    assert math.isfinite(result.annualized_volatility)
    assert result.sharpe_ratio is not None
    assert math.isfinite(result.sharpe_ratio)


def test_minimum_volatility_optimizer_prefers_lower_volatility_asset():
    returns = pd.DataFrame(
        {
            "low": [-0.01, 0.01, -0.01, 0.01],
            "high": [-0.10, 0.10, -0.10, 0.10],
        }
    )

    result = optimize_minimum_volatility(returns)

    assert result.weights["low"] == pytest.approx(1.0, abs=1e-5)
    assert result.annualized_volatility == pytest.approx(
        returns["low"].std(ddof=1) * math.sqrt(252)
    )


def test_optimizer_handles_a_single_asset():
    returns = pd.DataFrame({"only": [0.01, -0.01, 0.02]})

    result = optimize_minimum_volatility(returns)

    assert result.weights.to_dict() == {"only": 1.0}


def test_maximum_sharpe_optimizer_accounts_for_risk_free_rate():
    returns = pd.DataFrame(
        {
            "steady": [0.01, 0.02, 0.015, 0.018, 0.012],
            "risky": [-0.04, 0.08, 0.06, -0.02, 0.10],
        }
    )

    result = optimize_maximum_sharpe(
        returns,
        risk_free_rate=0.03,
        periods_per_year=12,
    )

    assert result.weights.sum() == pytest.approx(1)
    assert result.sharpe_ratio == pytest.approx(
        calculate_portfolio_sharpe_ratio(
            calculate_portfolio_returns(returns, result.weights),
            risk_free_rate=0.03,
            periods_per_year=12,
        )
    )


def test_optimizer_reports_solver_failure(asset_returns, monkeypatch):
    def fail_minimize(
        objective: object,
        *,
        x0: np.ndarray,
        **options: object,
    ) -> SimpleNamespace:
        assert callable(objective)
        assert options["method"] == "SLSQP"
        return SimpleNamespace(
            success=False,
            message="iteration limit reached",
            x=x0,
        )

    monkeypatch.setattr(portfolio_analytics, "minimize", fail_minimize)

    with pytest.raises(RuntimeError, match="iteration limit reached"):
        optimize_minimum_volatility(asset_returns)


@pytest.mark.parametrize(
    "returns",
    [
        pd.DataFrame(),
        pd.DataFrame({"A": [0.01]}),
        pd.DataFrame({"A": [0.01, 0.02], "B": [0.0, 0.01]}).set_axis(
            ["A", "A"], axis=1
        ),
        pd.DataFrame({"A": [0.01, np.nan], "B": [0.02, 0.01]}),
    ],
)
def test_optimizers_reject_insufficient_or_invalid_data(returns):
    with pytest.raises((TypeError, ValueError)):
        optimize_minimum_volatility(returns)


@pytest.mark.parametrize(
    ("risk_free_rate", "periods_per_year", "exception"),
    [
        (-1.0, 252, ValueError),
        (np.inf, 252, ValueError),
        (True, 252, TypeError),
        (0.0, 0, ValueError),
        (0.0, 2.5, TypeError),
    ],
)
def test_maximum_sharpe_optimizer_validates_assumptions(
    asset_returns,
    risk_free_rate,
    periods_per_year,
    exception,
):
    with pytest.raises(exception):
        optimize_maximum_sharpe(
            asset_returns,
            risk_free_rate=risk_free_rate,
            periods_per_year=periods_per_year,
        )
