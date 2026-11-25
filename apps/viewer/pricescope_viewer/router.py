"""Роуты локального просмотровщика PriceScope (Jinja2 + HTMX)."""

from __future__ import annotations

from html import escape
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pricescope_api.config import get_settings
from pricescope_api.db.models import Observation, ParseRun, ProductMatch
from pricescope_api.db.session import get_session
from pricescope_api.errors import ApiError
from pricescope_api.pagination import Pagination
from pricescope_api.search import matches
from pricescope_api.services import (
    apply_bulk_decision,
    compare_prices,
    decide_match,
    get_review_rows,
)
from pricescope_core import MatchStatus, format_rub
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

_TEMPLATES = Path(__file__).parent / "templates"
_STATIC = Path(__file__).parent / "static"

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=str(_TEMPLATES))


def mount_static(app) -> None:
    """Подключить статические файлы viewer к приложению."""
    _STATIC.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")


def _render(request: Request, name: str, context: dict, status: int = 200) -> HTMLResponse:
    """Отрендерить шаблон с базовым контекстом."""
    return templates.TemplateResponse(
        request, name, {**context, "format_rub": format_rub}, status_code=status
    )


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request, session: AsyncSession = Depends(get_session)
) -> HTMLResponse:
    """Обзор: последние импорты, счётчики, быстрые ссылки."""
    runs = (
        (await session.execute(select(ParseRun).order_by(ParseRun.id.desc()).limit(10)))
        .scalars()
        .all()
    )
    observation_count = await session.scalar(select(func.count()).select_from(Observation))
    product_count = await session.scalar(
        select(func.count()).select_from(ProductMatch).where(
            ProductMatch.status == MatchStatus.CONFIRMED
        )
    )
    return _render(
        request,
        "index.html",
        {
            "title": "PriceScope · Обзор",
            "runs": runs,
            "observation_count": observation_count or 0,
            "product_count": product_count or 0,
            "active": "overview",
        },
    )


async def _observation_page(
    session: AsyncSession,
    *,
    query: str,
    store_code: str,
    category: str,
    page: int,
    page_size: int,
) -> dict:
    """Выборка observation с фильтрами и пагинацией."""
    conditions = []
    if store_code:
        conditions.append(Observation.store_code == store_code)
    if category:
        conditions.append(Observation.category_path == category)
    stmt = select(Observation)
    if conditions:
        stmt = stmt.where(*conditions)
    rows = list(
        (
            await session.execute(stmt.order_by(Observation.observed_at.desc()))
        )
        .scalars()
        .all()
    )
    # ILIKE в SQLite не понимает кириллицу — фильтруем через casefold
    if query:
        rows = [row for row in rows if matches(row.name, query)]
    total = len(rows)
    rows = rows[(page - 1) * page_size : (page - 1) * page_size + page_size]
    return Pagination(page=page, page_size=page_size).envelope(total, rows)


@router.get("/products", response_class=HTMLResponse)
async def products_page(
    request: Request, session: AsyncSession = Depends(get_session)
) -> HTMLResponse:
    """Страница каталога с фильтрами (фрагмент подгружается HTMX)."""
    categories = (
        await session.execute(
            select(Observation.category_path, func.count())
            .where(Observation.category_path.is_not(None))
            .where(Observation.category_path != "")
            .group_by(Observation.category_path)
            .order_by(Observation.category_path)
        )
    ).all()
    return _render(
        request,
        "products.html",
        {
            "title": "PriceScope · Товары",
            "active": "products",
            "categories": [{"name": name, "count": count} for name, count in categories],
        },
    )


@router.get("/viewer/fragments/products", response_class=HTMLResponse)
async def products_fragment(
    request: Request,
    query: str = "",
    store_code: str = "",
    category: str = "",
    page: int = 1,
    page_size: int = 20,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """HTMX-фрагмент таблицы товаров."""
    result = await _observation_page(
        session,
        query=query,
        store_code=store_code,
        category=category,
        page=max(1, page),
        page_size=min(200, max(1, page_size)),
    )
    return _render(
        request,
        "fragments/products.html",
        {"result": result, "query": query, "store_code": store_code, "category": category},
    )


@router.get("/product", response_class=HTMLResponse)
async def product_card(
    request: Request,
    external_id: str,
    store_code: str = "",
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Карточка товара: атрибуты, история цен, график."""
    conditions = [Observation.external_id == external_id]
    if store_code:
        conditions.append(Observation.store_code == store_code)
    rows = (
        (
            await session.execute(
                select(Observation).where(*conditions).order_by(Observation.observed_at)
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        return _render(
            request,
            "product.html",
            {"title": "Товар не найден", "observation": None, "chart": "", "active": "products"},
            status=404,
        )
    latest = rows[-1]
    points = [(row.observed_at.strftime("%d.%m"), row.price_minor) for row in rows]

    images: list[str] = []
    for row in reversed(rows):
        for url in row.image_urls_json or []:
            if url and url not in images:
                images.append(url)
        if row.photo_path and row.photo_path not in images:
            images.insert(0, row.photo_path)
    if latest.photo_path and latest.photo_path in images:
        images.remove(latest.photo_path)
        images.insert(0, latest.photo_path)

    settings = get_settings()
    comparison = await compare_prices(
        session, None, settings.default_lat, settings.default_lon, query=latest.name
    )
    return _render(
        request,
        "product.html",
        {
            "title": f"PriceScope · {latest.name}",
            "observation": latest,
            "history": list(reversed(rows)),
            "chart": _price_svg(points),
            "images": images,
            "comparison": comparison,
            "active": "products",
        },
    )


@router.get("/compare", response_class=HTMLResponse)
async def compare_page(
    request: Request,
    query: str = "",
    lat: float = 55.3925,
    lon: float = 36.7323,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Сравнение цен в магазинах рядом с точкой."""
    rows = []
    if query:
        rows = await compare_prices(session, None, lat, lon, query)
    return _render(
        request,
        "compare.html",
        {
            "title": "PriceScope · Сравнение",
            "rows": rows,
            "query": query,
            "lat": lat,
            "lon": lon,
            "store_names": {
                "lenta": "Лента",
                "pyaterochka": "Пятёрочка",
                "manual": "Ручной импорт",
            },
            "active": "compare",
        },
    )


@router.get("/imports", response_class=HTMLResponse)
async def imports_page(
    request: Request, page: int = 1, session: AsyncSession = Depends(get_session)
) -> HTMLResponse:
    """Журнал импортов."""
    total = await session.scalar(select(func.count()).select_from(ParseRun))
    rows = (
        (
            await session.execute(
                select(ParseRun)
                .order_by(ParseRun.id.desc())
                .limit(20)
                .offset((max(1, page) - 1) * 20)
            )
        )
        .scalars()
        .all()
    )
    return _render(
        request,
        "imports.html",
        {
            "title": "PriceScope · Импорты",
            "result": Pagination(page=max(1, page), page_size=20).envelope(total or 0, list(rows)),
            "active": "imports",
        },
    )


@router.get("/matches", response_class=HTMLResponse)
async def matches_page(
    request: Request, session: AsyncSession = Depends(get_session)
) -> HTMLResponse:
    """Очередь спорных сопоставлений товаров."""
    result = await get_review_rows(session, Pagination(page=1, page_size=50))
    return _render(
        request,
        "matches.html",
        {"title": "PriceScope · Совпадения", "result": result, "active": "matches"},
    )


@router.post("/viewer/matches/apply", response_class=HTMLResponse)
async def matches_apply(
    request: Request,
    min_score: float = 0.0,
    max_score: float = 1.0,
    confirm: bool = True,
    limit: int = 1000,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Массово решить пары в диапазоне confidence и обновить список."""
    counts = await apply_bulk_decision(
        session,
        min_score=min_score,
        max_score=max_score,
        confirm=confirm,
        limit=limit,
        actor="viewer",
    )
    result = await get_review_rows(session, Pagination(page=1, page_size=50))
    return _render(
        request,
        "fragments/match_list.html",
        {"result": result, "banner": counts},
    )


@router.post("/viewer/matches/{match_id}/decide", response_class=HTMLResponse)
async def match_decide(
    request: Request,
    match_id: int,
    confirm: bool = True,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Подтвердить/отклонить совпадение и вернуть обновлённую строку."""
    try:
        decision = await decide_match(session, match_id, confirm, "viewer")
    except ApiError:
        return _render(request, "fragments/match_row.html", {"row": None})
    match = await session.get(ProductMatch, match_id)
    if match is None:
        return _render(request, "fragments/match_row.html", {"row": None})
    return _render(
        request,
        "fragments/match_row.html",
        {
            "row": {
                "id": match.id,
                "observation_id": match.observation_id,
                "product_id": match.product_id,
                "method": match.method,
                "score": match.score,
                "status": decision["status"],
            }
        },
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request) -> HTMLResponse:
    """Информация о локальном режиме и подключении."""
    return _render(
        request,
        "settings.html",
        {"title": "PriceScope · Настройки", "active": "settings"},
    )


def _price_svg(points: list[tuple[str, int]], width: int = 640, height: int = 180) -> str:
    """Простой SVG-график цены без внешних JS-библиотек."""
    if not points:
        return ""
    prices = [price for _, price in points]
    low, high = min(prices), max(prices)
    span = high - low or 1
    pad_x, pad_y = 46, 22
    plot_w, plot_h = width - pad_x - 12, height - pad_y - 26

    def x(index: int) -> float:
        return pad_x + (plot_w * index / max(1, len(points) - 1))

    def y(price: int) -> float:
        return pad_y + plot_h - (plot_h * (price - low) / span)

    line = " ".join(f"{x(i):.1f},{y(price):.1f}" for i, (_, price) in enumerate(points))
    dots = "".join(
        f'<circle cx="{x(i):.1f}" cy="{y(price):.1f}" r="2.5" class="dot"/>'
        for i, (_, price) in enumerate(points)
    )
    axis = (
        f'<line x1="{pad_x}" y1="{pad_y + plot_h}" x2="{width - 12}" '
        f'y2="{pad_y + plot_h}" class="axis"/>'
    )
    labels = (
        f'<text x="4" y="{pad_y + 8}" class="label">{escape(format_rub(high))}</text>'
        f'<text x="4" y="{pad_y + plot_h}" class="label">{escape(format_rub(low))}</text>'
        f'<text x="{pad_x}" y="{height - 4}" class="label">{escape(points[0][0])}</text>'
        f'<text x="{width - 54}" y="{height - 4}" class="label">{escape(points[-1][0])}</text>'
    )
    return (
        f'<svg class="price-chart" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="График цены">'
        f"{axis}<polyline points=\"{line}\" class=\"line\"/>{dots}{labels}</svg>"
    )
