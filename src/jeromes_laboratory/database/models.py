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


class Project(Base):
    """The durable root record for one scientific research project."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tag: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    scientific_question: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)
    question_detailing_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    question_detailing_prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
