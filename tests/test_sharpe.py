import math

import pandas as pd
import pytest

from alphaforge.analytics.sharpe import calculate_sharpe_ratio


def test_calculate_sharpe_ratio_uses_annualized_sample_volatility():
    returns = pd.Series([0.01, 0.03, -0.01])
    expected = returns.mean() / returns.std(ddof=1) * math.sqrt(252)

    assert calculate_sharpe_ratio(returns) == pytest.approx(expected)


def test_calculate_sharpe_ratio_converts_annual_risk_free_rate_to_periodic():
    returns = pd.Series([0.01, 0.03, -0.01])
    risk_free_rate = 0.05
    periods_per_year = 12
    periodic_risk_free_rate = (1 + risk_free_rate) ** (1 / periods_per_year) - 1
    expected = (
        (returns.mean() - periodic_risk_free_rate)
        / returns.std(ddof=1)
        * math.sqrt(periods_per_year)
    )

    actual = calculate_sharpe_ratio(
        returns,
        risk_free_rate=risk_free_rate,
        periods_per_year=periods_per_year,
    )

    assert actual == pytest.approx(expected)


def test_calculate_sharpe_ratio_ignores_missing_values():
    returns = pd.Series([0.01, float("nan"), 0.03, -0.01])
    valid_returns = returns.dropna()
    expected = valid_returns.mean() / valid_returns.std(ddof=1) * math.sqrt(252)

    assert calculate_sharpe_ratio(returns) == pytest.approx(expected)


@pytest.mark.parametrize(
    "returns",
    [
        [0.01, 0.02],
        pd.Series(["0.01", "0.02"]),
        pd.Series([0.01, "invalid"]),
        pd.Series([True, False]),
    ],
)
def test_calculate_sharpe_ratio_rejects_invalid_returns(returns):
    with pytest.raises(TypeError, match="returns"):
        calculate_sharpe_ratio(returns)


@pytest.mark.parametrize("infinite_value", [float("inf"), float("-inf")])
def test_calculate_sharpe_ratio_rejects_infinite_returns(infinite_value):
    with pytest.raises(ValueError, match="infinite"):
        calculate_sharpe_ratio(pd.Series([0.01, 0.02, infinite_value]))


@pytest.mark.parametrize(
    "returns",
    [
        pd.Series([], dtype="float64"),
        pd.Series([float("nan"), float("nan")]),
        pd.Series([0.01]),
        pd.Series([0.01, float("nan")]),
    ],
)
def test_calculate_sharpe_ratio_requires_two_valid_returns(returns):
    with pytest.raises(ValueError, match="at least two"):
        calculate_sharpe_ratio(returns)


def test_calculate_sharpe_ratio_rejects_zero_volatility():
    with pytest.raises(ValueError, match="volatility"):
        calculate_sharpe_ratio(pd.Series([0.02, 0.02, 0.02]))


@pytest.mark.parametrize("risk_free_rate", [-1.0, -1.1, float("inf"), float("-inf"), float("nan")])
def test_calculate_sharpe_ratio_rejects_invalid_risk_free_rates(risk_free_rate):
    with pytest.raises(ValueError, match="risk_free_rate"):
        calculate_sharpe_ratio(pd.Series([0.01, 0.02]), risk_free_rate=risk_free_rate)


@pytest.mark.parametrize("risk_free_rate", ["0.05", True])
def test_calculate_sharpe_ratio_rejects_non_numeric_risk_free_rate(risk_free_rate):
    with pytest.raises(TypeError, match="risk_free_rate"):
        calculate_sharpe_ratio(pd.Series([0.01, 0.02]), risk_free_rate=risk_free_rate)


@pytest.mark.parametrize("periods_per_year", [0, -1])
def test_calculate_sharpe_ratio_rejects_nonpositive_periods(periods_per_year):
    with pytest.raises(ValueError, match="periods_per_year"):
        calculate_sharpe_ratio(
            pd.Series([0.01, 0.02]),
            periods_per_year=periods_per_year,
        )


@pytest.mark.parametrize("periods_per_year", [1.5, "252", True])
def test_calculate_sharpe_ratio_rejects_non_integer_periods(periods_per_year):
    with pytest.raises(TypeError, match="periods_per_year"):
        calculate_sharpe_ratio(
            pd.Series([0.01, 0.02]),
            periods_per_year=periods_per_year,
        )


def test_calculate_sharpe_ratio_does_not_modify_input():
    returns = pd.Series([0.01, float("nan"), 0.03], name="period_return")
    original = returns.copy()

    calculate_sharpe_ratio(returns)

    pd.testing.assert_series_equal(returns, original)
