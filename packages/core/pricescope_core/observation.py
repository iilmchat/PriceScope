"""Версионированный контракт `ProductObservation` v1 (ADR-001)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from pricescope_core.hashing import canonical_hash

SCHEMA_VERSION: Final[Literal[1]] = 1


class ProductObservation(BaseModel):
    """Одно наблюдение цены товара в магазине в момент времени.

    Все суммы — целые копейки (`*_minor`), время — UTC.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = SCHEMA_VERSION
    store_code: str
    external_id: str
    location_id: str | None = None
    name: str
    brand: str | None = None
    category_path: str | None = None
    price_minor: int = Field(ge=0)
    old_price_minor: int | None = Field(default=None, ge=0)
    currency: Literal["RUB"] = "RUB"
    package: str | None = None
    net_weight_g: int | None = None
    gross_weight_g: int | None = None
    image_urls: list[str] = Field(default_factory=list)
    product_url: str | None = None
    available: bool = True
    observed_at: datetime
    raw_ref: str
    parser_version: str
    content_hash: str = ""

    @field_validator("store_code", "external_id", "name", "raw_ref", "parser_version")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Поле не может быть пустым")
        return value.strip()

    @field_validator("observed_at")
    @classmethod
    def _ensure_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def with_hash(self) -> ProductObservation:
        """Возвращает копию с посчитанным `content_hash`.

        Хэш считается по каноническому представлению без самого хэша и с датой
        наблюдения (не временем), чтобы повторный запуск в тот же день не
        создавал дубликат.
        """
        payload = self.model_dump(mode="json", exclude={"content_hash"})
        payload["observed_on"] = self.observed_at.date().isoformat()
        payload.pop("observed_at", None)
        return self.model_copy(update={"content_hash": canonical_hash(payload)})
