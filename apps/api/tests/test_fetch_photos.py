"""Тесты дозагрузки фото по URL (PL-016)."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pricescope_api.db.session as session_module
from pricescope_api import repositories as repo
from pricescope_api.config import Settings
from pricescope_api.services import fetch_photos
from pricescope_core import ProductObservation
from sqlalchemy import select

PNG = b"\x89PNG\r\n\x1a\n" + b"fake-image-bytes"


def handler(request: httpx.Request) -> httpx.Response:
    """Фейковый CDN с картинкой."""
    if request.url.path.endswith(".png"):
        return httpx.Response(200, content=PNG, headers={"content-type": "image/png"})
    return httpx.Response(200, content=b"html", headers={"content-type": "text/html"})


async def test_fetch_photos_saves_file_without_touching_hash(client, tmp_path):
    """Фото скачивается, путь пишется отдельно, ценовой hash не меняется."""
    maker = session_module.get_sessionmaker()
    settings = Settings(mode="local", photos_dir=tmp_path / "photos", auto_migrate=False)
    async with maker() as session:
        original = ProductObservation(
            store_code="lenta",
            external_id="42",
            name="Товар 42",
            price_minor=12345,
            image_urls=["https://cdn.test/42.png"],
            observed_at=datetime.now(UTC),
            raw_ref="sha-test",
            parser_version="0.1.0",
        ).with_hash()
        await repo.upsert_observation(session, original)
        await session.commit()
        old_hash = original.content_hash

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http:
            result = await fetch_photos(session, settings, http_client=http)

    assert result["downloaded"] == 1
    assert result["failed"] == 0
    files = list((tmp_path / "photos" / "lenta" / "42").glob("*"))
    assert len(files) == 1
    assert files[0].read_bytes() == PNG

    async with maker() as session:
        row = (await session.execute(select(repo.Observation))).scalar_one()
        assert row.photo_path and row.photo_path.startswith("/photos/lenta/42/")
        assert row.content_hash == old_hash  # обогащение не меняет ценовой факт


async def test_fetch_photos_skips_legacy_local_photo(client, tmp_path):
    """У legacy-фото CDN-ссылка игнорируется — скачивание не нужно."""
    maker = session_module.get_sessionmaker()
    settings = Settings(mode="local", photos_dir=tmp_path / "photos", auto_migrate=False)
    async with maker() as session:
        observation = ProductObservation(
            store_code="lenta",
            external_id="44",
            name="Legacy товар",
            price_minor=500,
            image_urls=["/legacy-photos/44.png", "https://cdn.test/44.png"],
            observed_at=datetime.now(UTC),
            raw_ref="sha-test",
            parser_version="0.1.0",
        ).with_hash()
        await repo.upsert_observation(session, observation)
        await session.commit()

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            result = await fetch_photos(session, settings, http_client=http)

    assert result["already_local"] == 1
    assert result["downloaded"] == 0
    async with maker() as session:
        row = (await session.execute(select(repo.Observation))).scalar_one()
        assert row.photo_path == "/legacy-photos/44.png"


async def test_fetch_photos_skips_rows_without_url(client, tmp_path):
    """Observation без URL отсекается запросом и не ломает загрузку."""
    maker = session_module.get_sessionmaker()
    settings = Settings(mode="local", photos_dir=tmp_path / "photos", auto_migrate=False)
    async with maker() as session:
        observation = ProductObservation(
            store_code="lenta",
            external_id="43",
            name="Товар без фото",
            price_minor=999,
            image_urls=[],
            observed_at=datetime.now(UTC),
            raw_ref="sha-test",
            parser_version="0.1.0",
        ).with_hash()
        await repo.upsert_observation(session, observation)
        await session.commit()

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            result = await fetch_photos(session, settings, http_client=http)

    assert result["no_source"] == 0
    assert result["downloaded"] == 0
    async with maker() as session:
        row = (await session.execute(select(repo.Observation))).scalar_one()
        assert row.photo_path is None
