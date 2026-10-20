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

## FastAPI

Install the API and test dependencies in editable mode:

```powershell
python -m pip install -e ".[test]"
```

Start the API locally with:

```powershell
.\.venv\Scripts\python.exe -m uvicorn alphaforge.api.app:app --reload
```

Interactive documentation is available at
`http://127.0.0.1:8000/docs`; the generated OpenAPI schema is at
`/openapi.json`. The API has no startup dependency on PostgreSQL or an
external provider. Market-data requests use `YFinanceProvider` by default and
therefore need network access; tests can inject a deterministic
`MarketDataEngine`.

Available endpoints:

- `GET /health` returns `{"status": "ok"}` and checks only application health.
- `POST /market-data/history` accepts `tickers`, inclusive `start`, exclusive
  `end`, and optional `include_returns`.
- `POST /analytics` accepts a `prices` array and returns returns, drawdown,
  volatility, and Sharpe metrics where enough observations exist.
- `POST /portfolio/analytics` accepts aligned `asset_returns`, optional
  fully-invested `weights`, and optional `optimization` of
  `minimum_volatility` or `maximum_sharpe`. It returns supported risk metrics
  and correlations.
- `POST /backtests/run` accepts either inline standardized `history` or
  `tickers` with `start` and `end`, plus `initial_capital`, a
  `moving_average_crossover` strategy, transaction costs, slippage, and an
  optional benchmark ticker.

Backtests retain the engine's complete daily panel requirement, next-session
open execution, long-only positions, and accounting rules. Validation errors
use HTTP 422, an empty market-data result uses 404, and provider failures use
502. PostgreSQL is not used by these endpoints unless an application-specific
dependency is supplied; the existing repository and migrations remain
available for storage workflows.

## Dashboard

Install the optional dashboard dependencies in editable mode:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dashboard]"
```

Start the API in one terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn alphaforge.api.app:app --reload
```

Start the dashboard in another terminal:

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard/app.py
```

The dashboard provides Overview, Market Data, Portfolio Analysis, Backtesting,
and System Status pages. Market Data calls `POST /market-data/history` and
displays interactive closing-price and returns charts while preserving missing
values. Portfolio Analysis fetches prices, calculates aligned simple returns,
and calls `POST /portfolio/analytics` for supported risk metrics and
long-only minimum-volatility or maximum-Sharpe optimization. Incomplete
observations are reported and never forward-filled. Backtesting calls
`POST /backtests/run` using only the moving-average crossover strategy and
displays the metrics and time series returned by the API. Backtests preserve
the engine's next-session-open execution, complete-panel requirement, and
long-only behavior. System Status checks application liveness through
`GET /health`; it does not claim PostgreSQL or provider readiness.

All date ranges use an inclusive start and exclusive end. The API base URL
defaults to `http://127.0.0.1:8000` and can be changed with
`ALPHAFORGE_API_URL`. The dashboard does not connect directly to PostgreSQL
and does not expose database credentials. Ordinary dashboard tests use mocked
HTTP responses and do not require an API, database, or internet connection.

## Next.js Frontend

The repository also includes a separate production-oriented frontend in
`frontend/`. It uses Next.js App Router, React, TypeScript, Tailwind CSS,
Plotly, and Lucide icons. It communicates with FastAPI over HTTP and does not
connect directly to PostgreSQL or market-data providers. The existing
Streamlit dashboard remains available as a fallback.

Prerequisites:

- Node.js 20 or newer.
- The AlphaForge Python dependencies installed.
- The FastAPI service running for live data.

Install and configure the frontend:

```powershell
cd frontend
npm install
Copy-Item .env.example .env.local
```

Set `NEXT_PUBLIC_API_URL` in `frontend/.env.local` if the API is not running
at `http://127.0.0.1:8000`.

Start the frontend:

```powershell
cd frontend
npm run dev
```

Open `http://localhost:3000`. Available routes are `/`, `/market-data`,
`/portfolio`, `/backtesting`, and `/system`.

Frontend checks:

```powershell
cd frontend
npm run typecheck
npm run lint
npm test
npm run build
```

The frontend uses the existing API contracts. Portfolio analysis first
fetches market data, aligns complete simple-return observations, and then
calls `/portfolio/analytics`. Backtesting exposes only the existing
moving-average crossover strategy. Live market-provider behavior and
PostgreSQL readiness require the backend's own configuration and are not
claimed by the frontend without an explicit API response.