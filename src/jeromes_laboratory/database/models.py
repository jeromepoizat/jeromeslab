"""SQLAlchemy metadata for the local application database."""

from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all application tables."""


class ApplicationMetadata(Base):
    """Small schema-owned values reserved for application-level metadata."""

    __tablename__ = "application_metadata"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
