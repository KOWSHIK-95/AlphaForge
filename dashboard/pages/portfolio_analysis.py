"""Streamlit Portfolio Analysis page."""

from datetime import date, timedelta
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.api_client import AlphaForgeApiClient, ApiResult


def prepare_asset_returns(records: list[dict[str, Any]], tickers: list[str]) -> tuple[dict[str, list[float]], int]:
    """Convert price records into aligned, complete return observations."""
    frame = pd.DataFrame(records)
    required = {"date", "ticker", "close"}
    if frame.empty or not required.issubset(frame.columns):
        raise ValueError("The API returned no usable prices for portfolio analysis.")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    if frame[["date", "ticker", "close"]].isna().any().any():
        raise ValueError("Returned prices contain missing or invalid values.")
    prices = frame.pivot_table(index="date", columns="ticker", values="close", aggfunc="first")
    prices = prices.reindex(columns=tickers).sort_index()
    if prices.empty or prices.isna().all().any():
        raise ValueError("At least one asset has no usable price history.")
    returns = prices.pct_change(fill_method=None)
    complete = returns.dropna(how="any")
    dropped = len(returns) - len(complete)
    if complete.empty:
        raise ValueError("There are not enough complete aligned return observations.")
    return {ticker: complete[ticker].astype(float).tolist() for ticker in tickers}, dropped


def _validate_weights(tickers: list[str], weights: dict[str, float]) -> str | None:
    if set(weights) != set(tickers):
        return "Provide exactly one weight for every selected asset."
    if any(value < 0 for value in weights.values()):
        return "Portfolio weights must be nonnegative for this dashboard."
    if abs(sum(weights.values()) - 1.0) > 1e-8:
        return "Portfolio weights must sum to 1.0."
    return None


def render_portfolio_analysis(client: AlphaForgeApiClient | None = None) -> None:
    """Render portfolio controls, analysis, and supported optimization results."""
    st.title("Portfolio Analysis")
    st.write(
        "Prices are converted to simple daily returns and aligned by date. "
        "Incomplete observations are excluded only with a visible warning."
    )
    ticker_text = st.text_input("Asset tickers", value="AAPL, MSFT")
    today = date.today()
    start = st.date_input("Start date", value=today - timedelta(days=365))
    end = st.date_input("End date (exclusive)", value=today)
    risk_free_rate = st.number_input("Annual risk-free rate", value=0.0, step=0.01)
    periods_per_year = st.number_input("Periods per year", min_value=1, value=252, step=1)
    confidence_level = st.number_input(
        "VaR/CVaR confidence level", min_value=0.01, max_value=0.99, value=0.95, step=0.01
    )
    optimization = st.selectbox(
        "Optimization",
        ["none", "minimum_volatility", "maximum_sharpe"],
        format_func=lambda value: value.replace("_", " ").title(),
    )
    tickers = [ticker.strip().upper() for ticker in ticker_text.split(",") if ticker.strip()]
    weights: dict[str, float] = {}
    if optimization == "none":
        st.caption("Weights are long-only on this page and must sum to 1.0.")
        for ticker in tickers:
            weights[ticker] = st.number_input(
                f"{ticker} weight", min_value=0.0, max_value=1.0, value=1.0 / len(tickers) if tickers else 0.0, step=0.01
            )
    if not st.button("Run portfolio analysis", type="primary"):
        return
    if not tickers:
        st.warning("Enter at least one asset ticker.")
        return
    if start >= end:
        st.warning("The start date must be earlier than the exclusive end date.")
        return
    if optimization == "none":
        weight_error = _validate_weights(tickers, weights)
        if weight_error:
            st.warning(weight_error)
            return

    api_client = client or AlphaForgeApiClient()
    owns_client = client is None
    try:
        market_data = api_client.market_data_history(tickers, start, end)
        if not market_data.successful:
            st.error(market_data.message)
            return
        try:
            asset_returns, dropped = prepare_asset_returns(market_data.data, tickers)
        except ValueError as error:
            st.warning(str(error))
            return
        if dropped:
            st.warning(f"Excluded {dropped} incomplete return observation(s); no values were filled.")
        result = api_client.portfolio_analytics(
            asset_returns,
            weights=weights if optimization == "none" else None,
            risk_free_rate=float(risk_free_rate),
            periods_per_year=int(periods_per_year),
            confidence_level=float(confidence_level),
            optimization=optimization,
        )
        if result.successful and optimization != "none":
            optimized = result.data.get("optimization")
            optimized_weights = optimized.get("weights") if isinstance(optimized, dict) else None
            if isinstance(optimized_weights, dict):
                performance = api_client.portfolio_analytics(
                    asset_returns,
                    weights={str(key): float(value) for key, value in optimized_weights.items()},
                    risk_free_rate=float(risk_free_rate),
                    periods_per_year=int(periods_per_year),
                    confidence_level=float(confidence_level),
                    optimization="none",
                )
                if performance.successful:
                    result = ApiResult(
                        {**performance.data, "optimization": optimized},
                        performance.status_code,
                        performance.message,
                    )
    finally:
        if owns_client:
            api_client.close()
    _render_result(result, weights)


def _render_result(result: ApiResult, weights: dict[str, float]) -> None:
    if not result.successful:
        st.error(result.message)
        return
    data = result.data
    metric_columns = st.columns(6)
    for column, label, key in zip(
        metric_columns,
        ["Annualized volatility", "Sharpe ratio", "Maximum drawdown", "VaR", "CVaR", "Volatility"],
        ["annualized_volatility", "sharpe_ratio", "max_drawdown", "var", "cvar", "volatility"],
    ):
        value = data.get(key)
        column.metric(label, "N/A" if value is None else f"{float(value):.4f}")
    returns = data.get("returns")
    cumulative = data.get("cumulative_returns")
    if isinstance(returns, list) and isinstance(cumulative, list):
        chart = pd.DataFrame({"observation": range(len(returns)), "returns": returns, "cumulative_returns": cumulative})
        st.plotly_chart(px.line(chart, x="observation", y=["returns", "cumulative_returns"], title="Portfolio returns"), use_container_width=True)
    optimization = data.get("optimization")
    chart_weights = weights
    if isinstance(optimization, dict) and isinstance(optimization.get("weights"), dict):
        chart_weights = {
            str(asset): float(value)
            for asset, value in optimization["weights"].items()
        }
    if chart_weights:
        allocation = pd.DataFrame({"asset": list(chart_weights), "weight": list(chart_weights.values())})
        st.plotly_chart(px.bar(allocation, x="asset", y="weight", title="Portfolio allocation"), use_container_width=True)
    correlation = data.get("correlation")
    if isinstance(correlation, dict) and correlation:
        correlation_frame = pd.DataFrame(correlation, dtype=float)
        st.plotly_chart(px.imshow(correlation_frame, text_auto=True, title="Asset correlation"), use_container_width=True)
    if isinstance(optimization, dict):
        st.subheader("Optimized portfolio")
        st.json(optimization)
    st.caption("Metrics use historical observations only. VaR and CVaR are nonnegative loss fractions.")
