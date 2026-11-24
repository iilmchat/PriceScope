"""Реестр адаптеров и хранилище raw snapshots."""

from __future__ import annotations

import asyncio

import pytest
from pricescope_core import UnknownStoreError
from pricescope_parsers.base import StoreParser
from pricescope_parsers.registry import get_parser, list_parsers
from pricescope_parsers.snapshots import RawSnapshotStore


def test_registry_returns_builtin_parsers():
    """Известные адаптеры доступны через реестр и удовлетворяют порту."""
    for name in ("lenta", "pyaterochka", "manual"):
        parser = get_parser(name)
        assert parser.name == name
        assert isinstance(parser, StoreParser)
        assert parser.version
    assert set(list_parsers()) >= {"lenta", "pyaterochka", "manual"}


def test_registry_unknown_store():
    """Неизвестный магазин — явная доменная ошибка."""
    with pytest.raises(UnknownStoreError):
        get_parser("unknown-store")


async def test_snapshot_saved_once(tmp_path):
    """Одинаковые байты → один файл и один sha256."""
    store = RawSnapshotStore(tmp_path / "raw")
    payload = b'{"items": []}'
    first = await store.save_async("lenta", payload, "https://example.test/items")
    second = await store.save_async("lenta", payload, "https://example.test/items")

    assert first == second
    assert len(first) == 64
    files = [path for path in (tmp_path / "raw" / "lenta").rglob("*") if path.is_file()]
    assert len(files) == 2  # сам JSON + .uri.txt (в подпапке даты)
    assert any(file.suffix == ".json" for file in files)


def test_snapshot_store_sync_api(tmp_path):
    """Синхронный API нужен CLI/тестам и даёт тот же хэш."""
    store = RawSnapshotStore(tmp_path / "raw")
    sha = store.save("manual", b"abc", "manual:test.csv", "text/csv")
    assert len(sha) == 64
    assert asyncio.run(store.save_async("manual", b"abc", "manual:test.csv")) == sha
