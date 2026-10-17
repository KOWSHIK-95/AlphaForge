import pandas as pd
import pytest

from alphaforge.analytics.returns import calculate_returns


def test_calculate_returns():
    prices = pd.Series([100, 110, 105, 115])

    actual = calculate_returns(prices)

    expected = pd.Series([
        float("nan"),
        0.10,
        -5 / 110,
        10 / 105,
    ])

    pd.testing.assert_series_equal(
        actual,
        expected,
        check_exact=False,
        rtol=1e-5,
    )


def test_calculate_returns_empty_series():
    prices = pd.Series([], dtype="object", name="price")

    actual = calculate_returns(prices)

    expected = pd.Series([], dtype="float64", name="price")
    pd.testing.assert_series_equal(actual, expected)


def test_calculate_returns_propagates_missing_values_without_filling():
    prices = pd.Series([100.0, float("nan"), 120.0, 132.0])
    original = prices.copy()

    actual = calculate_returns(prices)

    expected = pd.Series([float("nan"), float("nan"), float("nan"), 0.1])
    pd.testing.assert_series_equal(actual, expected, check_exact=False, rtol=1e-5)
    pd.testing.assert_series_equal(prices, original)


@pytest.mark.parametrize("prices", [[100, 0], [0, 100]])
def test_calculate_returns_rejects_zero_prices(prices):
    with pytest.raises(ValueError, match="strictly positive"):
        calculate_returns(pd.Series(prices))


@pytest.mark.parametrize("prices", [[100, -1], [-1, 100]])
def test_calculate_returns_rejects_negative_prices(prices):
    with pytest.raises(ValueError, match="strictly positive"):
        calculate_returns(pd.Series(prices))


@pytest.mark.parametrize("infinite_price", [float("inf"), float("-inf")])
def test_calculate_returns_rejects_infinite_prices(infinite_price):
    with pytest.raises(ValueError, match="infinite"):
        calculate_returns(pd.Series([100.0, infinite_price]))


@pytest.mark.parametrize(
    "prices",
    [
        pd.Series(["100", "110"]),
        pd.Series([100, "not a price"]),
        [100, 110],
    ],
)
def test_calculate_returns_rejects_invalid_inputs(prices):
    with pytest.raises(TypeError, match="prices"):
        calculate_returns(prices)