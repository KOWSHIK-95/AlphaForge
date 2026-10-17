from unittest.mock import patch

import pandas as pd
import pytest

from alphaforge.data.providers import YFinanceProvider


def test_yfinance_provider_maps_multiindex_ticker_data_to_standard_rows():
    columns = pd.MultiIndex.from_product(
        [["AAPL", "MSFT"], ["Open", "High", "Low", "Close", "Adj Close", "Volume"]]
    )
    downloaded = pd.DataFrame(
        [[100, 102, 99, 101, 100.5, 1000, 200, 203, 199, 202, 202, 2000]],
        index=pd.DatetimeIndex(["2025-01-02"], name="Date"),
        columns=columns,
    )
    with patch("alphaforge.data.providers.yf.download", return_value=downloaded) as download:
        actual = YFinanceProvider().fetch_history(
            ["aapl", "msft"], "2025-01-01", "2025-01-03"
        )

    assert list(actual["ticker"]) == ["AAPL", "MSFT"]
    assert list(actual["close"]) == [101, 202]
    download.assert_called_once()
    assert download.call_args.kwargs["auto_adjust"] is False


def test_yfinance_provider_maps_single_ticker_data():
    downloaded = pd.DataFrame(
        {"Open": [100], "Close": [101], "Adj Close": [100.5], "Volume": [500]},
        index=pd.DatetimeIndex(["2025-01-02"], name="Date"),
    )
    with patch("alphaforge.data.providers.yf.download", return_value=downloaded):
        actual = YFinanceProvider().fetch_history(["AAPL"], "2025-01-01", "2025-01-03")

    assert actual.loc[0, "ticker"] == "AAPL"
    assert actual.loc[0, "adj_close"] == 100.5


def test_yfinance_provider_surfaces_download_errors_with_context():
    with patch(
        "alphaforge.data.providers.yf.download",
        side_effect=OSError("network unavailable"),
    ):
        with pytest.raises(RuntimeError, match="yfinance failed") as error:
            YFinanceProvider().fetch_history(["AAPL"], "2025-01-01", "2025-01-03")

    assert isinstance(error.value.__cause__, OSError)
