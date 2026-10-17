import pandas as pd
import pytest

from alphaforge.data.engine import MarketDataEngine


class FakeProvider:
    def __init__(self, history):
        self.history = history
        self.request = None

    def fetch_history(self, tickers, start, end):
        self.request = (tickers, start, end)
        dates = pd.to_datetime(self.history["date"])
        selected = self.history.loc[
            self.history["ticker"].str.upper().isin(tickers)
            & dates.ge(pd.Timestamp(start))
            & dates.lt(pd.Timestamp(end))
        ]
        return selected.copy()


class UnfilteredProvider(FakeProvider):
    def fetch_history(self, tickers, start, end):
        self.request = (tickers, start, end)
        return self.history.copy()


class FakeRepository:
    def __init__(self, history):
        self.history = history
        self.stored = None
        self.request = None

    def upsert_history(self, history):
        self.stored = history.copy()

    def get_history(self, tickers, start, end):
        self.request = (tickers, start, end)
        dates = pd.to_datetime(self.history["date"])
        selected = self.history.loc[
            self.history["ticker"].str.upper().isin(tickers)
            & dates.ge(pd.Timestamp(start))
            & dates.lt(pd.Timestamp(end))
        ]
        return selected.copy()


@pytest.fixture
def sample_history():
    return pd.DataFrame(
        {
            "date": ["2025-01-02", "2025-01-03", "2025-01-02", "2025-01-03"],
            "ticker": ["AAPL", "AAPL", "MSFT", "MSFT"],
            "close": [100.0, 110.0, 50.0, 55.0],
            "adj_close": [100.0, 110.0, 50.0, 55.0],
        }
    )


def test_engine_fetches_multiple_tickers_and_calculates_returns(sample_history):
    provider = FakeProvider(sample_history)
    engine = MarketDataEngine(provider)

    actual = engine.fetch_history(
        ["aapl", "msft", "AAPL"],
        "2025-01-01",
        "2025-02-01",
        include_returns=True,
    )

    assert provider.request == (["AAPL", "MSFT"], pd.Timestamp("2025-01-01").date(), pd.Timestamp("2025-02-01").date())
    assert list(actual["returns"].iloc[[1, 3]]) == pytest.approx([0.1, 0.1])
    assert pd.isna(actual.loc[0, "returns"])


def test_engine_fetch_and_store_stores_validated_data(sample_history):
    repository = FakeRepository(sample_history)
    engine = MarketDataEngine(FakeProvider(sample_history), repository)

    actual = engine.fetch_and_store(["AAPL"], "2025-01-01", "2025-02-01")

    assert repository.stored is not None
    assert "returns" not in repository.stored.columns
    assert list(actual["ticker"]) == ["AAPL", "AAPL"]


def test_engine_loads_stored_history_and_can_add_returns(sample_history):
    repository = FakeRepository(sample_history)
    engine = MarketDataEngine(FakeProvider(sample_history), repository)

    actual = engine.get_history(
        ["aapl"],
        "2025-01-01",
        "2025-02-01",
        include_returns=True,
    )

    assert repository.request[0] == ["AAPL"]
    assert list(actual["ticker"]) == ["AAPL", "AAPL"]
    assert actual["returns"].iloc[1] == pytest.approx(0.1)


def test_engine_returns_preserve_gaps_and_fall_back_to_close():
    history = pd.DataFrame(
        {
            "date": ["2025-01-02", "2025-01-03", "2025-01-04", "2025-01-05"],
            "ticker": ["AAPL"] * 4,
            "close": [100.0, float("nan"), 120.0, 132.0],
            "adj_close": [float("nan")] * 4,
        }
    )
    engine = MarketDataEngine(FakeProvider(history))

    actual = engine.fetch_history(
        ["AAPL"],
        "2025-01-01",
        "2025-02-01",
        include_returns=True,
    )

    assert pd.isna(actual["returns"].iloc[:3]).all()
    assert actual["returns"].iloc[3] == pytest.approx(0.1)


def test_engine_validates_tickers_and_date_range(sample_history):
    engine = MarketDataEngine(FakeProvider(sample_history))

    with pytest.raises(ValueError, match="at least one ticker"):
        engine.fetch_history([], "2025-01-01", "2025-02-01")
    with pytest.raises(ValueError, match="earlier"):
        engine.fetch_history(["AAPL"], "2025-02-01", "2025-01-01")
    with pytest.raises(ValueError, match="valid dates"):
        engine.fetch_history(["AAPL"], None, "2025-02-01")


def test_engine_rejects_provider_data_outside_requested_scope():
    unexpected_ticker = UnfilteredProvider(
        pd.DataFrame(
            {"date": ["2025-01-02"], "ticker": ["MSFT"], "close": [100.0]}
        )
    )
    engine = MarketDataEngine(unexpected_ticker)
    with pytest.raises(ValueError, match="unrequested tickers"):
        engine.fetch_history(["AAPL"], "2025-01-01", "2025-02-01")

    out_of_range = UnfilteredProvider(
        pd.DataFrame(
            {"date": ["2025-02-02"], "ticker": ["AAPL"], "close": [100.0]}
        )
    )
    engine = MarketDataEngine(out_of_range)
    with pytest.raises(ValueError, match="outside the requested date range"):
        engine.fetch_history(["AAPL"], "2025-01-01", "2025-02-01")


def test_engine_requires_repository_for_storage():
    engine = MarketDataEngine(FakeProvider(pd.DataFrame()))

    with pytest.raises(RuntimeError, match="MarketDataRepository"):
        engine.fetch_and_store(["AAPL"], "2025-01-01", "2025-02-01")
