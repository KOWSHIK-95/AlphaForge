import os

from alembic import context
from sqlalchemy import engine_from_config, pool

from alphaforge.database.models import metadata


config = context.config
target_metadata = metadata


def _database_url() -> str:
    url = os.environ.get("ALPHAFORGE_DATABASE_URL")
    if not url:
        raise RuntimeError("ALPHAFORGE_DATABASE_URL must be set before running migrations.")
    if not url.startswith("postgresql+psycopg://"):
        raise ValueError("ALPHAFORGE_DATABASE_URL must use the postgresql+psycopg scheme.")
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _database_url().replace("%", "%%")
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
