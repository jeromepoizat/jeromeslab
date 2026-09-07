"""Alembic environment for Jerome's Laboratory workspace databases."""

from __future__ import annotations

from alembic import context
from sqlalchemy import engine_from_config, pool

from jeromes_laboratory.database.models import Base

configuration = context.config
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without creating an engine."""
    url = configuration.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations using a short-lived SQLite connection."""
    connectable = engine_from_config(
        configuration.get_section(configuration.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
