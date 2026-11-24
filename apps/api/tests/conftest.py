"""Общие фикстуры тестов (БД в памяти, без сети)."""

from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pricescope_api.app import create_app
from pricescope_api.config import Settings
from pricescope_api.db import models  # noqa: F401
from pricescope_api.db.base import Base
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def client():
    """Тестовый HTTP-клиент с изолированной SQLite in-memory БД."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    test_sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    import pricescope_api.db.session as session_module

    original = session_module._sessionmaker
    session_module._sessionmaker = test_sessionmaker
    settings = Settings(mode="local", db_url="sqlite+aiosqlite:///:memory:", auto_migrate=False)

    # Справочник магазинов нужен многим экранам/тестам
    async with test_sessionmaker() as seed_session:
        from pricescope_api.repositories import seed_stores

        await seed_stores(seed_session)

    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client

    session_module._sessionmaker = original
    await engine.dispose()
