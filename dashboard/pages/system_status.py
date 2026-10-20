"""Streamlit System Status page."""

import streamlit as st

from dashboard.api_client import AlphaForgeApiClient
from dashboard.config import get_api_url


def render_system_status() -> None:
    """Render application liveness without claiming dependency readiness."""
    st.title("System Status")
    st.write("This check reports application liveness only; it does not verify PostgreSQL or provider availability.")
    st.button("Refresh status", type="primary")
    client = AlphaForgeApiClient()
    try:
        result = client.health()
    finally:
        client.close()
    st.caption(f"API URL: `{get_api_url()}`")
    if result.reachable:
        st.success(result.message)
        st.metric("API status", result.status or "unknown")
    else:
        st.error(result.message)
        st.info("Start the FastAPI service and refresh this page.")
