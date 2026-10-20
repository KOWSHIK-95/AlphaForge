"""Dashboard configuration loaded from environment variables."""

import os


DEFAULT_API_URL = "http://127.0.0.1:8000"
API_URL_ENVIRONMENT_VARIABLE = "ALPHAFORGE_API_URL"


def get_api_url() -> str:
    """Return the configured AlphaForge API base URL."""
    return os.environ.get(API_URL_ENVIRONMENT_VARIABLE, DEFAULT_API_URL).rstrip("/")
