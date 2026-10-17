import pandas as pd
import pytest

from alphaforge.analytics.drawdown import (
    calculate_drawdown,
    calculate_max_drawdown,
)


def test_calculate_drawdown_computes_declines_from_running_peak():
    prices = pd.Series([100.0, 120.0, 90.0, 96.0])

    actual = calculate_drawdown(prices)

    expected = pd.Series([0.0, 0.0, -0.25, -0.2])
    pd.testing.assert_series_equal(actual, expected)


def test_calculate_drawdown_resets_to_zero_at_new_peak():
    prices = pd.Series([100.0, 80.0, 110.0, 105.0])

    actual = calculate_drawdown(prices)

    expected = pd.Series([0.0, -0.2, 0.0, -5 / 110])
    pd.testing.assert_series_equal(actual, expected)


def test_calculate_drawdown_returns_zero_after_recovery():
    prices = pd.Series([100.0, 80.0, 100.0])

    actual = calculate_drawdown(prices)

    assert actual.iloc[-1] == 0.0


def test_calculate_drawdown_preserves_missing_prices_and_running_peak():
    prices = pd.Series([100.0, 80.0, float("nan"), 90.0, 110.0, float("nan")])

    actual = calculate_drawdown(prices)

    expected = pd.Series([0.0, -0.2, float("nan"), -0.1, 0.0, float("nan")])
    pd.testing.assert_series_equal(actual, expected)


def test_calculate_max_drawdown_ignores_missing_observations():
    prices = pd.Series([100.0, float("nan"), 80.0, float("nan"), 90.0])

    assert calculate_max_drawdown(prices) == pytest.approx(-0.2)


def test_calculate_max_drawdown_returns_nan_when_all_prices_are_missing():
    prices = pd.Series([float("nan"), float("nan")])

    assert pd.isna(calculate_max_drawdown(prices))


@pytest.mark.parametrize("prices", [[100, 90], None, "100,90"])
def test_drawdown_functions_reject_non_series_inputs(prices):
    with pytest.raises(TypeError, match="prices"):
        calculate_drawdown(prices)
    with pytest.raises(TypeError, match="prices"):
        calculate_max_drawdown(prices)


@pytest.mark.parametrize(
    "prices",
    [
        pd.Series(["100", "90"]),
        pd.Series([100, "invalid"]),
        pd.Series([True, False]),
    ],
)
def test_drawdown_functions_reject_non_numeric_prices(prices):
    with pytest.raises(TypeError, match="prices"):
        calculate_drawdown(prices)
    with pytest.raises(TypeError, match="prices"):
        calculate_max_drawdown(prices)


@pytest.mark.parametrize(
    "invalid_price",
    [float("inf"), float("-inf"), 0.0, -1.0],
)
def test_drawdown_functions_reject_invalid_prices(invalid_price):
    prices = pd.Series([100.0, invalid_price])

    with pytest.raises(ValueError):
        calculate_drawdown(prices)
    with pytest.raises(ValueError):
        calculate_max_drawdown(prices)


def test_calculate_drawdown_preserves_input_index_and_name():
    index = pd.Index(["open", "dip", "recovery"], name="observation")
    prices = pd.Series([100.0, 80.0, 100.0], index=index, name="portfolio")

    actual = calculate_drawdown(prices)

    assert actual.index.equals(index)
    assert actual.name == prices.name


def test_drawdown_functions_do_not_modify_input():
    prices = pd.Series([100.0, float("nan"), 80.0, 90.0], name="portfolio")
    original = prices.copy()

    calculate_drawdown(prices)
    calculate_max_drawdown(prices)

    pd.testing.assert_series_equal(prices, original)
