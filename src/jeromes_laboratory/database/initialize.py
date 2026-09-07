"""Apply the packaged Alembic migration chain to a workspace database."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import URL

MIGRATIONS_DIRECTORY = Path(__file__).with_name("migrations")


def database_url(database_path: Path) -> str:
    """Return a SQLite URL that correctly preserves platform-specific paths."""
    return URL.create("sqlite", database=str(database_path)).render_as_string(
        hide_password=False
    )


def upgrade_database(database_path: Path) -> None:
    """Create or upgrade a workspace database to the latest schema revision."""
    configuration = Config()
    configuration.set_main_option("script_location", str(MIGRATIONS_DIRECTORY))
    configuration.set_main_option("sqlalchemy.url", database_url(database_path))
    command.upgrade(configuration, "head")
