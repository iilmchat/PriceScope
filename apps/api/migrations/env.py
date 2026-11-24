"""Alembic environment для PriceScope (синхронный движок, batch mode для SQLite)."""

# ЗАМЕЧАНИЕ: миграции применяются синхронно; async-движок используется только в API.

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Позволяет запускать alembic из корня репозитория без установки пакета
_REPO_ROOT = Path(__file__).resolve().parents[3]
for path in (
    _REPO_ROOT,
    _REPO_ROOT / "apps" / "api",
    _REPO_ROOT / "apps" / "viewer",
    _REPO_ROOT / "packages" / "core",
    _REPO_ROOT / "packages" / "parsers",
    _REPO_ROOT / "packages" / "ml",
):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from pricescope_api.config import get_settings  # noqa: E402
from pricescope_api.db import models  # noqa: E402,F401 — регистрация моделей
from pricescope_api.db.base import Base  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
# Явный URL из приложения (тесты/CLI) имеет приоритет над env-настройками
_url = config.attributes.get("pricescope_url")
if not _url:
    _settings = get_settings()
    _settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    _url = _settings.sync_database_url
elif _url.startswith("sqlite:///"):
    Path(_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
config.set_main_option("sqlalchemy.url", _url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Сформировать SQL без подключения к БД."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Применить миграции через синхронный движок."""
    engine = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
