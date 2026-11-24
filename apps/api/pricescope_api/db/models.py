"""Модели БД PriceScope (ARCHITECTURE.md § 3)."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pricescope_api.db.base import Base, TimestampMixin


class Store(Base, TimestampMixin):
    """Магазин (источник цен)."""

    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    site_url: Mapped[str | None] = mapped_column(String(512), nullable=True)


class StoreLocation(Base, TimestampMixin):
    """Точка магазина, к которой привязаны цены."""

    __tablename__ = "store_locations"
    __table_args__ = (UniqueConstraint("store_code", "external_id", name="uq_location"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_code: Mapped[str] = mapped_column(String(32), index=True)
    external_id: Mapped[str] = mapped_column(String(64))
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    address: Mapped[str | None] = mapped_column(String(512), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(nullable=True)


class RawSnapshot(Base, TimestampMixin):
    """Исходный ответ парсера (линеаджа)."""

    __tablename__ = "raw_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    store_code: Mapped[str] = mapped_column(String(32), index=True)
    uri: Mapped[str] = mapped_column(Text)
    parser_version: Mapped[str] = mapped_column(String(32))
    path: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(index=True)


class Product(Base, TimestampMixin):
    """Канонический товар после сопоставления."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(512))
    brand: Mapped[str | None] = mapped_column(String(128), nullable=True)
    category_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    attributes_json: Mapped[dict] = mapped_column(JSON, default=dict)
    image_urls_json: Mapped[list] = mapped_column(JSON, default=list)


class Observation(Base, TimestampMixin):
    """Неизменяемый факт цены товара в магазине."""

    __tablename__ = "observations"
    __table_args__ = (
        UniqueConstraint(
            "store_code",
            "external_id",
            "location_id",
            "observed_on",
            name="uq_observation",
        ),
        Index("ix_observation_product_time", "product_id", "observed_at"),
        Index("ix_observation_store_time", "store_code", "observed_at"),
    )

    # SQLite не автоинкрементит BigInteger PK — используем INTEGER variant
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    store_code: Mapped[str] = mapped_column(String(32))
    external_id: Mapped[str] = mapped_column(String(128))
    location_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(512))
    category_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    price_minor: Mapped[int] = mapped_column(BigInteger)
    old_price_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    package: Mapped[str | None] = mapped_column(String(128), nullable=True)
    net_weight_g: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gross_weight_g: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_urls_json: Mapped[list] = mapped_column(JSON, default=list)
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    observed_at: Mapped[datetime] = mapped_column()
    observed_on: Mapped[date] = mapped_column(Date)
    raw_ref: Mapped[str] = mapped_column(String(64))
    parser_version: Mapped[str] = mapped_column(String(32))
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)

    product: Mapped[Product | None] = relationship()


class ProductMatch(Base, TimestampMixin):
    """Связь наблюдения с каноническим товаром."""

    __tablename__ = "product_matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    observation_id: Mapped[int] = mapped_column(ForeignKey("observations.id"), index=True)
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id"), nullable=True, index=True
    )
    method: Mapped[str] = mapped_column(String(32))
    score: Mapped[float] = mapped_column(Float)
    model_version: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), index=True)
    decided_by: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ParseRun(Base, TimestampMixin):
    """Журнал запуска парсера."""

    __tablename__ = "parse_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_code: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    new_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace_id: Mapped[str] = mapped_column(String(32))
    parser_version: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[datetime] = mapped_column()
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)


class TrainingExport(Base, TimestampMixin):
    """Манифест выгрузки датасета."""

    __tablename__ = "training_exports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    version: Mapped[str] = mapped_column(String(32))
    manifest_json: Mapped[dict] = mapped_column(JSON)
    rows_json: Mapped[dict] = mapped_column(JSON)
    path: Mapped[str] = mapped_column(Text)


class AuditLog(Base):
    """Аудит действий (импорт/экспорт/review)."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    actor: Mapped[str] = mapped_column(String(64), default="local")
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details_json: Mapped[dict] = mapped_column(JSON, default=dict)
    trace_id: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(index=True)
