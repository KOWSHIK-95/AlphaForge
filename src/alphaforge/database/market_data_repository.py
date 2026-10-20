from collections.abc import Sequence
from datetime import date, datetime

import pandas as pd
from sqlalchemy import Engine, select
from sqlalchemy.dialects.postgresql import insert

from alphaforge.data.validation import (
    MARKET_DATA_COLUMNS,
    normalize_tickers,
    validate_market_data,
)
from alphaforge.database.models import market_data


class MarketDataRepository:
    """Persist and retrieve validated daily bars in PostgreSQL."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def upsert_history(self, history: pd.DataFrame) -> None:
        """Insert or update daily bars, keyed by ticker and market date."""
        normalized = validate_market_data(history)
        if normalized.empty:
            return

        records = normalized.loc[:, MARKET_DATA_COLUMNS].copy()
        records["date"] = records["date"].dt.date
        rows = records.astype(object).where(pd.notna(records), None).to_dict(orient="records")
        update_columns = {
            column: getattr(insert(market_data).excluded, column)
            for column in MARKET_DATA_COLUMNS
            if column not in {"date", "ticker"}
        }

        with self._engine.begin() as connection:
            for start in range(0, len(rows), 1000):
                statement = insert(market_data).values(rows[start : start + 1000])
                statement = statement.on_conflict_do_update(
                    index_elements=[market_data.c.ticker, market_data.c.date],
                    set_=update_columns,
                )
                connection.execute(statement)

    def get_history(
        self,
        tickers: Sequence[str],
        start: date | datetime | str,
        end: date | datetime | str,
    ) -> pd.DataFrame:
        """Retrieve daily bars for requested tickers and ``[start, end)``."""
        symbols = normalize_tickers(tickers)
        start_date, end_date = _validate_date_range(start, end)
        statement = (
            select(market_data)
            .where(
                market_data.c.ticker.in_(symbols),
                market_data.c.date >= start_date,
                market_data.c.date < end_date,
            )
            .order_by(market_data.c.ticker, market_data.c.date)
        )
        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return validate_market_data(pd.DataFrame(rows, columns=MARKET_DATA_COLUMNS))


def _validate_date_range(
    start: date | datetime | str,
    end: date | datetime | str,
) -> tuple[date, date]:
    if start is None or end is None:
        raise ValueError("start and end must be valid dates.")
    try:
        start_timestamp = pd.Timestamp(start)
        end_timestamp = pd.Timestamp(end)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("start and end must be valid dates.") from error
    if pd.isna(start_timestamp) or pd.isna(end_timestamp):
        raise ValueError("start and end must be valid dates.")
    start_date = start_timestamp.date()
    end_date = end_timestamp.date()
    if start_date >= end_date:
        raise ValueError("start must be earlier than end.")
    return start_date, end_date
