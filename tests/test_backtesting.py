import math

import numpy as np
import pandas as pd
import pytest

from alphaforge.backtesting import (
    BacktestEngine,
    ExecutionModel,
    MovingAverageCrossoverStrategy,
)
from alphaforge.backtesting.accounting import SimulatedPortfolio
from alphaforge.data.engine import MarketDataEngine


def _history(
    opens: dict[str, list[float]],
    closes: dict[str, list[float]],
) -> pd.DataFrame:
    dates = pd.date_range("2025-01-02", periods=len(next(iter(opens.values()))))
    rows = []
    for ticker in opens:
        for index, date in enumerate(dates):
            rows.append(
                {
                    "date": date,
                    "ticker": ticker,
                    "open": opens[ticker][index],
                    "high": max(opens[ticker][index], closes[ticker][index]),
                    "low": min(opens[ticker][index], closes[ticker][index]),
                    "close": closes[ticker][index],
                    "adj_close": closes[ticker][index],
                    "volume": 1000,
                }
            )
    return pd.DataFrame(rows)


class FixedTargetStrategy:
    def __init__(self, weights: dict[str, float]) -> None:
        self.weights = weights
        self.observed_through: list[pd.Timestamp] = []

    def generate_target_weights(self, history: pd.DataFrame) -> pd.Series:
        last_date = pd.Timestamp(history["date"].max())
        self.observed_through.append(last_date)
        assert history["date"].max() == last_date
        return pd.Series(self.weights, name="target_weight")


def test_moving_average_strategy_validates_windows():
    for args, error in (
        ((0, 3), ValueError),
        ((2, 2), ValueError),
        ((1.5, 3), TypeError),
        ((True, 3), TypeError),
    ):
        with pytest.raises(error):
            MovingAverageCrossoverStrategy(*args)


def test_moving_average_strategy_stays_in_cash_during_warmup():
    strategy = MovingAverageCrossoverStrategy(short_window=2, long_window=3)
    history = _history({"A": [1, 1]}, {"A": [10, 12]})

    actual = strategy.generate_target_weights(history)

    assert actual.to_dict() == {"A": 0.0}


@pytest.mark.parametrize("close", [0, -1, np.inf, -np.inf])
def test_moving_average_strategy_rejects_invalid_close_prices(close):
    strategy = MovingAverageCrossoverStrategy(short_window=1, long_window=2)
    history = _history({"A": [10, close]}, {"A": [10, close]})

    with pytest.raises(ValueError):
        strategy.generate_target_weights(history)


def test_moving_average_strategy_enters_and_exits_on_crossovers():
    strategy = MovingAverageCrossoverStrategy(short_window=2, long_window=3)
    closes = [3, 2, 1, 2, 4, 6, 4, 2]
    history = _history({"A": [*closes]}, {"A": closes})
    expected = [0, 0, 0, 0, 1, 1, 1, 0]

    actual = [
        strategy.generate_target_weights(history.iloc[: index + 1])["A"]
        for index in range(len(history))
    ]

    assert actual == expected


def test_moving_average_strategy_equal_weights_active_assets():
    strategy = MovingAverageCrossoverStrategy(short_window=1, long_window=2)
    history = _history(
        {"A": [1, 2], "B": [1, 3]},
        {"A": [1, 3], "B": [1, 4]},
    )

    actual = strategy.generate_target_weights(history)

    assert actual.to_dict() == {"A": 0.5, "B": 0.5}


def test_strategy_executes_at_next_open_not_signal_close():
    history = _history(
        {"A": [10, 20, 30]},
        {"A": [10, 25, 30]},
    )
    strategy = FixedTargetStrategy({"A": 1.0})
    result = BacktestEngine(1000).run(history, strategy)

    assert result.trades.iloc[0]["date"] == history["date"].min() + pd.Timedelta(days=1)
    assert result.trades.iloc[0]["price"] == 20
    assert result.equity.tolist() == pytest.approx([1000, 1250, 1500])
    assert strategy.observed_through == list(pd.to_datetime(sorted(history["date"].unique()))[:2])


def test_strategy_never_receives_future_rows():
    history = _history({"A": [10, 20, 30, 40]}, {"A": [10, 20, 30, 40]})
    strategy = FixedTargetStrategy({"A": 0.0})

    BacktestEngine(100).run(history, strategy)

    assert strategy.observed_through == list(pd.to_datetime(sorted(history["date"].unique()))[:3])


def test_initial_capital_and_cash_when_strategy_holds_cash():
    history = _history({"A": [10, 11]}, {"A": [10, 11]})
    result = BacktestEngine(2500).run(history, FixedTargetStrategy({"A": 0.0}))

    assert result.cash.tolist() == [2500, 2500]
    assert result.equity.tolist() == [2500, 2500]
    assert result.positions["A"].tolist() == [0, 0]
    assert result.trades.empty


def test_accounting_tracks_buys_sells_and_realized_unrealized_pnl():
    portfolio = SimulatedPortfolio(1000)
    model = ExecutionModel()
    date = pd.Timestamp("2025-01-02")
    portfolio.execute_trade(
        date=date,
        ticker="A",
        side="BUY",
        quantity=10,
        reference_price=20,
        execution_model=model,
    )

    assert portfolio.cash == pytest.approx(800)
    assert portfolio.quantity("A") == 10
    assert portfolio.market_value(pd.Series({"A": 25})) == pytest.approx(1050)
    assert portfolio.unrealized_pnl(pd.Series({"A": 25})) == pytest.approx(50)

    trade = portfolio.execute_trade(
        date=date + pd.Timedelta(days=1),
        ticker="A",
        side="SELL",
        quantity=4,
        reference_price=25,
        execution_model=model,
    )

    assert trade.realized_pnl == pytest.approx(20)
    assert portfolio.realized_pnl == pytest.approx(20)
    assert portfolio.quantity("A") == pytest.approx(6)
    assert portfolio.cash == pytest.approx(900)
    assert portfolio.unrealized_pnl(pd.Series({"A": 25})) == pytest.approx(30)
    assert portfolio.market_value(pd.Series({"A": 25})) == pytest.approx(1050)
    assert portfolio.market_value(pd.Series({"A": 25})) - 1000 == pytest.approx(
        portfolio.realized_pnl + portfolio.unrealized_pnl(pd.Series({"A": 25}))
    )


def test_transaction_costs_and_slippage_are_applied():
    history = _history({"A": [10, 10]}, {"A": [10, 10]})
    result = BacktestEngine(
        1000,
        execution_model=ExecutionModel(
            transaction_cost_rate=0.01,
            slippage_rate=0.02,
        ),
    ).run(history, FixedTargetStrategy({"A": 1.0}))

    trade = result.trades.iloc[0]
    assert trade["price"] == pytest.approx(10.2)
    assert trade["transaction_cost"] == pytest.approx(
        trade["quantity"] * 10.2 * 0.01
    )
    assert result.cash.iloc[-1] == pytest.approx(0)
    assert result.equity.iloc[-1] < 1000


def test_extreme_prices_cannot_silently_skip_unexecutable_orders():
    history = _history(
        {"A": [1e-320, 1e-320]},
        {"A": [1e-320, 1e-320]},
    )

    with pytest.raises(ValueError, match="non-finite"):
        BacktestEngine(1e308).run(history, FixedTargetStrategy({"A": 1.0}))


def test_order_validation_prevents_overspending_and_short_sales():
    portfolio = SimulatedPortfolio(100)
    model = ExecutionModel()
    date = pd.Timestamp("2025-01-02")
    with pytest.raises(ValueError, match="insufficient cash"):
        portfolio.execute_trade(
            date=date,
            ticker="A",
            side="BUY",
            quantity=11,
            reference_price=10,
            execution_model=model,
        )
    with pytest.raises(ValueError, match="exceeds"):
        portfolio.execute_trade(
            date=date,
            ticker="A",
            side="SELL",
            quantity=1,
            reference_price=10,
            execution_model=model,
        )
    assert portfolio.quantities == {}
    with pytest.raises(ValueError, match="positive"):
        portfolio.execute_trade(
            date=date,
            ticker="A",
            side="BUY",
            quantity=0,
            reference_price=10,
            execution_model=model,
        )


@pytest.mark.parametrize(
    ("transaction_cost_rate", "slippage_rate"),
    [(-0.01, 0), (0, -0.01), (1, 0), (0, float("inf"))],
)
def test_execution_model_rejects_invalid_rates(transaction_cost_rate, slippage_rate):
    with pytest.raises(ValueError):
        ExecutionModel(
            transaction_cost_rate=transaction_cost_rate,
            slippage_rate=slippage_rate,
        )


def test_target_rebalance_respects_cash_even_with_costs():
    history = _history(
        {"A": [10, 10, 10], "B": [20, 20, 20]},
        {"A": [10, 10, 10], "B": [20, 20, 20]},
    )
    result = BacktestEngine(
        1000,
        execution_model=ExecutionModel(transaction_cost_rate=0.05),
    ).run(history, FixedTargetStrategy({"A": 0.5, "B": 0.5}))

    assert result.cash.min() >= 0
    assert result.trades["ticker"].tolist() == ["A", "B"]
    assert result.positions.iloc[-1].to_dict() == pytest.approx(
        {"A": result.trades.iloc[0]["quantity"], "B": result.trades.iloc[1]["quantity"]}
    )


@pytest.mark.parametrize(
    "history",
    [
        pd.DataFrame(),
        _history({"A": [10]}, {"A": [10]}),
        _history({"A": [10, 10]}, {"A": [10, 10]}).assign(open=[10.0, np.nan]),
        _history({"A": [10, 10]}, {"A": [10, 10]}).assign(close=[10.0, np.nan]),
        _history({"A": [10, 10], "B": [10, 10]}, {"A": [10, 10], "B": [10, 10]}).drop(
            index=3
        ),
    ],
)
def test_backtest_rejects_empty_insufficient_or_incomplete_market_data(history):
    with pytest.raises(ValueError):
        BacktestEngine(100).run(history, FixedTargetStrategy({"A": 0.0}))


def test_backtest_rejects_invalid_strategy_target_weights():
    history = _history({"A": [10, 10]}, {"A": [10, 10]})
    invalid_targets = [
        {"A": -0.1},
        {"A": 1.1},
        {"B": 1.0},
    ]
    for weights in invalid_targets:
        with pytest.raises(ValueError):
            BacktestEngine(100).run(history, FixedTargetStrategy(weights))


def test_missing_mark_price_for_held_position_is_rejected():
    portfolio = SimulatedPortfolio(100)
    portfolio.execute_trade(
        date=pd.Timestamp("2025-01-02"),
        ticker="A",
        side="BUY",
        quantity=1,
        reference_price=10,
        execution_model=ExecutionModel(),
    )
    with pytest.raises(ValueError, match="missing mark"):
        portfolio.market_value(pd.Series(dtype="float64"))


def test_multiple_assets_and_repeated_targets_do_not_create_redundant_orders():
    history = _history(
        {"A": [10, 10, 10], "B": [20, 20, 20]},
        {"A": [10, 10, 10], "B": [20, 20, 20]},
    )
    strategy = FixedTargetStrategy({"A": 0.5, "B": 0.5})
    result = BacktestEngine(1000).run(history, strategy)

    assert len(result.trades) == 2
    assert result.trades["side"].tolist() == ["BUY", "BUY"]
    assert result.positions.iloc[-1].to_dict() == pytest.approx({"A": 50, "B": 25})
    assert result.equity.tolist() == pytest.approx([1000, 1000, 1000])


def test_benchmark_comparison_uses_buy_and_hold_close_prices():
    history = _history(
        {"A": [10, 10, 10], "BMK": [100, 100, 110]},
        {"A": [10, 10, 10], "BMK": [100, 105, 110]},
    )
    result = BacktestEngine(1000).run(
        history,
        FixedTargetStrategy({"A": 0.0}),
        benchmark_ticker="bmk",
    )

    assert result.benchmark_equity.tolist() == pytest.approx([1000, 1050, 1100])
    assert result.benchmark_cumulative_returns.tolist() == pytest.approx([0, 0.05, 0.1])
    assert result.benchmark_annualized_return == pytest.approx(1.1**126 - 1)
    assert result.equity.tolist() == [1000, 1000, 1000]


def test_backtest_reports_returns_risk_and_drawdown():
    history = _history(
        {"A": [10, 10, 10, 10]},
        {"A": [10, 11, 9, 12]},
    )
    result = BacktestEngine(1000).run(history, FixedTargetStrategy({"A": 1.0}))
    observed_returns = result.returns.iloc[1:]

    assert result.returns.iloc[0] == 0
    assert result.cumulative_returns.iloc[-1] == pytest.approx(0.2)
    assert result.annualized_return == pytest.approx(1.2 ** (252 / 3) - 1)
    assert result.annualized_volatility == pytest.approx(
        observed_returns.std(ddof=1) * math.sqrt(252)
    )
    assert result.sharpe_ratio is not None
    assert result.max_drawdown == pytest.approx(-2 / 11)
    assert result.realized_pnl.iloc[-1] == pytest.approx(0)
    assert result.unrealized_pnl.iloc[-1] == pytest.approx(200)


def test_periods_per_year_controls_annualized_volatility_and_return():
    history = _history(
        {"A": [10, 10, 10, 10]},
        {"A": [10, 11, 9, 12]},
    )
    result = BacktestEngine(
        1000,
        periods_per_year=12,
    ).run(history, FixedTargetStrategy({"A": 1.0}))
    returns = result.returns.iloc[1:]

    assert result.annualized_volatility == pytest.approx(
        returns.std(ddof=1) * math.sqrt(12)
    )
    assert result.annualized_return == pytest.approx(1.2 ** (12 / 3) - 1)


def test_market_data_engine_integration_uses_fetch_history():
    class Provider:
        def __init__(self, history: pd.DataFrame) -> None:
            self.history = history

        def fetch_history(self, tickers, start, end):
            dates = pd.to_datetime(self.history["date"])
            return self.history.loc[
                self.history["ticker"].isin(tickers)
                & dates.ge(pd.Timestamp(start))
                & dates.lt(pd.Timestamp(end))
            ].copy()

    history = _history({"A": [10, 10]}, {"A": [10, 11]})
    data_engine = MarketDataEngine(Provider(history))
    result = BacktestEngine(100).run_from_market_data(
        data_engine,
        FixedTargetStrategy({"A": 1.0}),
        ["A"],
        "2025-01-01",
        "2025-02-01",
    )

    assert result.equity.iloc[-1] == pytest.approx(110)
