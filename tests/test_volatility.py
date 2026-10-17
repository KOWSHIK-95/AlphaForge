import math

import pandas as pd
import pytest

from alphaforge.analytics.volatility import calculate_volatility


def test_calculate_volatility_uses_sample_standard_deviation():
    returns = pd.Series([0.01, 0.02, -0.01])

    actual = calculate_volatility(returns)

    assert actual == pytest.approx(returns.std(ddof=1))


def test_calculate_volatility_annualizes_daily_volatility():
    returns = pd.Series([0.01, 0.02, -0.01])

    actual = calculate_volatility(returns, annualize=True)

    assert actual == pytest.approx(returns.std(ddof=1) * math.sqrt(252))


def test_calculate_volatility_ignores_missing_values():
    returns = pd.Series([0.01, float("nan"), 0.03, 0.02])

    actual = calculate_volatility(returns)

    assert actual == pytest.approx(pd.Series([0.01, 0.03, 0.02]).std(ddof=1))


@pytest.mark.parametrize(
    "returns",
    [
        [0.01, 0.02],
        pd.Series(["0.01", "0.02"]),
        pd.Series([0.01, "invalid"]),
    ],
)
def test_calculate_volatility_rejects_invalid_inputs(returns):
    with pytest.raises(TypeError, match="returns"):
        calculate_volatility(returns)


@pytest.mark.parametrize("infinite_value", [float("inf"), float("-inf")])
def test_calculate_volatility_rejects_infinite_values(infinite_value):
    with pytest.raises(ValueError, match="infinite"):
        calculate_volatility(pd.Series([0.01, infinite_value]))


@pytest.mark.parametrize(
    "returns",
    [
        pd.Series([], dtype="float64"),
        pd.Series([float("nan"), float("nan")]),
        pd.Series([0.01]),
        pd.Series([0.01, float("nan")]),
    ],
)
def test_calculate_volatility_requires_two_valid_observations(returns):
    with pytest.raises(ValueError, match="at least two"):
        calculate_volatility(returns)


def test_calculate_volatility_does_not_modify_input():
    returns = pd.Series([0.01, float("nan"), 0.03], name="daily_return")
    original = returns.copy()

    calculate_volatility(returns)

    pd.testing.assert_series_equal(returns, original)
