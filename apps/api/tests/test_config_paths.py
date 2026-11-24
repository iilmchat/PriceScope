"""Регрессионные тесты путей данных (PL-013).

Баг: `pricescope init-db` из корня и `pricescope parse` из apps/api работали
с разными SQLite-файлами, потому что пути резолвились относительно CWD.
"""

from __future__ import annotations

from pricescope_api.config import PROJECT_ROOT, Settings


def test_default_paths_are_root_anchored():
    """Относительные пути по умолчанию привязаны к корню репозитория."""
    settings = Settings()
    assert settings.db_path == PROJECT_ROOT / "data" / "pricescope.db"
    assert settings.raw_dir == PROJECT_ROOT / "data" / "raw"
    assert settings.photos_dir == PROJECT_ROOT / "data" / "photos"
    assert settings.datasets_dir == PROJECT_ROOT / "datasets"
    assert settings.db_path.is_absolute()


def test_same_db_path_from_different_cwd(monkeypatch, tmp_path):
    """Смена CWD не меняет путь БД."""
    monkeypatch.chdir(tmp_path)
    from_root_cwd = Settings().db_path

    monkeypatch.chdir(tmp_path.parent)
    from_other_cwd = Settings().db_path

    assert from_root_cwd == from_other_cwd == PROJECT_ROOT / "data" / "pricescope.db"


def test_absolute_path_is_not_changed(tmp_path):
    """Явно заданный абсолютный путь остаётся как есть."""
    settings = Settings(db_path=tmp_path / "custom.db")
    assert settings.db_path == tmp_path / "custom.db"


def test_default_port_is_8775_and_env_can_override(monkeypatch, tmp_path):
    """Порт по умолчанию 8775; PRICESCOPE_PORT имеет приоритет."""
    monkeypatch.chdir(tmp_path)  # чтобы не подхватить корневой .env
    monkeypatch.delenv("PRICESCOPE_PORT", raising=False)
    assert Settings().port == 8775

    monkeypatch.setenv("PRICESCOPE_PORT", "9999")
    assert Settings().port == 9999


def test_sync_url_contains_resolved_path():
    """Alembic получает абсолютный путь к той же БД."""
    settings = Settings()
    assert settings.sync_database_url == f"sqlite:///{settings.db_path.as_posix()}"
