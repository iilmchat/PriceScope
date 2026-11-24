"""Тесты Alembic-миграций (S04)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from pricescope_api.config import Settings
from pricescope_api.db import models  # noqa: F401
from pricescope_api.db.base import Base
from pricescope_api.db.session import downgrade_db, init_db
from sqlalchemy import create_engine


def _tables(path: Path) -> list[str]:
    """Список таблиц файловой SQLite БД."""
    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    return [row[0] for row in rows]


def _settings(path: Path) -> Settings:
    """Настройки под файловую БД."""
    return Settings(
        mode="local",
        db_url=f"sqlite+aiosqlite:///{path.as_posix()}",
        db_path=path,
        auto_migrate=False,
    )


async def test_upgrade_downgrade_roundtrip(tmp_path):
    """head создаёт все таблицы, base — удаляет, повторный head — восстанавливает."""
    path = tmp_path / "migration.db"
    settings = _settings(path)

    await init_db(settings)
    tables = _tables(path)
    assert "alembic_version" in tables
    assert {"stores", "observations", "parse_runs", "product_matches"} <= set(tables)

    with sqlite3.connect(path) as connection:
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    assert revision

    await downgrade_db(settings, "base")
    assert "observations" not in _tables(path)  # Alembic оставляет только alembic_version

    await init_db(settings)
    assert {"stores", "observations"} <= set(_tables(path))


async def test_legacy_db_is_stamped_without_data_loss(tmp_path):
    """БД от create_all получает stamp head без пересоздания таблиц (PL-010)."""
    path = tmp_path / "legacy.db"
    settings = _settings(path)
    engine = create_engine(settings.sync_database_url)
    Base.metadata.create_all(engine)
    engine.dispose()

    with sqlite3.connect(path) as connection:
        connection.execute("INSERT INTO stores (code, name, currency, active) VALUES (?,?,?,?)",
                           ("lenta", "Лента", "RUB", 1))
        connection.commit()

    await init_db(settings)

    with sqlite3.connect(path) as connection:
        stores = connection.execute("SELECT code FROM stores").fetchall()
        versions = connection.execute("SELECT version_num FROM alembic_version").fetchall()
    assert stores == [("lenta",)]
    assert versions
