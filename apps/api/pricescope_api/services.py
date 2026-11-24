"""Сервисы приложения: оркестрация импорта, сравнения, экспорта."""

from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from datetime import UTC, datetime
from math import asin, cos, radians, sin, sqrt
from typing import Any

import httpx
from pricescope_core import ParseStatus, extract_measure
from pricescope_ml.matching import (
    MODEL_VERSION,
    MatchCandidate,
    MatchResult,
    decide,
    score_candidates,
)
from pricescope_parsers.base import ParseContext
from pricescope_parsers.registry import get_parser
from pricescope_parsers.snapshots import RawSnapshotStore
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pricescope_api import repositories as repo
from pricescope_api.config import Settings
from pricescope_api.errors import ApiError
from pricescope_api.logging import current_trace_id, get_logger

logger = get_logger(__name__)


async def run_import(
    session: AsyncSession,
    settings: Settings,
    store_code: str,
    lat: float | None = None,
    lon: float | None = None,
    categories: list[str] | None = None,
    fetch_details: bool = False,
    idempotency_key: str | None = None,
    limit: int | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> dict:
    """Запустить парсер и записать результаты в БД."""
    parser = get_parser(store_code)
    if idempotency_key:
        existing = await session.execute(
            select(repo.ParseRun).where(repo.ParseRun.idempotency_key == idempotency_key)
        )
        run = existing.scalar_one_or_none()
        if run is not None:
            return {"run_id": run.id, "status": run.status, "idempotent": True}

    trace_id = current_trace_id()
    run = await repo.create_parse_run(
        session,
        store_code=store_code,
        status=ParseStatus.RUNNING,
        idempotency_key=idempotency_key,
        trace_id=trace_id,
        parser_version=parser.version,
        started_at=datetime.now(UTC),
    )
    await session.commit()

    ctx = ParseContext(
        lat=lat if lat is not None else settings.default_lat,
        lon=lon if lon is not None else settings.default_lon,
        categories=categories,
        limit=limit,
        fetch_details=fetch_details,
        trace_id=trace_id,
        parser_version=parser.version,
        http=None,
        raw_store=RawSnapshotStore(settings.raw_dir),
        photos_dir=settings.photos_dir,
    )
    new_count = updated_count = skipped_count = 0
    error_code = error_message = None
    status = ParseStatus.SUCCESS
    stack = AsyncExitStack()
    try:
        if http_client is not None:
            http = http_client
        else:
            http = await stack.enter_async_context(
                httpx.AsyncClient(timeout=20, follow_redirects=True)
            )
        ctx.http = http
        try:
            async for observation in parser.parse(ctx):
                try:
                    # SAVEPOINT: ошибка одной строки не отравляет всю транзакцию
                    async with session.begin_nested():
                        result, _ = await repo.upsert_observation(session, observation)
                    if result == "new":
                        new_count += 1
                    elif result == "updated":
                        updated_count += 1
                    # "unchanged" — повтор того же дня, счётчики не трогаем
                except Exception as exc:  # одна карточка не роняет прогон
                    skipped_count += 1
                    logger.warning("observation_skipped", error=str(exc), trace_id=trace_id)
                if (new_count + updated_count + skipped_count) % 100 == 0:
                    await session.commit()
            await session.commit()
            if ctx.location_info and status in (ParseStatus.SUCCESS, ParseStatus.PARTIAL):
                info = ctx.location_info
                await repo.upsert_store_location(
                    session,
                    store_code,
                    str(info["external_id"]),
                    ctx.lat,
                    ctx.lon,
                    info.get("address"),
                )
                await session.commit()
        except asyncio.CancelledError:
            status = ParseStatus.CANCELLED
            error_code = "CANCELLED"
            raise
        except Exception as exc:
            status = ParseStatus.FAILED
            error_code = getattr(exc, "code", type(exc).__name__)
            error_message = str(exc)
            logger.error("parse_failed", store=store_code, error=error_message, trace_id=trace_id)
            await session.rollback()  # снять PendingRollbackError перед finish_parse_run
    finally:
        # ParseRun завершается даже при отмене — иначе статус «running» висит вечно
        if skipped_count and status == ParseStatus.SUCCESS:
            status = ParseStatus.PARTIAL
        await repo.finish_parse_run(
            session,
            run.id,
            status,
            new_count=new_count,
            updated_count=updated_count,
            skipped_count=skipped_count,
            error_code=error_code,
            error_message=error_message,
        )
        await repo.audit(
            session, "parse.run", trace_id, store=store_code, status=status, run_id=run.id
        )
        await session.commit()
        await stack.aclose()

    return {
        "run_id": run.id,
        "status": status,
        "new": new_count,
        "updated": updated_count,
        "skipped": skipped_count,
        "error_code": error_code,
        "trace_id": trace_id,
    }


async def seed_stores(session: AsyncSession) -> None:
    """Заполнить справочник магазинов (идемпотентно)."""
    await repo.seed_stores(session)
    await session.commit()


async def compare_prices(
    session: AsyncSession,
    product_id: int | None,
    lat: float,
    lon: float,
    query: str | None = None,
) -> list[dict]:
    """Цены одного товара по магазинам около заданной точки.

    Для каждого магазина берётся наблюдение в ближайшей точке; если координаты
    точки неизвестны — самое свежее. Возвращает цену за кг/литр и экономию
    относительно самого дешёвого предложения.
    """
    if product_id is None and not query:
        return []
    stmt = select(repo.Observation)
    if product_id is not None:
        stmt = stmt.where(repo.Observation.product_id == product_id)
    else:
        stmt = stmt.where(repo.Observation.name.ilike(f"%{query}%"))
    observations = (
        await session.execute(stmt.order_by(repo.Observation.observed_at.desc()).limit(1000))
    ).scalars().all()
    if not observations:
        return []

    locations = {
        row.external_id: row
        for row in (await session.execute(select(repo.StoreLocation))).scalars().all()
    }
    grouped: dict[str, list[Any]] = {}
    for observation in observations:
        grouped.setdefault(observation.store_code, []).append(observation)

    rows: list[dict] = []
    for store_code, items in grouped.items():
        def order_key(item: Any) -> tuple[float, float]:
            location = locations.get(item.location_id or "")
            distance = (
                _distance_m(lat, lon, location.lat, location.lon)
                if location is not None and location.lat is not None and location.lon is not None
                else float("inf")
            )
            return distance, -item.observed_at.timestamp()

        chosen = min(items, key=order_key)
        distance, _ = order_key(chosen)
        price_per_kg, price_per_l = _unit_prices(chosen)
        rows.append(
            {
                "store_code": store_code,
                "external_id": chosen.external_id,
                "name": chosen.name,
                "location_id": chosen.location_id,
                "price_minor": chosen.price_minor,
                "price_per_kg_minor": price_per_kg,
                "price_per_l_minor": price_per_l,
                "package": chosen.package,
                "observed_at": chosen.observed_at,
                "distance_m": None if distance == float("inf") else round(distance),
                "is_cheapest": False,
                "savings_pct": 0.0,
            }
        )

    if rows:
        cheapest = min(row["price_minor"] for row in rows)
        for row in rows:
            row["is_cheapest"] = row["price_minor"] == cheapest
            if cheapest and row["price_minor"] > cheapest:
                row["savings_pct"] = round(
                    (row["price_minor"] - cheapest) * 100 / cheapest, 1
                )
    rows.sort(key=lambda row: (row["price_minor"], row["store_code"]))
    return rows


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Расстояние между координатами по формуле гаверсинуса, метры."""
    radius = 6_371_000.0
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * radius * asin(sqrt(a))


def _unit_prices(observation: Any) -> tuple[int | None, int | None]:
    """Цена за кг и за литр (если известна фасовка)."""
    value, unit = extract_measure(observation.package or "")
    if value and unit in ("мл", "л"):
        liters = value / 1000 if unit == "мл" else float(value)
        return None, round(observation.price_minor / liters) if liters else None
    if observation.net_weight_g:
        return round(observation.price_minor * 1000 / observation.net_weight_g), None
    if value and unit in ("г", "кг"):
        grams = float(value) if unit == "г" else float(value) * 1000
        return round(observation.price_minor * 1000 / grams), None
    return None, None


def _candidate(item: Any) -> MatchCandidate:
    """Observation → кандидат сопоставления."""
    return MatchCandidate(
        name=item.name,
        store_code=item.store_code,
        external_id=item.external_id,
        package=item.package,
        price_minor=item.price_minor,
        image_url=(item.image_urls_json or [None])[0],
        observed_at=item.observed_at.isoformat(),
        product_id=item.product_id,
    )


async def run_matching(session: AsyncSession, limit: int = 2000) -> dict:
    """Сопоставить observation с каноническими товарами (DESIGN_DATA_ML § 4)."""
    products = (await session.execute(select(repo.Product))).scalars().all()
    candidates = [
        MatchCandidate(
            name=product.canonical_name,
            package=(product.attributes_json or {}).get("package"),
            product_id=product.id,
        )
        for product in products
    ]
    known_products = {candidate.product_id for candidate in candidates}
    linked = (
        await session.execute(
            select(repo.Observation)
            .where(repo.Observation.product_id.is_not(None))
            .limit(2000)
        )
    ).scalars().all()
    for item in linked:
        if item.product_id not in known_products:
            candidates.append(_candidate(item))
            known_products.add(item.product_id)

    unlinked = (
        await session.execute(
            select(repo.Observation)
            .where(repo.Observation.product_id.is_(None))
            .order_by(repo.Observation.observed_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    already_matched = set(
        (await session.execute(select(repo.ProductMatch.observation_id))).scalars().all()
    )
    counts = {"auto": 0, "review": 0, "new": 0}

    for item in unlinked:
        if item.id in already_matched:
            continue
        current = _candidate(item)
        best_score, best = -1.0, None
        for candidate in candidates:
            result = score_candidates(current, candidate)
            if result.score > best_score:
                best_score, best = result.score, candidate

        decision = decide(MatchResult(score=best_score, method="lexical", same_measure=False))
        status = decision.status
        is_new = False
        if best is not None and status in ("auto", "review") and best.product_id:
            product_id, method, score = best.product_id, decision.method, best_score
        else:
            product = await repo.upsert_product(
                session,
                item.name,
                category_path=item.category_path,
                attributes_json={"package": item.package},
                image_urls_json=item.image_urls_json,
            )
            product_id, method, score, status = product.id, "new_product", 1.0, "auto"
            is_new = True
            candidate = _candidate(item)
            candidates.append(
                MatchCandidate(
                    name=candidate.name,
                    store_code=candidate.store_code,
                    external_id=candidate.external_id,
                    package=candidate.package,
                    price_minor=candidate.price_minor,
                    image_url=candidate.image_url,
                    observed_at=candidate.observed_at,
                    product_id=product.id,
                )
            )
            known_products.add(product.id)

        await repo.create_product_match(
            session,
            item.id,
            product_id,
            method=method,
            score=score,
            status=status,
            model_version=MODEL_VERSION,
        )
        if status == "auto":
            item.product_id = product_id
        counts["new" if is_new else status] += 1

    await session.commit()
    await repo.audit(session, "matching.run", current_trace_id(), counts=counts)
    await session.commit()
    return {"counts": counts, "model_version": MODEL_VERSION, "processed": sum(counts.values())}


async def get_review_rows(session: AsyncSession, pagination: Any) -> dict:
    """Очередь спорных сопоставлений с названиями и ценами."""
    condition = repo.ProductMatch.status == "review"
    total = await session.scalar(
        select(func.count()).select_from(repo.ProductMatch).where(condition)
    )
    result = await session.execute(
        select(repo.ProductMatch, repo.Observation, repo.Product)
        .join(repo.Observation, repo.ProductMatch.observation_id == repo.Observation.id)
        .outerjoin(repo.Product, repo.ProductMatch.product_id == repo.Product.id)
        .where(condition)
        .order_by(repo.ProductMatch.score.desc())
        .limit(pagination.page_size)
        .offset(pagination.offset)
    )
    items = [
        {
            "id": match.id,
            "observation_id": observation.id,
            "product_id": product.id if product else None,
            "left_name": observation.name,
            "right_name": product.canonical_name if product else None,
            "left_price_minor": observation.price_minor,
            "left_image": (observation.image_urls_json or [None])[0],
            "right_image": (product.image_urls_json or [None])[0] if product else None,
            "score": match.score,
            "method": match.method,
            "status": match.status,
        }
        for match, observation, product in result.all()
    ]
    return pagination.envelope(total or 0, items)


async def decide_match(
    session: AsyncSession, match_id: int, confirm: bool, actor: str
) -> dict:
    """Подтвердить/отклонить пару; при подтверждении связать observation."""
    match = await repo.update_match_decision(session, match_id, confirm, actor)
    if match is None:
        raise ApiError(404, "NOT_FOUND", f"ProductMatch#{match_id} не найден")
    if confirm and match.product_id is not None:
        observation = await session.get(repo.Observation, match.observation_id)
        if observation is not None:
            observation.product_id = match.product_id
    await repo.audit(session, "match.decide", "", match_id=match_id, confirm=confirm)
    await session.commit()
    return {"id": match.id, "status": match.status, "product_id": match.product_id}


async def get_metrics(session: AsyncSession) -> dict:
    """Метрики качества сопоставления и покрытия каталога."""
    total = await session.scalar(select(func.count()).select_from(repo.Observation))
    linked = await session.scalar(
        select(func.count())
        .select_from(repo.Observation)
        .where(repo.Observation.product_id.is_not(None))
    )
    status_rows = (
        await session.execute(
            select(repo.ProductMatch.status, func.count()).group_by(repo.ProductMatch.status)
        )
    ).all()
    statuses: dict[str, int] = {row[0]: row[1] for row in status_rows}
    exports = await session.scalar(select(func.count()).select_from(repo.TrainingExport))
    auto, review = statuses.get("auto", 0), statuses.get("review", 0)
    return {
        "observations": total or 0,
        "linked_observations": linked or 0,
        "coverage": round((linked or 0) / total, 3) if total else 0.0,
        "matches_by_status": statuses,
        "auto_rate": round(auto / (auto + review), 3) if auto + review else 0.0,
        "exports": exports or 0,
        "model_version": MODEL_VERSION,
    }


async def export_dataset(
    session: AsyncSession, settings: Settings, name: str, version: str
) -> dict:
    """Сформировать JSONL-датасет пар «один товар в двух магазинах»."""
    from pricescope_ml.export import build_export

    matches = (
        await session.execute(
            select(repo.ProductMatch).where(
                repo.ProductMatch.status.in_(("auto", "confirmed"))
            )
        )
    ).scalars().all()
    pairs: list[dict[str, Any]] = []
    exported_at = datetime.now(UTC).isoformat()
    for match in matches:
        if match.product_id is None:
            continue
        left = await session.get(repo.Observation, match.observation_id)
        if left is None:
            continue
        right = (
            await session.execute(
                select(repo.Observation)
                .where(
                    repo.Observation.product_id == match.product_id,
                    repo.Observation.store_code != left.store_code,
                )
                .order_by(desc(repo.Observation.observed_at))
                .limit(1)
            )
        ).scalar_one_or_none()
        if right is None:
            continue
        pairs.append(
            {
                "product_id": match.product_id,
                "left": {
                    "store": left.store_code,
                    "external_id": left.external_id,
                    "name": left.name,
                    "price_minor": left.price_minor,
                    "image_url": (left.image_urls_json or [None])[0],
                },
                "right": {
                    "store": right.store_code,
                    "external_id": right.external_id,
                    "name": right.name,
                    "price_minor": right.price_minor,
                    "image_url": (right.image_urls_json or [None])[0],
                },
                "label": "match",
                "match_method": match.method,
                "model_version": match.model_version,
                "observed_at": right.observed_at.isoformat(),
                "exported_at": exported_at,
            }
        )

    out_dir = settings.datasets_dir / f"{name}-v{version}"
    manifest = build_export(
        pairs, out_dir, name=name, version=version, extra={"pair_count": len(pairs)}
    )
    export = await repo.create_training_export(
        session, name, version, manifest, manifest.get("rows", {}), str(out_dir)
    )
    await repo.audit(session, "dataset.export", current_trace_id(), name=name, version=version)
    await session.commit()
    return {"id": export.id, "path": str(out_dir), "manifest": manifest}


async def get_or_404(session: AsyncSession, model: type, entity_id: int) -> Any:
    """Получить сущность или бросить 404."""
    entity: Any = await session.get(model, entity_id)
    if entity is None:
        raise ApiError(404, "NOT_FOUND", f"{model.__name__}#{entity_id} не найден")
    return entity
