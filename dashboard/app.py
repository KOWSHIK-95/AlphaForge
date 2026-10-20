"""AlphaForge Streamlit dashboard entry point."""

import streamlit as st

from dashboard.api_client import AlphaForgeApiClient
from dashboard.config import get_api_url
from dashboard.pages.market_data import render_market_data


def main() -> None:
    """Render the dashboard overview page."""
    st.set_page_config(
        page_title="AlphaForge Overview",
        page_icon="📈",
        layout="wide",
    )
    st.title("AlphaForge")
    st.caption("Quantitative finance analysis dashboard")

    page = st.sidebar.radio("Page", ["Overview", "Market Data"])
    if page == "Market Data":
        render_market_data()
        return

    st.subheader("Overview")
    st.write("Check the availability of the AlphaForge API before using analysis pages.")

    client = AlphaForgeApiClient()
    try:
        health = client.health()
    finally:
        client.close()

    st.caption(f"API URL: `{get_api_url()}`")
    if health.reachable:
        st.success(health.message)
        st.metric("API status", health.status or "unknown")
    else:
        st.error(health.message)
        st.info("Start the API with Uvicorn, then refresh this page.")


if __name__ == "__main__":
    main()
