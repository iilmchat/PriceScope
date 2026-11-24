"""REST-роутеры `/api/v1/*`."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pricescope_api import repositories as repo
from pricescope_api import services
from pricescope_api.config import Settings, get_settings
from pricescope_api.db.models import Product, Store
from pricescope_api.db.session import get_session
from pricescope_api.errors import ApiError
from pricescope_api.pagination import Pagination, paginate_params
from pricescope_api.schemas import (
    DecideRequest,
    ExportRequest,
    ImportRequest,
)

api = APIRouter(prefix="/api/v1")


def ok(data: object, trace_id: str = "") -> dict:
    """Успешная обёртка ответа."""
    return {"success": True, "data": data, "trace_id": trace_id}


def _product_dto(product: Product) -> dict[str, Any]:
    """Сериализация товара."""
    return {
        "id": product.id,
        "canonical_name": product.canonical_name,
        "brand": product.brand,
        "category_path": product.category_path,
        "image_urls": product.image_urls_json,
    }


def _observation_dto(item: Any) -> dict[str, Any]:
    """Сериализация наблюдения цены."""
    return {
        "id": item.id,
        "store_code": item.store_code,
        "external_id": item.external_id,
        "name": item.name,
        "price_minor": item.price_minor,
        "old_price_minor": item.old_price_minor,
        "package": item.package,
        "observed_at": item.observed_at.isoformat(),
        "raw_ref": item.raw_ref,
    }


@api.get("/stores")
async def list_stores(session: AsyncSession = Depends(get_session)) -> dict:
    """Список магазинов."""
    result = await session.execute(select(Store).order_by(Store.code))
    return ok(
        [
            {"code": s.code, "name": s.name, "currency": s.currency, "active": s.active}
            for s in result.scalars()
        ]
    )


@api.get("/products")
async def list_products(
    query: str = "",
    category: str | None = None,
    brand: str | None = None,
    sort: str = Query("id", pattern="^(id|name|created)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    pagination: Pagination = Depends(paginate_params),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Поиск канонических товаров с фильтрами, сортировкой и пагинацией."""
    conditions: list[Any] = []
    if query:
        conditions.append(Product.canonical_name.ilike(f"%{query}%"))
    if category:
        conditions.append(Product.category_path == category)
    if brand:
        conditions.append(Product.brand.ilike(f"%{brand}%"))

    stmt = select(Product)
    if conditions:
        stmt = stmt.where(*conditions)
    total = await session.scalar(select(func.count()).select_from(Product).where(*conditions))
    sort_column: Any = {
        "id": Product.id,
        "name": Product.canonical_name,
        "created": Product.created_at,
    }[sort]
    stmt = stmt.order_by(sort_column.asc() if order == "asc" else sort_column.desc())
    rows = (
        (await session.execute(stmt.limit(pagination.page_size).offset(pagination.offset)))
        .scalars()
        .all()
    )
    return ok(pagination.envelope(total or 0, [_product_dto(p) for p in rows]))


@api.get("/products/{product_id}")
async def get_product(product_id: int, session: AsyncSession = Depends(get_session)) -> dict:
    """Карточка товара."""
    product = await services.get_or_404(session, Product, product_id)
    return ok(_product_dto(product))


@api.get("/observations")
async def list_observations(
    product_id: int | None = None,
    store_code: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    pagination: Pagination = Depends(paginate_params),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """История наблюдений с фильтрами по товару, магазину и периоду."""
    conditions: list[Any] = []
    if product_id is not None:
        conditions.append(repo.Observation.product_id == product_id)
    if store_code:
        conditions.append(repo.Observation.store_code == store_code)
    if date_from:
        conditions.append(repo.Observation.observed_on >= date_from)
    if date_to:
        conditions.append(repo.Observation.observed_on <= date_to)

    stmt = select(repo.Observation)
    if conditions:
        stmt = stmt.where(*conditions)
    total = await session.scalar(
        select(func.count()).select_from(repo.Observation).where(*conditions)
    )
    stmt = stmt.order_by(repo.Observation.observed_at.desc())
    rows = (
        (await session.execute(stmt.limit(pagination.page_size).offset(pagination.offset)))
        .scalars()
        .all()
    )
    return ok(pagination.envelope(total or 0, [_observation_dto(item) for item in rows]))


@api.get("/compare")
async def compare(
    product_id: int | None = None,
    query: str | None = None,
    lat: float = 55.3925,
    lon: float = 36.7323,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Сравнение цен по магазинам около заданной точки."""
    if product_id is None and not query:
        raise ApiError(400, "INVALID_QUERY", "Укажите product_id или query")
    rows = await services.compare_prices(session, product_id, lat, lon, query)
    return ok([{**row, "observed_at": row["observed_at"].isoformat()} for row in rows])


@api.post("/imports", status_code=202)
async def create_import(
    body: ImportRequest,
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Запустить импорт."""
    result = await services.run_import(
        session, settings, body.store_code, body.lat, body.lon,
        body.categories, body.fetch_details, body.idempotency_key, body.limit,
    )
    return ok(result)


@api.get("/imports")
async def list_imports(
    pagination: Pagination = Depends(paginate_params),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Журнал запусков парсера."""
    total = await session.scalar(select(func.count()).select_from(repo.ParseRun))
    rows = (
        (
            await session.execute(
                select(repo.ParseRun)
                .order_by(repo.ParseRun.id.desc())
                .limit(pagination.page_size)
                .offset(pagination.offset)
            )
        )
        .scalars()
        .all()
    )
    return ok(
        pagination.envelope(
            total or 0,
            [
                {
                    "id": run.id,
                    "store_code": run.store_code,
                    "status": run.status,
                    "new_count": run.new_count,
                    "updated_count": run.updated_count,
                    "skipped_count": run.skipped_count,
                    "error_code": run.error_code,
                    "error_message": run.error_message,
                    "trace_id": run.trace_id,
                    "started_at": run.started_at.isoformat(),
                    "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                }
                for run in rows
            ],
        )
    )


@api.get("/imports/{run_id}")
async def get_import(run_id: int, session: AsyncSession = Depends(get_session)) -> dict:
    """Статус запуска парсера."""
    run = await services.get_or_404(session, repo.ParseRun, run_id)
    return ok({
        "id": run.id, "store_code": run.store_code, "status": run.status,
        "new_count": run.new_count, "updated_count": run.updated_count,
        "skipped_count": run.skipped_count, "error_code": run.error_code,
        "error_message": run.error_message, "trace_id": run.trace_id,
        "started_at": run.started_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    })


@api.post("/matches/run")
async def run_matching(session: AsyncSession = Depends(get_session)) -> dict:
    """Запустить entity resolution по observation без product_id."""
    return ok(await services.run_matching(session))


@api.get("/matches/review")
async def review_queue(
    pagination: Pagination = Depends(paginate_params),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Очередь спорных сопоставлений (0.70…0.90) с названиями и ценами."""
    return ok(await services.get_review_rows(session, pagination))


@api.post("/matches/{match_id}/decide")
async def decide_match(
    match_id: int, body: DecideRequest, session: AsyncSession = Depends(get_session)
) -> dict:
    """Подтвердить/отклонить совпадение."""
    return ok(await services.decide_match(session, match_id, body.confirm, body.actor))


@api.get("/metrics")
async def metrics(session: AsyncSession = Depends(get_session)) -> dict:
    """Метрики сопоставления и покрытия каталога."""
    return ok(await services.get_metrics(session))


@api.post("/exports")
async def create_export(
    body: ExportRequest,
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Сформировать датасет."""
    return ok(await services.export_dataset(session, settings, body.name, body.version))


@api.get("/exports/{export_id}")
async def get_export(export_id: int, session: AsyncSession = Depends(get_session)) -> dict:
    """Информация о выгрузке."""
    export = await services.get_or_404(session, repo.TrainingExport, export_id)
    return ok({"id": export.id, "name": export.name, "version": export.version,
               "manifest": export.manifest_json, "path": export.path})


@api.get("/exports/{export_id}/download")
async def download_export(
    export_id: int,
    file: str = Query("train.jsonl", description="Имя файла из manifest.sha256"),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    """Скачать один из файлов датасета (только перечисленные в манифесте)."""
    export = await services.get_or_404(session, repo.TrainingExport, export_id)
    allowed = (export.manifest_json or {}).get("sha256", {})
    if file not in allowed:
        raise ApiError(404, "NOT_FOUND", f"Файл {file!r} не входит в манифест")
    path = Path(export.path) / file
    if not path.is_file():
        raise ApiError(404, "NOT_FOUND", f"Файл {file!r} не найден на диске")
    return FileResponse(path, media_type="application/x-ndjson", filename=file)
