import pandas as pd
import pytest

from alphaforge.data.validation import normalize_tickers, validate_market_data


def _bars(**overrides):
    row = {
        "date": "2025-01-02",
        "ticker": " aapl ",
        "open": 99.0,
        "high": 102.0,
        "low": 98.0,
        "close": 100.0,
        "adj_close": 100.0,
        "volume": 1000,
    }
    row.update(overrides)
    return pd.DataFrame([row])


def test_validation_normalizes_tickers_and_sorts_bars():
    data = pd.concat(
        [
            _bars(date="2025-01-03", ticker="msft"),
            _bars(date="2025-01-02", ticker="aapl"),
        ],
        ignore_index=True,
    )

    actual = validate_market_data(data)

    assert list(actual.columns) == [
        "date", "ticker", "open", "high", "low", "close", "adj_close", "volume"
    ]
    assert list(zip(actual["ticker"], actual["date"].dt.strftime("%Y-%m-%d"))) == [
        ("AAPL", "2025-01-02"),
        ("MSFT", "2025-01-03"),
    ]


def test_validation_deduplicates_exact_rows_and_preserves_missing_values():
    row = _bars(close=float("nan"), adj_close=float("nan"))
    data = pd.concat([row, row], ignore_index=True)

    actual = validate_market_data(data)

    assert len(actual) == 1
    assert pd.isna(actual.loc[0, "close"])


def test_validation_rejects_conflicting_duplicate_keys():
    data = pd.concat([_bars(), _bars(close=101.0)], ignore_index=True)

    with pytest.raises(ValueError, match="conflicting"):
        validate_market_data(data)


@pytest.mark.parametrize("bad_price", [0.0, -1.0, float("inf"), float("-inf")])
def test_validation_rejects_invalid_prices(bad_price):
    with pytest.raises(ValueError):
        validate_market_data(_bars(close=bad_price))


def test_validation_rejects_non_numeric_prices():
    with pytest.raises(TypeError, match="close"):
        validate_market_data(_bars(close="100"))


def test_validation_rejects_invalid_dates_and_missing_close_column():
    with pytest.raises(ValueError, match="date"):
        validate_market_data(_bars(date="not-a-date"))
    with pytest.raises(ValueError, match="missing"):
        validate_market_data(_bars(date=None))
    with pytest.raises(ValueError, match="close"):
        validate_market_data(pd.DataFrame({"date": ["2025-01-02"], "ticker": ["AAPL"]}))


def test_normalize_tickers_validates_and_deduplicates():
    assert normalize_tickers([" aapl ", "MSFT", "AAPL"]) == ["AAPL", "MSFT"]

    with pytest.raises(TypeError):
        normalize_tickers("AAPL")
    with pytest.raises(ValueError):
        normalize_tickers([])
    with pytest.raises(ValueError):
        normalize_tickers([" "])
