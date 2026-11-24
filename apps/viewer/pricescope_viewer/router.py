"""Роуты локального просмотровщика."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pricescope_api.db.models import Observation, ParseRun
from pricescope_api.db.session import get_session
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_TEMPLATES = Path(__file__).parent / "templates"
_STATIC = Path(__file__).parent / "static"

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=str(_TEMPLATES))


def mount_static(app) -> None:
    """Подключить статические файлы viewer к приложению."""
    _STATIC.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request, session: AsyncSession = Depends(get_session)
) -> HTMLResponse:
    """Главная страница: обзор, товары, сравнение, импорты."""
    runs = (
        (await session.execute(select(ParseRun).order_by(ParseRun.id.desc()).limit(10)))
        .scalars()
        .all()
    )
    observations = (
        await session.execute(select(Observation).order_by(Observation.id.desc()).limit(20))
    ).scalars().all()
    return templates.TemplateResponse(
        request,
        "index.html",
        {"runs": runs, "observations": observations, "title": "PriceScope · Обзор"},
    )


@router.get("/viewer/fragments/products", response_class=HTMLResponse)
async def products_fragment(
    request: Request,
    query: str = "",
    store_code: str = "",
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """HTMX-фрагмент таблицы товаров (без перезагрузки страницы)."""
    stmt = select(Observation)
    if query:
        stmt = stmt.where(Observation.name.ilike(f"%{query}%"))
    if store_code:
        stmt = stmt.where(Observation.store_code == store_code)
    rows = (await session.execute(stmt.order_by(Observation.id.desc()).limit(100))).scalars().all()
    return templates.TemplateResponse(
        request, "fragments/products.html", {"rows": rows}
    )
