import pandas as pd
import pytest
from sqlalchemy import create_engine

import alphaforge.database.connection as database_connection
from alphaforge.database.market_data_repository import MarketDataRepository


def test_create_database_engine_requires_postgresql_configuration(monkeypatch):
    monkeypatch.delenv("ALPHAFORGE_DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="ALPHAFORGE_DATABASE_URL"):
        database_connection.create_database_engine()

    monkeypatch.setenv("ALPHAFORGE_DATABASE_URL", "sqlite:///local.db")
    with pytest.raises(ValueError, match="postgresql\\+psycopg"):
        database_connection.create_database_engine()


def test_create_database_engine_configures_pre_ping(monkeypatch):
    captured = {}

    def fake_create_engine(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(database_connection, "create_engine", fake_create_engine)
    monkeypatch.setenv(
        "ALPHAFORGE_DATABASE_URL",
        "postgresql+psycopg://user:password@example.test/alphaforge",
    )

    assert database_connection.create_database_engine() is not None
    assert captured == {
        "url": "postgresql+psycopg://user:password@example.test/alphaforge",
        "kwargs": {"pool_pre_ping": True},
    }


class FailingEngine:
    def connect(self):
        raise AssertionError("database should not be contacted")


@pytest.fixture
def repository():
    return MarketDataRepository(FailingEngine())


@pytest.mark.parametrize(
    ("tickers", "start", "end", "message"),
    [
        ([], "2025-01-01", "2025-02-01", "at least one ticker"),
        ([" "], "2025-01-01", "2025-02-01", "must not be empty"),
        (["AAPL"], "2025-02-01", "2025-01-01", "earlier"),
        (["AAPL"], "not-a-date", "2025-02-01", "valid dates"),
        (["AAPL"], None, "2025-02-01", "valid dates"),
    ],
)
def test_repository_rejects_invalid_read_parameters_before_connecting(
    repository,
    tickers,
    start,
    end,
    message,
):
    with pytest.raises((TypeError, ValueError), match=message):
        repository.get_history(tickers, start, end)


def test_repository_upsert_validates_data_before_connecting(repository):
    invalid = pd.DataFrame(
        {
            "date": ["2025-01-02"],
            "ticker": ["AAPL"],
            "close": [0.0],
        }
    )
    with pytest.raises(ValueError, match="positive"):
        repository.upsert_history(invalid)


def test_postgresql_dialect_can_compile_repository_upsert():
    from alphaforge.database.models import market_data
    from sqlalchemy.dialects.postgresql import dialect, insert

    statement = insert(market_data).values(
        date=pd.Timestamp("2025-01-02").date(),
        ticker="AAPL",
        close=100.0,
    ).on_conflict_do_update(
        index_elements=[market_data.c.ticker, market_data.c.date],
        set_={"close": insert(market_data).excluded.close},
    )
    compiled = str(statement.compile(dialect=dialect()))
    assert "ON CONFLICT (ticker, date) DO UPDATE" in compiled


def test_sqlalchemy_can_create_an_isolated_schema_from_metadata():
    from alphaforge.database.models import metadata

    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    assert "market_data" in metadata.tables
    engine.dispose()
