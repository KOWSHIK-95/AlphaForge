"""Cash and long-only position accounting for simulated portfolios."""

from dataclasses import dataclass
import math
from numbers import Real

import pandas as pd

from alphaforge.backtesting.execution import ExecutionModel
from alphaforge.backtesting.models import Trade


@dataclass
class _Position:
    quantity: float = 0.0
    average_cost: float = 0.0


class SimulatedPortfolio:
    """Maintain cash, long positions, cost basis, and realized profit/loss."""

    def __init__(self, initial_capital: float) -> None:
        if isinstance(initial_capital, bool) or not isinstance(initial_capital, Real):
            raise TypeError("initial_capital must be a real number.")
        if not math.isfinite(initial_capital) or initial_capital <= 0:
            raise ValueError("initial_capital must be finite and positive.")
        self.initial_capital = float(initial_capital)
        self.cash = float(initial_capital)
        self._positions: dict[str, _Position] = {}
        self._realized_pnl = 0.0

    @property
    def realized_pnl(self) -> float:
        return self._realized_pnl

    @property
    def quantities(self) -> dict[str, float]:
        return {
            ticker: position.quantity
            for ticker, position in self._positions.items()
        }

    def quantity(self, ticker: str) -> float:
        position = self._positions.get(ticker)
        return position.quantity if position is not None else 0.0

    def execute_trade(
        self,
        *,
        date: pd.Timestamp,
        ticker: str,
        side: str,
        quantity: float,
        reference_price: float,
        execution_model: ExecutionModel,
    ) -> Trade:
        """Execute a validated buy or long-position sale."""
        if side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL.")
        if isinstance(quantity, bool) or not isinstance(quantity, Real):
            raise TypeError("quantity must be a real number.")
        if not math.isfinite(quantity) or quantity <= 0:
            raise ValueError("quantity must be finite and positive.")
        if not isinstance(ticker, str) or not ticker:
            raise ValueError("ticker must be a non-empty string.")

        position = self._positions.get(ticker)
        if side == "SELL":
            if position is None or quantity > position.quantity + 1e-10:
                raise ValueError("sell quantity exceeds the current position.")
            quantity = min(quantity, position.quantity)

        execution_price = execution_model.execution_price(reference_price, side)
        fee = execution_model.transaction_cost(quantity, execution_price)
        notional = quantity * execution_price
        if not math.isfinite(notional) or not math.isfinite(fee):
            raise ValueError("trade notional and transaction cost must be finite.")
        if position is None:
            position = _Position()
        realized_pnl = 0.0

        if side == "BUY":
            total_cost = notional + fee
            if total_cost > self.cash + 1e-10:
                raise ValueError("insufficient cash to execute buy order.")
            previous_cost = position.average_cost * position.quantity
            new_quantity = position.quantity + quantity
            new_average_cost = (previous_cost + total_cost) / new_quantity
            new_cash = max(0.0, self.cash - total_cost)
            if not all(
                math.isfinite(value)
                for value in (new_quantity, new_average_cost, new_cash)
            ):
                raise ValueError("trade would produce non-finite portfolio accounting.")
            self._positions[ticker] = position
            position.quantity = new_quantity
            position.average_cost = new_average_cost
            self.cash = new_cash
        else:
            realized_pnl = notional - fee - position.average_cost * quantity
            new_cash = self.cash + notional - fee
            new_realized_pnl = self._realized_pnl + realized_pnl
            if not math.isfinite(new_cash) or not math.isfinite(new_realized_pnl):
                raise ValueError("trade would produce non-finite portfolio accounting.")
            position.quantity -= quantity
            self.cash = new_cash
            self._realized_pnl = new_realized_pnl
            if position.quantity <= 1e-12:
                position.quantity = 0.0
                position.average_cost = 0.0

        if not math.isfinite(self.cash) or not math.isfinite(self._realized_pnl):
            raise ValueError("trade would produce non-finite portfolio accounting.")
        return Trade(
            date=pd.Timestamp(date),
            ticker=ticker,
            side=side,
            quantity=float(quantity),
            price=float(execution_price),
            transaction_cost=float(fee),
            realized_pnl=float(realized_pnl),
        )

    def market_value(self, prices: pd.Series) -> float:
        """Value every held position at supplied current market prices."""
        value = self.cash
        for ticker, position in self._positions.items():
            if position.quantity == 0:
                continue
            if ticker not in prices.index or pd.isna(prices[ticker]):
                raise ValueError(f"missing mark price for held position {ticker}.")
            price = float(prices[ticker])
            if not math.isfinite(price) or price <= 0:
                raise ValueError(f"mark price for {ticker} must be finite and positive.")
            value += position.quantity * price
        if not math.isfinite(value):
            raise ValueError("portfolio market value is non-finite.")
        return value

    def unrealized_pnl(self, prices: pd.Series) -> float:
        """Calculate current unrealized P&L, including buy-side fees in cost basis."""
        unrealized = 0.0
        for ticker, position in self._positions.items():
            if position.quantity == 0:
                continue
            if ticker not in prices.index or pd.isna(prices[ticker]):
                raise ValueError(f"missing mark price for held position {ticker}.")
            unrealized += (
                float(prices[ticker]) - position.average_cost
            ) * position.quantity
        if not math.isfinite(unrealized):
            raise ValueError("unrealized profit and loss is non-finite.")
        return unrealized
