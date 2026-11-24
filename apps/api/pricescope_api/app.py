"""Фабрика FastAPI-приложения."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from pricescope_api import __version__
from pricescope_api.config import PROJECT_ROOT, Settings, get_settings
from pricescope_api.logging import configure_logging
from pricescope_api.middleware import ObservabilityMiddleware, register_error_handlers
from pricescope_api.routers import api


def create_app(settings: Settings | None = None) -> FastAPI:
    """Создать приложение с роутерами, middleware и lifespan."""
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        from pricescope_api.db.session import get_sessionmaker, init_db
        from pricescope_api.services import seed_stores

        if settings.is_local and settings.auto_migrate:
            await init_db(settings)
        if settings.auto_migrate:
            async with get_sessionmaker()() as session:
                await seed_stores(session)
        app.state.settings = settings
        yield

    app = FastAPI(
        title="PriceScope API",
        version=__version__,
        description="Сбор, хранение и сравнение цен товаров",
        lifespan=lifespan,
    )
    app.add_middleware(ObservabilityMiddleware)
    register_error_handlers(app)
    app.include_router(api)

    @app.get("/health", tags=["system"])
    async def health() -> dict:
        """Проверка доступности приложения."""
        return {
            "status": "ok",
            "version": __version__,
            "mode": settings.mode,
            "service": "pricescope-api",
        }

    # Локальный просмотровщик подключается тем же приложением
    try:
        from pricescope_viewer.router import mount_static
        from pricescope_viewer.router import router as viewer_router

        app.include_router(viewer_router)
        mount_static(app)
    except ImportError:
        pass

    # Дозагруженные фото (data/photos) и legacy-каталог (~10 ГБ) — только чтение
    settings.photos_dir.mkdir(parents=True, exist_ok=True)
    app.mount(
        "/photos",
        StaticFiles(directory=str(settings.photos_dir)),
        name="photos",
    )
    legacy_photos = PROJECT_ROOT / "photos"
    if legacy_photos.is_dir():
        app.mount(
            "/legacy-photos",
            StaticFiles(directory=str(legacy_photos)),
            name="legacy-photos",
        )

    return app


app = create_app()
