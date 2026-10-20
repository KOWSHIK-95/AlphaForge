"""Streamlit Backtesting page."""

from datetime import date, timedelta
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.api_client import AlphaForgeApiClient, ApiResult


def render_backtesting(client: AlphaForgeApiClient | None = None) -> None:
    """Render supported moving-average crossover backtest controls."""
    st.title("Backtesting")
    st.write(
        "The moving-average strategy uses closes through date t and executes "
        "eligible orders at the next available open. Backtests are long-only."
    )
    ticker_text = st.text_input("Tradable tickers", value="AAPL")
    benchmark = st.text_input("Optional benchmark ticker", value="")
    today = date.today()
    start = st.date_input("Start date", value=today - timedelta(days=365))
    end = st.date_input("End date (exclusive)", value=today)
    initial_capital = st.number_input("Initial capital", min_value=0.01, value=100000.0)
    short_window = st.number_input("Short moving-average window", min_value=1, value=20, step=1)
    long_window = st.number_input("Long moving-average window", min_value=2, value=50, step=1)
    transaction_cost_rate = st.number_input("Transaction cost rate", min_value=0.0, max_value=0.99, value=0.0, step=0.001, format="%.4f")
    slippage_rate = st.number_input("Slippage rate", min_value=0.0, max_value=0.99, value=0.0, step=0.001, format="%.4f")
    risk_free_rate = st.number_input("Annual risk-free rate", value=0.0, step=0.01)
    periods_per_year = st.number_input("Periods per year", min_value=1, value=252, step=1)
    if not st.button("Run backtest", type="primary"):
        return
    tickers = [ticker.strip().upper() for ticker in ticker_text.split(",") if ticker.strip()]
    if not tickers:
        st.warning("Enter at least one ticker.")
        return
    if start >= end:
        st.warning("The start date must be earlier than the exclusive end date.")
        return
    if short_window >= long_window:
        st.warning("The short window must be smaller than the long window.")
        return
    api_client = client or AlphaForgeApiClient()
    owns_client = client is None
    try:
        result = api_client.run_backtest(
            tickers,
            start,
            end,
            initial_capital=float(initial_capital),
            short_window=int(short_window),
            long_window=int(long_window),
            transaction_cost_rate=float(transaction_cost_rate),
            slippage_rate=float(slippage_rate),
            risk_free_rate=float(risk_free_rate),
            periods_per_year=int(periods_per_year),
            benchmark_ticker=benchmark.strip().upper() or None,
        )
    finally:
        if owns_client:
            api_client.close()
    _render_result(result)


def _render_result(result: ApiResult) -> None:
    if not result.successful:
        st.error(result.message)
        return
    data = result.data
    metrics = data.get("metrics")
    if not isinstance(metrics, dict):
        st.error("The backtest API returned no performance metrics.")
        return
    columns = st.columns(5)
    for column, label, key in zip(
        columns,
        ["Annualized return", "Annualized volatility", "Sharpe ratio", "Maximum drawdown", "Benchmark return"],
        ["annualized_return", "annualized_volatility", "sharpe_ratio", "max_drawdown", "benchmark_annualized_return"],
    ):
        value = metrics.get(key)
        column.metric(label, "N/A" if value is None else f"{float(value):.4f}")
    equity = _series_frame(data.get("equity"), "equity")
    if equity is not None:
        benchmark = _series_frame(data.get("benchmark_equity"), "benchmark")
        chart = equity if benchmark is None else equity.merge(benchmark, on="date", how="outer")
        st.plotly_chart(px.line(chart, x="date", y=[column for column in chart.columns if column != "date"], title="Equity curve"), use_container_width=True)
    cumulative = _series_frame(data.get("cumulative_returns"), "cumulative_returns")
    if cumulative is not None:
        st.plotly_chart(px.line(cumulative, x="date", y="cumulative_returns", title="Cumulative returns"), use_container_width=True)
    positions = data.get("positions")
    if isinstance(positions, list) and positions:
        st.subheader("Positions")
        st.dataframe(pd.DataFrame(positions), use_container_width=True, hide_index=True)
    trades = data.get("trades")
    if isinstance(trades, list):
        st.subheader("Trades")
        st.dataframe(pd.DataFrame(trades), use_container_width=True, hide_index=True)
    st.caption("Only the backend-supported moving_average_crossover strategy is available.")


def _series_frame(value: Any, name: str) -> pd.DataFrame | None:
    if not isinstance(value, list) or not value:
        return None
    frame = pd.DataFrame(value)
    if not {"date", "value"}.issubset(frame.columns):
        return None
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame[name] = pd.to_numeric(frame["value"], errors="coerce")
    return frame[["date", name]].dropna()

