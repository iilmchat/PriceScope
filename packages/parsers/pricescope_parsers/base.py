"""Порт `StoreParser` и контекст прогона (ADR-002)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

import httpx
from pricescope_core import ProductObservation

from pricescope_parsers.snapshots import RawSnapshotStore


@dataclass(frozen=True)
class ParserCapabilities:
    """Возможности адаптера — нужны планировщику и UI."""

    requires_browser: bool = False
    requires_location: bool = False
    supports_images: bool = True
    max_requests_per_minute: int = 60


@dataclass
class ParseContext:
    """Контекст одного запуска парсера.

    Содержит конфигурацию точки, общий HTTP-клиент, хранилище снапшотов,
    trace_id и событие отмены. Адаптер не должен создавать свои клиенты.
    """

    lat: float = 55.3925
    lon: float = 36.7323
    categories: list[str] | None = None
    limit: int | None = None
    fetch_details: bool = False
    trace_id: str = ""
    parser_version: str = "0.1.0"
    http: httpx.AsyncClient | None = None
    raw_store: RawSnapshotStore | None = None
    cancellation: asyncio.Event = field(default_factory=asyncio.Event)
    photos_dir: Path | None = None
    browser_snapshot: dict | None = None  # фикстура / результат браузера (S06)
    location_info: dict | None = None  # метаданные точки, заполняет адаптер (hub)

    def check_cancelled(self) -> None:
        """Проверить внешнюю отмену (RULES § 4.5)."""
        if self.cancellation.is_set():
            raise asyncio.CancelledError("Прогон парсера отменён")

    async def save_raw(
        self,
        store_code: str,
        payload: bytes,
        uri: str,
        content_type: str = "application/json",
    ) -> str:
        """Сохранить исходный ответ и вернуть его sha256."""
        if self.raw_store is None:
            raise RuntimeError("RawSnapshotStore не сконфигурирован в ParseContext")
        return await self.raw_store.save_async(store_code, payload, uri, content_type)


@runtime_checkable
class StoreParser(Protocol):
    """Контракт адаптера магазина. Реализации регистрируются в registry."""

    name: str
    version: str

    def capabilities(self) -> ParserCapabilities: ...
    async def health_check(self) -> bool: ...
    def parse(self, ctx: ParseContext) -> AsyncIterator[ProductObservation]: ...
