# AlphaForge

AlphaForge is a quantitative finance project I'm building to explore
how mathematics, programming, and data analysis can be used to understand
financial markets.

The goal is to build a platform that analyzes market data, measures
portfolio risk, and tests trading strategies using historical data.

## Tech Stack

- Python
- Pandas and NumPy
- PostgreSQL
- FastAPI
- Streamlit and Plotly

## What I'm Working On

- Analyzing stock market data
- Calculating returns and risk metrics
- Exploring portfolio optimization
- Backtesting trading strategies
- Building an interactive dashboard

## Status

The analytics package includes return, volatility, Sharpe ratio, and
drawdown calculations. Market data can be fetched as daily bars, validated,
optionally enriched with returns, and stored in PostgreSQL.

## Market Data

`MarketDataEngine` accepts a provider and an optional PostgreSQL repository.
The included `YFinanceProvider` fetches daily bars; other providers can
implement the same provider interface. Results use one row per ticker and
market date, with `date`, `ticker`, OHLC, adjusted close, and volume columns.
Date ranges use an inclusive start and exclusive end.

Missing observations are preserved. Exact duplicate ticker/date rows are
deduplicated, while conflicting duplicates and non-positive or non-finite
prices are rejected. Returns are calculated per ticker using the existing
analytics implementation, preferring adjusted close when available and
otherwise using close.

Install the market-data dependencies with the project and set
`ALPHAFORGE_DATABASE_URL` to a PostgreSQL SQLAlchemy URL using the psycopg
driver, for example `postgresql+psycopg://...`. Do not commit database
credentials. Apply schema migrations with `alembic upgrade head`.

Install the package and test tools in editable mode with
`python -m pip install -e ".[test]"`.

PostgreSQL repository integration tests run only when
`ALPHAFORGE_TEST_DATABASE_URL` points to a disposable test database.