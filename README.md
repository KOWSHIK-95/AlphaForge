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

## Portfolio Analytics

`alphaforge.analytics.portfolio` provides weighted portfolio returns,
cumulative returns, volatility, Sharpe ratio, maximum drawdown, asset
correlations, historical VaR/CVaR, and long-only minimum-volatility and
maximum-Sharpe optimizers. Portfolio inputs are pandas objects with aligned,
complete observations; missing and non-finite data are rejected rather than
filled or silently dropped. Weights supplied for return calculations must
sum to one and may be short; optimizer weights are long-only and sum to one.

Portfolio volatility uses sample standard deviation and can be annualized by
`sqrt(periods_per_year)` (252 by default). Sharpe uses the existing analytics
convention: the effective annual risk-free rate is converted to a periodic
rate, and the resulting ratio is annualized. Optimizer expected annual return
is the arithmetic mean periodic return multiplied by periods per year.
Optimization and performance estimates use historical observations only and
do not use future data.

Historical VaR and CVaR are expressed as nonnegative loss fractions, not
signed returns. VaR negates the empirical lower-tail return quantile; CVaR
negates the average return at or below that quantile. Both use a confidence
level strictly between zero and one. Optimization uses SciPy's SLSQP solver
and sample covariance.

## Backtesting

`alphaforge.backtesting.BacktestEngine` accepts validated daily bars directly,
or can fetch them with its `run_from_market_data` method, which delegates to
the existing `MarketDataEngine`. Strategies implement
`generate_target_weights(history)` and return long-only target
weights keyed by ticker; weights may sum to less than one to retain cash.
`MovingAverageCrossoverStrategy` is the initial example and equal-weights
assets whose short simple moving average is above their long moving average.

The timing convention is strict: on date *t*, the strategy receives bars only
through the close of *t*. Its targets can first be executed at the open of the
next available bar. The engine requires open prices for execution and close
prices for end-of-day valuation; it never substitutes one for the other.
Backtests support fractional shares, long-only positions, proportional
transaction costs, and adverse buy/sell slippage. Benchmark comparisons use a
buy-and-hold benchmark valued at close, starting with the same capital on the
first simulation date. Annualization assumes `periods_per_year` observations
per year (252 by default); annualized return is compounded over elapsed
periods, while volatility and Sharpe reuse the portfolio analytics
conventions.