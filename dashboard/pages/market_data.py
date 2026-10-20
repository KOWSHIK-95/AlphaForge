"""Streamlit Market Data page."""

from datetime import date, timedelta
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.api_client import AlphaForgeApiClient, MarketDataResult


def render_market_data(client: AlphaForgeApiClient | None = None) -> None:
    """Render controls and results for historical market data."""
    st.title("Market Data")
    st.write(
        "Request validated historical daily bars from the AlphaForge API. "
        "The start date is inclusive and the end date is exclusive."
    )

    ticker_text = st.text_input("Ticker symbols", value="AAPL, MSFT")
    today = date.today()
    start = st.date_input("Start date", value=today - timedelta(days=365))
    end = st.date_input("End date (exclusive)", value=today)
    include_returns = st.checkbox("Include returns", value=True)

    if not st.button("Load market data", type="primary"):
        return

    tickers = [ticker.strip() for ticker in ticker_text.split(",")]
    validation_error = _validate_controls(tickers, start, end)
    if validation_error:
        st.warning(validation_error)
        return

    api_client = client or AlphaForgeApiClient()
    owns_client = client is None
    try:
        result = api_client.market_data_history(
            tickers,
            start,
            end,
            include_returns=include_returns,
        )
    except (TypeError, ValueError) as error:
        st.warning(str(error))
        return
    finally:
        if owns_client:
            api_client.close()

    _render_result(result, include_returns=include_returns)


def _validate_controls(tickers: list[str], start: date, end: date) -> str | None:
    if not any(ticker.strip() for ticker in tickers):
        return "Enter at least one ticker symbol."
    if any(len(ticker.strip()) > 32 for ticker in tickers):
        return "Ticker symbols must be at most 32 characters."
    if start >= end:
        return "The start date must be earlier than the exclusive end date."
    return None


def _render_result(result: MarketDataResult, *, include_returns: bool) -> None:
    if not result.successful:
        if result.status_code == 404 or not result.data:
            st.info(result.message)
        else:
            st.error(result.message)
        return

    frame = pd.DataFrame(result.data)
    if frame.empty:
        st.info("No market data was returned for the requested range.")
        return
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    if frame["date"].isna().any() or "ticker" not in frame or "close" not in frame:
        st.error("The API returned market data in an unexpected format.")
        return

    st.success(f"Loaded {result.count} market-data rows.")
    chart_data = frame.dropna(subset=["date", "close"])
    if chart_data.empty:
        st.warning("No valid close prices are available to chart.")
    else:
        figure = px.line(
            chart_data,
            x="date",
            y="close",
            color="ticker",
            title="Historical closing prices",
            labels={"date": "Date", "close": "Close price", "ticker": "Ticker"},
        )
        st.plotly_chart(figure, use_container_width=True)

    if include_returns and "returns" in frame:
        return_data = frame[["date", "ticker", "returns"]].dropna(subset=["returns"])
        if return_data.empty:
            st.info("No valid returns are available for the returned observations.")
        else:
            return_figure = px.line(
                return_data,
                x="date",
                y="returns",
                color="ticker",
                title="Historical returns",
                labels={"date": "Date", "returns": "Return", "ticker": "Ticker"},
            )
            st.plotly_chart(return_figure, use_container_width=True)

    display_frame = frame.copy()
    display_frame["date"] = display_frame["date"].dt.strftime("%Y-%m-%d")
    st.dataframe(display_frame, use_container_width=True, hide_index=True)
