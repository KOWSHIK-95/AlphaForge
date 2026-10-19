"""Public result and execution record models for backtests."""

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Trade:
    """A simulated order fill, with execution price excluding transaction fee."""

    date: pd.Timestamp
    ticker: str
    side: str
    quantity: float
    price: float
    transaction_cost: float
    realized_pnl: float


@dataclass(frozen=True)
class BacktestResult:
    """Time series and performance statistics produced by a backtest."""

    equity: pd.Series
    cash: pd.Series
    positions: pd.DataFrame
    realized_pnl: pd.Series
    unrealized_pnl: pd.Series
    trades: pd.DataFrame
    returns: pd.Series
    cumulative_returns: pd.Series
    annualized_return: float | None
    annualized_volatility: float | None
    sharpe_ratio: float | None
    max_drawdown: float
    benchmark_equity: pd.Series | None
    benchmark_cumulative_returns: pd.Series | None
    benchmark_annualized_return: float | None
