import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def create_database_engine() -> Engine:
    """Create the PostgreSQL engine using ``ALPHAFORGE_DATABASE_URL``."""
    database_url = os.environ.get("ALPHAFORGE_DATABASE_URL")
    if not database_url:
        raise RuntimeError("ALPHAFORGE_DATABASE_URL must be set to connect to PostgreSQL.")
    if not database_url.startswith("postgresql+psycopg://"):
        raise ValueError("ALPHAFORGE_DATABASE_URL must use the postgresql+psycopg scheme.")
    return create_engine(database_url, pool_pre_ping=True)
