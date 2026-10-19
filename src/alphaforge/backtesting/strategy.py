"""Strategy interface and built-in moving-average crossover strategy."""

from numbers import Integral
from typing import Protocol

import pandas as pd


class Strategy(Protocol):
    """A strategy maps data available through a close to target asset weights."""

    def generate_target_weights(self, history: pd.DataFrame) -> pd.Series:
        """Return nonnegative target weights keyed by ticker."""


class MovingAverageCrossoverStrategy:
    """Equal-weight assets when short SMA exceeds long SMA; otherwise hold cash.

    The strategy reads only the bars passed for its current decision date.
    Each asset's close is used for both moving averages. Until both windows
    are populated, that asset remains in cash and is not entered.
    """

    def __init__(self, short_window: int, long_window: int) -> None:
        if (
            not isinstance(short_window, Integral)
            or isinstance(short_window, bool)
        ):
            raise TypeError("short_window must be a positive integer.")
        if not isinstance(long_window, Integral) or isinstance(long_window, bool):
            raise TypeError("long_window must be a positive integer.")
        if short_window <= 0 or long_window <= 0:
            raise ValueError("moving-average windows must be positive.")
        if short_window >= long_window:
            raise ValueError("short_window must be smaller than long_window.")
        self.short_window = int(short_window)
        self.long_window = int(long_window)

    def generate_target_weights(self, history: pd.DataFrame) -> pd.Series:
        """Generate equal-weight long allocations using history through its last date."""
        required = {"date", "ticker", "close"}
        if not isinstance(history, pd.DataFrame):
            raise TypeError("history must be a pandas DataFrame.")
        if not required.issubset(history.columns):
            raise ValueError("history must contain date, ticker, and close columns.")
        if history.empty:
            return pd.Series(dtype="float64", name="target_weight")
        if history[["date", "ticker", "close"]].isna().any().any():
            raise ValueError("strategy history must not contain missing values.")
        if (
            not pd.api.types.is_numeric_dtype(history["close"].dtype)
            or pd.api.types.is_bool_dtype(history["close"].dtype)
        ):
            raise TypeError("strategy close prices must be numeric.")
        if history["close"].isin([float("inf"), float("-inf")]).any():
            raise ValueError("strategy close prices must be finite.")
        if history["close"].le(0).any():
            raise ValueError("strategy close prices must be positive.")
        if history.duplicated(["ticker", "date"]).any():
            raise ValueError("strategy history must have unique ticker/date rows.")

        active: list[str] = []
        for ticker, bars in history.groupby("ticker", sort=False):
            closes = bars.sort_values("date")["close"]
            short_average = closes.rolling(
                self.short_window,
                min_periods=self.short_window,
            ).mean()
            long_average = closes.rolling(
                self.long_window,
                min_periods=self.long_window,
            ).mean()
            if (
                not long_average.empty
                and pd.notna(long_average.iloc[-1])
                and short_average.iloc[-1] > long_average.iloc[-1]
            ):
                active.append(str(ticker))

        weights = pd.Series(0.0, index=pd.Index(
            history["ticker"].drop_duplicates(), name="ticker"
        ), name="target_weight")
        if active:
            weights.loc[active] = 1.0 / len(active)
        return weights
