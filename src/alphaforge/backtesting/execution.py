"""Execution assumptions for simulated orders."""

from dataclasses import dataclass
import math
from numbers import Real


@dataclass(frozen=True)
class ExecutionModel:
    """Proportional transaction costs and adverse price slippage.

    ``transaction_cost_rate`` is charged on executed notional. Slippage is
    applied to the reference price adversely: buys pay more and sells receive
    less. Both rates are fractions in ``[0, 1)``.
    """

    transaction_cost_rate: float = 0.0
    slippage_rate: float = 0.0

    def __post_init__(self) -> None:
        for name, value in (
            ("transaction_cost_rate", self.transaction_cost_rate),
            ("slippage_rate", self.slippage_rate),
        ):
            if not isinstance(value, Real) or isinstance(value, bool):
                raise TypeError(f"{name} must be a real number.")
            if not math.isfinite(value) or not 0 <= value < 1:
                raise ValueError(f"{name} must be finite and in [0, 1).")

    def execution_price(self, reference_price: float, side: str) -> float:
        """Return the fill price after side-dependent slippage."""
        if (
            not isinstance(reference_price, Real)
            or isinstance(reference_price, bool)
        ):
            raise TypeError("reference_price must be a real number.")
        if not math.isfinite(reference_price) or reference_price <= 0:
            raise ValueError("reference_price must be finite and positive.")
        if side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL.")
        factor = (
            1 + self.slippage_rate if side == "BUY" else 1 - self.slippage_rate
        )
        execution_price = reference_price * factor
        if not math.isfinite(execution_price) or execution_price <= 0:
            raise ValueError("execution price must be finite and positive.")
        return execution_price

    def transaction_cost(self, quantity: float, execution_price: float) -> float:
        """Calculate a proportional fee on executed notional."""
        if (
            not isinstance(quantity, Real)
            or isinstance(quantity, bool)
            or not isinstance(execution_price, Real)
            or isinstance(execution_price, bool)
        ):
            raise TypeError("quantity and execution_price must be real numbers.")
        if (
            not math.isfinite(quantity)
            or quantity < 0
            or not math.isfinite(execution_price)
            or execution_price <= 0
        ):
            raise ValueError("quantity and execution_price must be finite and valid.")
        return abs(quantity * execution_price) * self.transaction_cost_rate
