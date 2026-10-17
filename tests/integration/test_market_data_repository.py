import os

import pandas as pd
import pytest
from sqlalchemy import create_engine, delete, func, select

from alphaforge.database.market_data_repository import MarketDataRepository
from alphaforge.database.models import market_data, metadata


DATABASE_URL = os.environ.get("ALPHAFORGE_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="set ALPHAFORGE_TEST_DATABASE_URL to run PostgreSQL integration tests",
)


@pytest.fixture
def repository():
    engine = create_engine(DATABASE_URL)
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(delete(market_data).where(market_data.c.ticker == "TESTALPHA"))
    yield MarketDataRepository(engine), engine
    with engine.begin() as connection:
        connection.execute(delete(market_data).where(market_data.c.ticker == "TESTALPHA"))
    engine.dispose()


def test_repository_upsert_is_idempotent_and_retrieves_date_range(repository):
    repo, engine = repository
    bars = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-01-02", "2025-01-03"]),
            "ticker": ["TESTALPHA", "TESTALPHA"],
            "open": [100.0, 101.0],
            "high": [102.0, 103.0],
            "low": [99.0, 100.0],
            "close": [101.0, 102.0],
            "adj_close": [101.0, 102.0],
            "volume": [float("nan"), 1200.0],
        }
    )
    repo.upsert_history(bars)
    updated_bars = bars.copy()
    updated_bars.loc[0, "close"] = 105.0
    repo.upsert_history(updated_bars)

    retrieved = repo.get_history(["TESTALPHA"], "2025-01-02", "2025-01-04")
    with engine.connect() as connection:
        row_count = connection.scalar(
            select(func.count()).select_from(market_data).where(
                market_data.c.ticker == "TESTALPHA"
            )
        )
        missing_volume_count = connection.scalar(
            select(func.count()).select_from(market_data).where(
                market_data.c.ticker == "TESTALPHA",
                market_data.c.date == pd.Timestamp("2025-01-02").date(),
                market_data.c.volume.is_(None),
            )
        )

    assert row_count == 2
    assert missing_volume_count == 1
    assert list(retrieved["close"]) == [105.0, 102.0]
