"""Базовый класс моделей SQLAlchemy 2."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    """Текущее время UTC (используется как Python-side default)."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Общий базовый класс всех моделей."""


class TimestampMixin:
    """Миксин с полями создания/обновления."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
