"""Конфигурация через Pydantic Settings (секреты — только env)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# config.py: apps/api/pricescope_api/config.py → parents[3] — корень репозитория
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _resolve_path(value: Path) -> Path:
    """Относительные пути — от корня проекта, а не от CWD (PL-013)."""
    return value if value.is_absolute() else (PROJECT_ROOT / value).resolve()


class Settings(BaseSettings):
    """Настройки приложения. env-префикс `PRICESCOPE_`."""

    model_config = SettingsConfigDict(
        env_prefix="PRICESCOPE_",
        env_file=".env",
        extra="ignore",
        validate_default=True,  # пути по умолчанию тоже проходят валидатор
    )

    mode: str = "local"
    db_path: Path = Field(default=Path("data/pricescope.db"))
    db_url: str = ""
    host: str = "127.0.0.1"
    port: int = 8775
    raw_dir: Path = Field(default=Path("data/raw"))
    photos_dir: Path = Field(default=Path("data/photos"))
    datasets_dir: Path = Field(default=Path("datasets"))
    log_level: str = "INFO"
    default_lat: float = 55.3925
    default_lon: float = 36.7323
    raw_retention_days: int = 90
    auto_migrate: bool = True  # тесты отключают: схема создаётся фикстурой
    # Без префикса PRICESCOPE_: браузерный слой читает именно эту переменную
    camoufox_executable: str | None = Field(
        default=None, validation_alias="CAMOUFOX_EXECUTABLE_PATH"
    )

    @field_validator("db_path", "raw_dir", "photos_dir", "datasets_dir", mode="before")
    @classmethod
    def _resolve_project_paths(cls, value: Path | str) -> Path:
        """Все пути к данным привязаны к корню проекта, независимо от CWD."""
        return _resolve_path(Path(value))

    @property
    def database_url(self) -> str:
        """Получить URL БД для SQLAlchemy."""
        if self.db_url:
            return self.db_url
        # В URL использовать прямой слеш и на Windows (иначе Alembic/SQLAlchemy
        # могут трактовать backslash как escape-последовательность).
        return f"sqlite+aiosqlite:///{self.db_path.as_posix()}"

    @property
    def sync_database_url(self) -> str:
        """Синхронный URL для Alembic (миграции выполняются в sync-режиме)."""
        url = self.database_url
        if url.startswith("sqlite+aiosqlite://"):
            return url.replace("sqlite+aiosqlite://", "sqlite://", 1)
        if url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
        return url

    @property
    def is_local(self) -> bool:
        """Локальный режим (без авторизации, SQLite)."""
        return self.mode == "local"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Получить кэшированные настройки процесса."""
    return Settings()
