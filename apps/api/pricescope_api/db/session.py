"""Движок, сессии SQLAlchemy и инициализация схемы через Alembic."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from pricescope_api.config import Settings, get_settings
from pricescope_api.db import models  # noqa: F401 — регистрация моделей в metadata

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None
_ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def get_engine(settings: Settings | None = None) -> AsyncEngine:
    """Создать (один раз) асинхронный движок."""
    global _engine
    if _engine is None:
        settings = settings or get_settings()
        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_async_engine(settings.database_url, echo=False, future=True)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Создать фабрику сессий."""
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    """Зависимость FastAPI: одна сессия на запрос (UoW)."""
    async with get_sessionmaker()() as session:
        yield session


def _alembic_config(settings: Settings) -> Config:
    """Собрать конфиг Alembic с явным URL БД."""
    config = Config(str(_ALEMBIC_INI))
    config.set_main_option("script_location", str(_ALEMBIC_INI.parent / "migrations"))
    config.attributes["pricescope_url"] = settings.sync_database_url
    return config


def _upgrade_sync(settings: Settings, *, revision: str = "head") -> None:
    """Применить миграции (синхронно, вызывается через to_thread)."""
    config = _alembic_config(settings)
    engine = create_engine(settings.sync_database_url)
    try:
        tables = inspect(engine).get_table_names()
        if tables and "alembic_version" not in tables:
            # Унаследованная БД от create_all (до S04) — перехватываем версию,
            # не пересоздавая таблицы и не теряя историю цен.
            command.stamp(config, "head")
        else:
            command.upgrade(config, revision)
    finally:
        engine.dispose()


def _downgrade_sync(settings: Settings, revision: str = "base") -> None:
    """Откатить миграции (только для тестов)."""
    command.downgrade(_alembic_config(settings), revision)


async def init_db(settings: Settings | None = None) -> None:
    """Применить Alembic-миграции к БД приложения."""
    await asyncio.to_thread(_upgrade_sync, settings or get_settings())


async def downgrade_db(settings: Settings, revision: str = "base") -> None:
    """Откатить схему (тесты, локальная разработка)."""
    await asyncio.to_thread(_downgrade_sync, settings, revision)
