"""Request and response models for the HTTP API."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ErrorResponse(BaseModel):
    code: str
    message: str


class MarketDataRequest(BaseModel):
    tickers: list[str] = Field(min_length=1)
    start: date
    end: date
    include_returns: bool = False

    @field_validator("tickers")
    @classmethod
    def validate_tickers(cls, value: list[str]) -> list[str]:
        normalized = [ticker.strip().upper() for ticker in value]
        if any(not ticker for ticker in normalized):
            raise ValueError("ticker symbols must not be empty.")
        if any(len(ticker) > 32 for ticker in normalized):
            raise ValueError("ticker symbols must not exceed 32 characters.")
        return list(dict.fromkeys(normalized))

    @model_validator(mode="after")
    def validate_range(self) -> "MarketDataRequest":
        if self.start >= self.end:
            raise ValueError("start must be earlier than end.")
        return self


class MarketBar(BaseModel):
    model_config = ConfigDict(extra="ignore")

    date: date
    ticker: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float
    adj_close: float | None = None
    volume: float | None = None

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, value: str) -> str:
        value = value.strip().upper()
        if not value or len(value) > 32:
            raise ValueError("ticker must be a non-empty symbol of at most 32 characters.")
        return value


class AnalyticsRequest(BaseModel):
    prices: list[float | None] = Field(min_length=1)
    risk_free_rate: float = 0.0
    periods_per_year: int = Field(default=252, gt=0)


class PortfolioRequest(BaseModel):
    asset_returns: dict[str, list[float]] = Field(min_length=1)
    weights: dict[str, float] | None = None
    risk_free_rate: float = 0.0
    periods_per_year: int = Field(default=252, gt=0)
    confidence_level: float = Field(default=0.95, gt=0, lt=1)
    optimization: Literal["none", "minimum_volatility", "maximum_sharpe"] = "none"

    @model_validator(mode="after")
    def validate_inputs(self) -> "PortfolioRequest":
        if not self.asset_returns or any(not name.strip() for name in self.asset_returns):
            raise ValueError("asset_returns must contain non-empty asset names.")
        lengths = {len(values) for values in self.asset_returns.values()}
        if len(lengths) != 1:
            raise ValueError("all asset return series must have the same length.")
        if not lengths or not next(iter(lengths)):
            raise ValueError("asset_returns must contain observations.")
        if self.optimization == "none" and self.weights is None:
            raise ValueError("weights are required when optimization is none.")
        if self.weights is not None and set(self.weights) != set(self.asset_returns):
            raise ValueError("weights must contain exactly one value for each asset.")
        return self


class StrategyConfig(BaseModel):
    type: Literal["moving_average_crossover"] = "moving_average_crossover"
    short_window: int = Field(gt=0)
    long_window: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_windows(self) -> "StrategyConfig":
        if self.short_window >= self.long_window:
            raise ValueError("short_window must be smaller than long_window.")
        return self


class BacktestRequest(BaseModel):
    tickers: list[str] | None = None
    start: date | None = None
    end: date | None = None
    history: list[MarketBar] | None = None
    initial_capital: float = Field(gt=0)
    strategy: StrategyConfig
    benchmark_ticker: str | None = None
    transaction_cost_rate: float = Field(default=0.0, ge=0, lt=1)
    slippage_rate: float = Field(default=0.0, ge=0, lt=1)
    risk_free_rate: float = 0.0
    periods_per_year: int = Field(default=252, gt=0)

    @model_validator(mode="after")
    def validate_source(self) -> "BacktestRequest":
        if self.history is None and (
            not self.tickers or self.start is None or self.end is None
        ):
            raise ValueError("provide history or tickers with start and end.")
        if self.start is not None and self.end is not None and self.start >= self.end:
            raise ValueError("start must be earlier than end.")
        if self.tickers:
            normalized = [ticker.strip().upper() for ticker in self.tickers]
            if any(not ticker for ticker in normalized):
                raise ValueError("ticker symbols must not be empty.")
            self.tickers = list(dict.fromkeys(normalized))
        if self.benchmark_ticker is not None:
            self.benchmark_ticker = self.benchmark_ticker.strip().upper()
            if not self.benchmark_ticker:
                raise ValueError("benchmark_ticker must not be empty.")
        return self
