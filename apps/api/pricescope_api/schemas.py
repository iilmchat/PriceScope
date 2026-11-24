"""Pydantic-схемы REST API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ApiResponse(BaseModel):
    """Единый формат успешного ответа."""

    model_config = ConfigDict(extra="forbid")

    success: bool = True
    data: object
    trace_id: str = ""


class ErrorDetail(BaseModel):
    """Детали ошибки."""

    code: str
    message: str
    details: dict = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Единый формат ошибки."""

    success: bool = False
    error: ErrorDetail
    trace_id: str = ""


class StoreDto(BaseModel):
    """Магазин."""

    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    currency: str
    active: bool


class ProductDto(BaseModel):
    """Карточка товара."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    canonical_name: str
    brand: str | None = None
    category_path: str | None = None
    image_urls: list[str] = Field(default_factory=list)


class ObservationDto(BaseModel):
    """Наблюдение цены."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    store_code: str
    external_id: str
    name: str
    price_minor: int
    old_price_minor: int | None = None
    package: str | None = None
    observed_at: datetime
    raw_ref: str


class CompareRowDto(BaseModel):
    """Строка сравнения цен."""

    store_code: str
    price_minor: int
    price_per_kg_minor: int | None = None
    observed_at: datetime
    is_cheapest: bool = False


class ImportRequest(BaseModel):
    """Запрос на запуск импорта."""

    model_config = ConfigDict(extra="forbid")

    store_code: str
    lat: float | None = None
    lon: float | None = None
    categories: list[str] | None = None
    fetch_details: bool = False
    idempotency_key: str | None = None
    limit: int | None = Field(default=None, ge=1, le=10000)


class ParseRunDto(BaseModel):
    """Статус запуска парсера."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    store_code: str
    status: str
    new_count: int
    updated_count: int
    skipped_count: int
    error_code: str | None = None
    error_message: str | None = None
    trace_id: str
    started_at: datetime
    finished_at: datetime | None = None


class MatchRowDto(BaseModel):
    """Строка очереди сопоставлений."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    observation_id: int
    left_name: str
    right_name: str
    score: float
    method: str
    status: str


class DecideRequest(BaseModel):
    """Решение по сопоставлению."""

    model_config = ConfigDict(extra="forbid")

    confirm: bool
    actor: str = "local"


class ExportRequest(BaseModel):
    """Запрос на экспорт датасета."""

    model_config = ConfigDict(extra="forbid")

    name: str = "product-matching"
    version: str = "1"
