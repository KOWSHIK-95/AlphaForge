"""Adapters that translate engine results into JSON-safe API values."""

from typing import Any

import pandas as pd

from alphaforge.analytics.drawdown import calculate_drawdown, calculate_max_drawdown
from alphaforge.analytics.portfolio import (
    calculate_asset_correlation,
    calculate_cumulative_returns,
    calculate_historical_cvar,
    calculate_historical_var,
    calculate_portfolio_max_drawdown,
    calculate_portfolio_returns,
    calculate_portfolio_sharpe_ratio,
    calculate_portfolio_volatility,
    optimize_maximum_sharpe,
    optimize_minimum_volatility,
)
from alphaforge.analytics.returns import calculate_returns
from alphaforge.backtesting import BacktestEngine, ExecutionModel, MovingAverageCrossoverStrategy
from alphaforge.data.engine import MarketDataEngine
from alphaforge.data.validation import validate_market_data

from alphaforge.api.models import AnalyticsRequest, BacktestRequest, PortfolioRequest


def frame_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    records = frame.copy()
    for column in records.columns:
        if pd.api.types.is_datetime64_any_dtype(records[column]):
            records[column] = records[column].dt.strftime("%Y-%m-%d")
    return records.astype(object).where(pd.notna(records), None).to_dict("records")


def series_values(series: pd.Series) -> list[Any]:
    values = series.tolist()
    return [None if pd.isna(value) else float(value) for value in values]


def fetch_market_data(engine: MarketDataEngine, request: Any) -> dict[str, Any]:
    history = engine.fetch_history(
        request.tickers,
        request.start,
        request.end,
        include_returns=request.include_returns,
    )
    if history.empty:
        raise LookupError("no market data was returned for the requested range.")
    return {"data": frame_records(history), "count": len(history)}


def calculate_analytics(request: AnalyticsRequest) -> dict[str, Any]:
    prices = pd.Series(request.prices, dtype="float64", name="price")
    if prices.dropna().empty:
        raise ValueError("prices must contain at least one valid observation.")
    returns = calculate_returns(prices)
    valid_returns = returns.dropna()
    result: dict[str, Any] = {
        "returns": series_values(returns),
        "drawdown": series_values(calculate_drawdown(prices)),
        "max_drawdown": calculate_max_drawdown(prices),
    }
    if len(valid_returns) >= 2:
        result["volatility"] = calculate_portfolio_volatility(valid_returns)
        result["annualized_volatility"] = calculate_portfolio_volatility(
            valid_returns, annualize=True
        )
        result["sharpe_ratio"] = calculate_portfolio_sharpe_ratio(
            valid_returns,
            risk_free_rate=request.risk_free_rate,
            periods_per_year=request.periods_per_year,
        )
    else:
        result.update(
            volatility=None,
            annualized_volatility=None,
            sharpe_ratio=None,
        )
    return result


def calculate_portfolio(request: PortfolioRequest) -> dict[str, Any]:
    asset_returns = pd.DataFrame(request.asset_returns)
    weights = pd.Series(request.weights, dtype="float64") if request.weights else None
    result: dict[str, Any] = {}
    if weights is not None:
        portfolio_returns = calculate_portfolio_returns(asset_returns, weights)
        result.update(
            returns=series_values(portfolio_returns),
            cumulative_returns=series_values(calculate_cumulative_returns(portfolio_returns)),
            volatility=calculate_portfolio_volatility(portfolio_returns),
            annualized_volatility=calculate_portfolio_volatility(
                portfolio_returns, annualize=True
            ),
            sharpe_ratio=calculate_portfolio_sharpe_ratio(
                portfolio_returns,
                risk_free_rate=request.risk_free_rate,
                periods_per_year=request.periods_per_year,
            ),
            max_drawdown=calculate_portfolio_max_drawdown(portfolio_returns),
            var=calculate_historical_var(portfolio_returns, request.confidence_level),
            cvar=calculate_historical_cvar(portfolio_returns, request.confidence_level),
        )
    result["correlation"] = (
        calculate_asset_correlation(asset_returns).to_dict()
        if asset_returns.shape[1] >= 2
        else {}
    )
    if request.optimization != "none":
        optimizer = (
            optimize_minimum_volatility
            if request.optimization == "minimum_volatility"
            else optimize_maximum_sharpe
        )
        if request.optimization == "maximum_sharpe":
            optimized = optimizer(
                asset_returns,
                risk_free_rate=request.risk_free_rate,
                periods_per_year=request.periods_per_year,
            )
        else:
            optimized = optimizer(asset_returns, periods_per_year=request.periods_per_year)
        optimized_returns = calculate_portfolio_returns(asset_returns, optimized.weights)
        result["optimization"] = {
            "weights": {str(key): float(value) for key, value in optimized.weights.items()},
            "expected_annual_return": optimized.expected_annual_return,
            "annualized_volatility": optimized.annualized_volatility,
            "sharpe_ratio": optimized.sharpe_ratio,
        }
        result.update(
            returns=series_values(optimized_returns),
            cumulative_returns=series_values(calculate_cumulative_returns(optimized_returns)),
            volatility=calculate_portfolio_volatility(optimized_returns),
            annualized_volatility=calculate_portfolio_volatility(
                optimized_returns, annualize=True
            ),
            sharpe_ratio=calculate_portfolio_sharpe_ratio(
                optimized_returns,
                risk_free_rate=request.risk_free_rate,
                periods_per_year=request.periods_per_year,
            ),
            max_drawdown=calculate_portfolio_max_drawdown(optimized_returns),
            var=calculate_historical_var(optimized_returns, request.confidence_level),
            cvar=calculate_historical_cvar(optimized_returns, request.confidence_level),
        )
    return result


def run_backtest(
    request: BacktestRequest,
    market_data_engine: MarketDataEngine,
) -> dict[str, Any]:
    strategy = MovingAverageCrossoverStrategy(
        request.strategy.short_window,
        request.strategy.long_window,
    )
    engine = BacktestEngine(
        request.initial_capital,
        execution_model=ExecutionModel(
            transaction_cost_rate=request.transaction_cost_rate,
            slippage_rate=request.slippage_rate,
        ),
        risk_free_rate=request.risk_free_rate,
        periods_per_year=request.periods_per_year,
    )
    if request.history is not None:
        history = validate_market_data(
            pd.DataFrame([bar.model_dump(exclude_none=True) for bar in request.history])
        )
        result = engine.run(history, strategy, benchmark_ticker=request.benchmark_ticker)
    else:
        result = engine.run_from_market_data(
            market_data_engine,
            strategy,
            request.tickers or [],
            request.start,
            request.end,
            benchmark_ticker=request.benchmark_ticker,
        )
    response: dict[str, Any] = {
        "metrics": {
            "annualized_return": result.annualized_return,
            "annualized_volatility": result.annualized_volatility,
            "sharpe_ratio": result.sharpe_ratio,
            "max_drawdown": result.max_drawdown,
            "benchmark_annualized_return": result.benchmark_annualized_return,
        },
        "equity": _indexed_series(result.equity),
        "cash": _indexed_series(result.cash),
        "positions": _indexed_frame(result.positions),
        "returns": _indexed_series(result.returns),
        "cumulative_returns": _indexed_series(result.cumulative_returns),
        "trades": frame_records(result.trades),
    }
    if result.benchmark_equity is not None:
        response["benchmark_equity"] = _indexed_series(result.benchmark_equity)
    return response


def _indexed_series(series: pd.Series) -> list[dict[str, Any]]:
    return [
        {"date": pd.Timestamp(index).strftime("%Y-%m-%d"), "value": float(value)}
        for index, value in series.items()
    ]


def _indexed_frame(frame: pd.DataFrame) -> list[dict[str, Any]]:
    result = frame.reset_index()
    return frame_records(result)
