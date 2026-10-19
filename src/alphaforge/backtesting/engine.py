"""Chronological daily backtesting with next-session-open execution."""

from collections.abc import Sequence
from datetime import date, datetime
import math
from numbers import Integral, Real

import numpy as np
import pandas as pd

from alphaforge.analytics.drawdown import calculate_max_drawdown
from alphaforge.analytics.portfolio import (
    calculate_cumulative_returns,
    calculate_portfolio_sharpe_ratio,
    calculate_portfolio_volatility,
)
from alphaforge.backtesting.accounting import SimulatedPortfolio
from alphaforge.backtesting.execution import ExecutionModel
from alphaforge.backtesting.models import BacktestResult, Trade
from alphaforge.backtesting.strategy import Strategy
from alphaforge.data.engine import MarketDataEngine
from alphaforge.data.validation import normalize_tickers, validate_market_data


class BacktestEngine:
    """Simulate a long-only strategy on daily bars without look-ahead bias.

    A strategy sees the market bars through each day's close. Its resulting
    target allocation is eligible at the next available date's open; opens
    are required for execution and are never replaced by closing prices.
    Holdings are marked at each date's close. Uninvested allocation remains
    in cash. Fractional shares are supported.
    """

    def __init__(
        self,
        initial_capital: float,
        *,
        execution_model: ExecutionModel | None = None,
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252,
    ) -> None:
        self._initial_capital = SimulatedPortfolio(initial_capital).initial_capital
        if execution_model is not None and not isinstance(
            execution_model, ExecutionModel
        ):
            raise TypeError("execution_model must be an ExecutionModel.")
        self._execution_model = execution_model or ExecutionModel()
        if not isinstance(risk_free_rate, Real) or isinstance(risk_free_rate, bool):
            raise TypeError("risk_free_rate must be a real number.")
        if not math.isfinite(risk_free_rate) or risk_free_rate <= -1:
            raise ValueError("risk_free_rate must be finite and greater than -1.")
        if not isinstance(periods_per_year, Integral) or isinstance(periods_per_year, bool):
            raise TypeError("periods_per_year must be a positive integer.")
        if periods_per_year <= 0:
            raise ValueError("periods_per_year must be a positive integer.")
        self._risk_free_rate = float(risk_free_rate)
        self._periods_per_year = int(periods_per_year)

    def run(
        self,
        history: pd.DataFrame,
        strategy: Strategy,
        *,
        benchmark_ticker: str | None = None,
    ) -> BacktestResult:
        """Run on standardized market bars, optionally comparing a benchmark.

        If supplied, ``benchmark_ticker`` is excluded from strategy assets and
        measured as a buy-and-hold close-price series beginning on the first
        simulation date.
        """
        if not callable(getattr(strategy, "generate_target_weights", None)):
            raise TypeError("strategy must implement generate_target_weights(history).")
        bars = _prepare_history(history)
        tickers = list(bars["ticker"].drop_duplicates())
        benchmark = None
        if benchmark_ticker is not None:
            if not isinstance(benchmark_ticker, str) or not benchmark_ticker.strip():
                raise ValueError("benchmark_ticker must be a non-empty ticker string.")
            benchmark = benchmark_ticker.strip().upper()
            if benchmark not in tickers:
                raise ValueError("benchmark_ticker must be present in market history.")
        assets = [ticker for ticker in tickers if ticker != benchmark]
        if not assets:
            raise ValueError("market history must contain at least one tradable asset.")

        bars = bars.loc[bars["ticker"].isin(assets + ([benchmark] if benchmark else []))]
        dates = pd.DatetimeIndex(sorted(bars["date"].unique()), name="date")
        expected_rows = len(dates) * len(tickers)
        if len(bars) != expected_rows:
            raise ValueError("market history must contain every ticker for every date.")

        opens = bars.pivot(index="date", columns="ticker", values="open").reindex(dates)
        closes = bars.pivot(index="date", columns="ticker", values="close").reindex(dates)
        if opens.isna().any().any():
            raise ValueError("open prices are required for every ticker and date.")
        if closes.isna().any().any():
            raise ValueError("close prices are required for every ticker and date.")

        portfolio = SimulatedPortfolio(self._initial_capital)
        pending_weights: pd.Series | None = None
        trades: list[Trade] = []
        equity_values: list[float] = []
        cash_values: list[float] = []
        position_values: list[dict[str, float]] = []
        realized_values: list[float] = []
        unrealized_values: list[float] = []
        benchmark_equity_values: list[float] | None = (
            [self._initial_capital] if benchmark is not None else None
        )
        benchmark_base = float(closes[benchmark].iloc[0]) if benchmark else None

        for index, date in enumerate(dates):
            open_prices = opens.loc[date, assets]
            if pending_weights is not None:
                trades.extend(
                    _rebalance(
                        portfolio,
                        pending_weights,
                        open_prices,
                        date,
                        self._execution_model,
                    )
                )

            close_prices = closes.loc[date, assets]
            equity = portfolio.market_value(close_prices)
            equity_values.append(equity)
            cash_values.append(portfolio.cash)
            position_values.append(
                {ticker: portfolio.quantity(ticker) for ticker in assets}
            )
            realized_values.append(portfolio.realized_pnl)
            unrealized_values.append(portfolio.unrealized_pnl(close_prices))

            if benchmark is not None and index > 0:
                assert benchmark_equity_values is not None and benchmark_base is not None
                benchmark_equity_values.append(
                    self._initial_capital
                    * float(closes[benchmark].loc[date])
                    / benchmark_base
                )

            if index < len(dates) - 1:
                available = bars.loc[bars["date"].le(date) & bars["ticker"].isin(assets)]
                pending_weights = strategy.generate_target_weights(available.copy())
                pending_weights = _validate_targets(pending_weights, assets)

        return _build_result(
            dates=dates,
            assets=assets,
            equity_values=equity_values,
            cash_values=cash_values,
            position_values=position_values,
            realized_values=realized_values,
            unrealized_values=unrealized_values,
            trades=trades,
            initial_capital=self._initial_capital,
            periods_per_year=self._periods_per_year,
            risk_free_rate=self._risk_free_rate,
            benchmark=benchmark,
            benchmark_equity_values=benchmark_equity_values,
        )

    def run_from_market_data(
        self,
        market_data_engine: MarketDataEngine,
        strategy: Strategy,
        tickers: Sequence[str],
        start: date | datetime | str,
        end: date | datetime | str,
        *,
        benchmark_ticker: str | None = None,
    ) -> BacktestResult:
        """Fetch bars through MarketDataEngine and run without database access."""
        if not isinstance(market_data_engine, MarketDataEngine):
            raise TypeError("market_data_engine must be a MarketDataEngine.")
        symbols = normalize_tickers(tickers)
        if benchmark_ticker is not None:
            normalized_benchmark = normalize_tickers([benchmark_ticker])[0]
            if normalized_benchmark not in symbols:
                symbols.append(normalized_benchmark)
        history = market_data_engine.fetch_history(symbols, start, end)
        return self.run(history, strategy, benchmark_ticker=benchmark_ticker)


def _prepare_history(history: pd.DataFrame) -> pd.DataFrame:
    bars = validate_market_data(history)
    if bars.empty:
        raise ValueError("market history must contain at least two dates.")
    if bars["date"].nunique() < 2:
        raise ValueError("market history must contain at least two dates.")
    if bars["open"].isna().any():
        raise ValueError("open prices are required for next-session execution.")
    if bars["close"].isna().any():
        raise ValueError("close prices are required to mark portfolio value.")
    return bars


def _validate_targets(targets: pd.Series, assets: list[str]) -> pd.Series:
    if not isinstance(targets, pd.Series):
        raise TypeError("strategy must return target weights as a pandas Series.")
    if not targets.index.is_unique or set(targets.index) != set(assets):
        raise ValueError("strategy target weights must contain each tradable asset once.")
    if (
        not pd.api.types.is_numeric_dtype(targets.dtype)
        or pd.api.types.is_bool_dtype(targets.dtype)
        or pd.api.types.is_complex_dtype(targets.dtype)
    ):
        raise TypeError("strategy target weights must be real numeric values.")
    targets = targets.reindex(assets).astype(float)
    values = targets.to_numpy()
    if not np.isfinite(values).all():
        raise ValueError("strategy target weights must be finite.")
    if (values < 0).any():
        raise ValueError("strategy target weights must be long-only.")
    if values.sum() > 1 + 1e-9:
        raise ValueError("strategy target weights must sum to no more than 1.")
    return targets


def _rebalance(
    portfolio: SimulatedPortfolio,
    target_weights: pd.Series,
    open_prices: pd.Series,
    date: pd.Timestamp,
    execution_model: ExecutionModel,
) -> list[Trade]:
    equity = portfolio.market_value(open_prices)
    target_quantities = {
        ticker: float(weight) * equity / float(open_prices[ticker])
        for ticker, weight in target_weights.items()
    }
    if not all(math.isfinite(quantity) for quantity in target_quantities.values()):
        raise ValueError("target allocation produced a non-finite position quantity.")
    trades: list[Trade] = []

    for ticker, target_quantity in target_quantities.items():
        current_quantity = portfolio.quantity(ticker)
        quantity_to_sell = current_quantity - target_quantity
        if quantity_to_sell > 1e-10:
            trades.append(
                portfolio.execute_trade(
                    date=date,
                    ticker=ticker,
                    side="SELL",
                    quantity=quantity_to_sell,
                    reference_price=float(open_prices[ticker]),
                    execution_model=execution_model,
                )
            )

    buy_quantities = {
        ticker: max(0.0, target_quantity - portfolio.quantity(ticker))
        for ticker, target_quantity in target_quantities.items()
    }
    total_buy_cost = sum(
        quantity
        * execution_model.execution_price(float(open_prices[ticker]), "BUY")
        * (1 + execution_model.transaction_cost_rate)
        for ticker, quantity in buy_quantities.items()
    )
    if not math.isfinite(total_buy_cost):
        raise ValueError("target allocation produced a non-finite order cost.")
    scale = min(1.0, portfolio.cash / total_buy_cost) if total_buy_cost else 1.0
    for ticker, quantity in buy_quantities.items():
        quantity *= scale
        if quantity > 1e-10:
            trades.append(
                portfolio.execute_trade(
                    date=date,
                    ticker=ticker,
                    side="BUY",
                    quantity=quantity,
                    reference_price=float(open_prices[ticker]),
                    execution_model=execution_model,
                )
            )
    return trades


def _annualized_return(
    equity: pd.Series,
    initial_capital: float,
    periods_per_year: int,
) -> float | None:
    periods = len(equity) - 1
    if periods <= 0:
        return None
    ending_value = float(equity.iloc[-1])
    if ending_value <= 0:
        raise ValueError("ending equity must be positive to calculate annualized return.")
    return (ending_value / initial_capital) ** (periods_per_year / periods) - 1


def _build_result(
    *,
    dates: pd.DatetimeIndex,
    assets: list[str],
    equity_values: list[float],
    cash_values: list[float],
    position_values: list[dict[str, float]],
    realized_values: list[float],
    unrealized_values: list[float],
    trades: list[Trade],
    initial_capital: float,
    periods_per_year: int,
    risk_free_rate: float,
    benchmark: str | None,
    benchmark_equity_values: list[float] | None,
) -> BacktestResult:
    equity = pd.Series(equity_values, index=dates, name="equity")
    cash = pd.Series(cash_values, index=dates, name="cash")
    positions = pd.DataFrame(position_values, index=dates, columns=assets)
    positions.index.name = "date"
    realized_pnl = pd.Series(realized_values, index=dates, name="realized_pnl")
    unrealized_pnl = pd.Series(unrealized_values, index=dates, name="unrealized_pnl")
    returns = equity.pct_change(fill_method=None).fillna(0.0).rename("return")
    cumulative_returns = calculate_cumulative_returns(returns)
    observed_returns = returns.iloc[1:]
    volatility = None
    if len(observed_returns) >= 2:
        volatility = calculate_portfolio_volatility(observed_returns) * math.sqrt(
            periods_per_year
        )
    sharpe = None
    if len(observed_returns) >= 2 and volatility not in (None, 0.0):
        sharpe = calculate_portfolio_sharpe_ratio(
            observed_returns,
            risk_free_rate=risk_free_rate,
            periods_per_year=periods_per_year,
        )
    max_drawdown = calculate_max_drawdown(equity)

    benchmark_equity = None
    benchmark_cumulative_returns = None
    benchmark_annualized_return = None
    if benchmark is not None:
        if benchmark_equity_values is None:
            raise RuntimeError("benchmark values were not recorded.")
        benchmark_equity = pd.Series(
            benchmark_equity_values,
            index=dates,
            name=f"{benchmark}_equity",
        )
        benchmark_returns = (
            benchmark_equity.pct_change(fill_method=None)
            .fillna(0.0)
            .rename("benchmark_return")
        )
        benchmark_cumulative_returns = calculate_cumulative_returns(benchmark_returns)
        benchmark_annualized_return = _annualized_return(
            benchmark_equity,
            initial_capital,
            periods_per_year,
        )

    trade_frame = pd.DataFrame(
        [
            {
                "date": trade.date,
                "ticker": trade.ticker,
                "side": trade.side,
                "quantity": trade.quantity,
                "price": trade.price,
                "transaction_cost": trade.transaction_cost,
                "realized_pnl": trade.realized_pnl,
            }
            for trade in trades
        ],
        columns=[
            "date",
            "ticker",
            "side",
            "quantity",
            "price",
            "transaction_cost",
            "realized_pnl",
        ],
    )
    if not trade_frame.empty:
        trade_frame["date"] = pd.to_datetime(trade_frame["date"])
    return BacktestResult(
        equity=equity,
        cash=cash,
        positions=positions,
        realized_pnl=realized_pnl,
        unrealized_pnl=unrealized_pnl,
        trades=trade_frame,
        returns=returns,
        cumulative_returns=cumulative_returns,
        annualized_return=_annualized_return(
            equity,
            initial_capital,
            periods_per_year,
        ),
        annualized_volatility=volatility,
        sharpe_ratio=sharpe,
        max_drawdown=max_drawdown,
        benchmark_equity=benchmark_equity,
        benchmark_cumulative_returns=benchmark_cumulative_returns,
        benchmark_annualized_return=benchmark_annualized_return,
    )
