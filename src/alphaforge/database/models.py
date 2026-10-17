from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    Float,
    MetaData,
    String,
    Table,
)


metadata = MetaData()

market_data = Table(
    "market_data",
    metadata,
    Column("date", Date, primary_key=True),
    Column("ticker", String(32), primary_key=True),
    Column("open", Float),
    Column("high", Float),
    Column("low", Float),
    Column("close", Float),
    Column("adj_close", Float),
    Column("volume", Float),
    CheckConstraint("open IS NULL OR open > 0", name="ck_market_data_open_positive"),
    CheckConstraint("high IS NULL OR high > 0", name="ck_market_data_high_positive"),
    CheckConstraint("low IS NULL OR low > 0", name="ck_market_data_low_positive"),
    CheckConstraint("close IS NULL OR close > 0", name="ck_market_data_close_positive"),
    CheckConstraint(
        "adj_close IS NULL OR adj_close > 0",
        name="ck_market_data_adj_close_positive",
    ),
    CheckConstraint("volume IS NULL OR volume >= 0", name="ck_market_data_volume_nonnegative"),
)
