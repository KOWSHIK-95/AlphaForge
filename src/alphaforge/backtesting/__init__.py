"""Backtesting engine, strategy interface, and execution models."""

from alphaforge.backtesting.engine import BacktestEngine
from alphaforge.backtesting.execution import ExecutionModel
from alphaforge.backtesting.models import BacktestResult, Trade
from alphaforge.backtesting.strategy import (
    MovingAverageCrossoverStrategy,
    Strategy,
)

__all__ = [
    "BacktestEngine",
    "BacktestResult",
    "ExecutionModel",
    "MovingAverageCrossoverStrategy",
    "Strategy",
    "Trade",
]
