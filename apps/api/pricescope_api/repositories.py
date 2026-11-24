"""Репозитории: работа с БД без бизнес-логики."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pricescope_core import ProductObservation
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from pricescope_api.db.models import (
    AuditLog,
    Observation,
    ParseRun,
    Product,
    ProductMatch,
    RawSnapshot,
    Store,
    StoreLocation,
    TrainingExport,
)


async def upsert_observation(
    session: AsyncSession, observation: ProductObservation, product_id: int | None = None
) -> tuple[str, int | None]:
    """Вставить или обновить observation.

    Возвращает (`new|updated|unchanged`, id). Явный SELECT перед записью нужен,
    потому что `rowcount` ON CONFLICT DO UPDATE одинаков для insert и update
    (этот баг проявился в интеграционном тесте S03).
    """
    values = {
        "store_code": observation.store_code,
        "external_id": observation.external_id,
        "location_id": observation.location_id,
        "name": observation.name,
        "category_path": observation.category_path,
        "price_minor": observation.price_minor,
        "old_price_minor": observation.old_price_minor,
        "currency": observation.currency,
        "package": observation.package,
        "net_weight_g": observation.net_weight_g,
        "gross_weight_g": observation.gross_weight_g,
        "image_urls_json": observation.image_urls,
        "available": observation.available,
        "observed_at": observation.observed_at,
        "observed_on": observation.observed_at.date(),
        "raw_ref": observation.raw_ref,
        "parser_version": observation.parser_version,
        "schema_version": observation.schema_version,
        "content_hash": observation.content_hash,
        "updated_at": datetime.now(UTC),
    }
    if product_id is not None:
        values["product_id"] = product_id
    conditions = [
        Observation.store_code == observation.store_code,
        Observation.external_id == observation.external_id,
        Observation.observed_on == observation.observed_at.date(),
    ]
    if observation.location_id is None:
        conditions.append(Observation.location_id.is_(None))
    else:
        conditions.append(Observation.location_id == observation.location_id)

    found = (
        await session.execute(
            select(Observation.id, Observation.content_hash).where(*conditions)
        )
    ).one_or_none()
    if found is None:
        entity = Observation(**values)
        session.add(entity)
        await session.flush()
        return "new", entity.id
    if found.content_hash == observation.content_hash:
        return "unchanged", found.id

    await session.execute(
        update(Observation).where(Observation.id == found.id).values(**values)
    )
    await session.flush()
    return "updated", found.id


async def create_parse_run(session: AsyncSession, **kwargs: Any) -> ParseRun:
    """Создать запись о запуске парсера."""
    run = ParseRun(**kwargs)
    session.add(run)
    await session.flush()
    return run


async def finish_parse_run(
    session: AsyncSession, run_id: int, status: str, **kwargs: Any
) -> None:
    """Завершить запуск парсера."""
    values = {"status": status, "finished_at": datetime.now(UTC), **kwargs}
    await session.execute(update(ParseRun).where(ParseRun.id == run_id).values(**values))


async def raw_snapshot_exists(session: AsyncSession, sha256: str) -> bool:
    """Проверить, сохранён ли уже raw snapshot."""
    result = await session.execute(
        select(RawSnapshot.id).where(RawSnapshot.sha256 == sha256)
    )
    return result.scalar_one_or_none() is not None


async def audit(session: AsyncSession, action: str, trace_id: str, **details: Any) -> None:
    """Записать действие в аудит."""
    session.add(
        AuditLog(
            action=action,
            actor="local",
            trace_id=trace_id,
            details_json=details,
            created_at=datetime.now(UTC),
        )
    )


async def update_match_decision(
    session: AsyncSession, match_id: int, confirm: bool, actor: str
) -> ProductMatch | None:
    """Сохранить решение по сопоставлению."""
    result = await session.execute(select(ProductMatch).where(ProductMatch.id == match_id))
    match = result.scalar_one_or_none()
    if match is None:
        return None
    match.status = "confirmed" if confirm else "rejected"
    match.decided_by = actor
    await session.flush()
    return match


async def create_product_match(
    session: AsyncSession,
    observation_id: int,
    product_id: int | None,
    *,
    method: str,
    score: float,
    status: str,
    model_version: str,
) -> ProductMatch:
    """Записать решение сопоставления."""
    match = ProductMatch(
        observation_id=observation_id,
        product_id=product_id,
        method=method,
        score=score,
        status=status,
        model_version=model_version,
    )
    session.add(match)
    await session.flush()
    return match


async def create_training_export(
    session: AsyncSession, name: str, version: str, manifest: dict, rows: dict, path: str
) -> TrainingExport:
    """Зарегистрировать выгрузку датасета."""
    export = TrainingExport(
        name=name, version=version, manifest_json=manifest, rows_json=rows, path=path
    )
    session.add(export)
    await session.flush()
    return export


async def upsert_store_location(
    session: AsyncSession,
    store_code: str,
    external_id: str,
    lat: float | None,
    lon: float | None,
    address: str | None = None,
) -> StoreLocation:
    """Сохранить точку магазина, к которой привязаны цены."""
    found = (
        await session.execute(
            select(StoreLocation).where(
                StoreLocation.store_code == store_code,
                StoreLocation.external_id == external_id,
            )
        )
    ).scalar_one_or_none()
    if found is None:
        found = StoreLocation(
            store_code=store_code,
            external_id=external_id,
            lat=lat,
            lon=lon,
            address=address,
            last_used_at=datetime.now(UTC),
        )
        session.add(found)
    else:
        found.lat = lat
        found.lon = lon
        found.address = address
        found.last_used_at = datetime.now(UTC)
    await session.flush()
    return found


async def seed_stores(session: AsyncSession) -> None:
    """Создать справочник магазинов при первом запуске."""
    defaults = (
        ("lenta", "Лента", "https://lenta.com"),
        ("pyaterochka", "Пятёрочка", "https://5ka.ru"),
        ("manual", "Ручной импорт", None),
    )
    for code, name, url in defaults:
        exists = await session.scalar(select(Store.id).where(Store.code == code))
        if exists is None:
            session.add(Store(code=code, name=name, site_url=url, currency="RUB", active=True))
    await session.flush()


async def upsert_product(session: AsyncSession, name: str, **fields: Any) -> Product:
    """Создать канонический товар (упрощённый вариант для v0.1)."""
    result = await session.execute(select(Product).where(Product.canonical_name == name))
    product = result.scalar_one_or_none()
    if product is None:
        product = Product(canonical_name=name, **fields)
        session.add(product)
        await session.flush()
    return product
