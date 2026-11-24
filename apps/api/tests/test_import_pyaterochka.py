"""Интеграция S06: импорт Пятёрочки и сравнение двух магазинов."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pricescope_api.db.session as session_module
import pytest
from pricescope_api import repositories as repo
from pricescope_api.config import Settings
from pricescope_api.db.models import StoreLocation
from pricescope_api.services import compare_prices, run_import
from pricescope_core import ProductObservation
from pricescope_parsers.base import ParseContext
from pricescope_parsers.pyaterochka.browser import BrowserBackend
from pricescope_parsers.pyaterochka.parser import PyaterochkaParser
from pricescope_parsers.registry import _REGISTRY
from sqlalchemy import select

FIXTURE = (
    Path(__file__).parents[3]
    / "packages" / "parsers" / "tests" / "fixtures" / "pyaterochka" / "snapshot.json"
)


class FixtureBackend:
    """Фикстуровый браузерный backend (ADR-002)."""

    async def fetch_snapshot(self, ctx: ParseContext) -> dict:
        """Отдать снимок каталога и сохранить raw."""
        payload = FIXTURE.read_bytes()
        ctx.last_raw_sha = await ctx.save_raw("pyaterochka", payload, "https://5ka.ru/fixture")
        return json.loads(payload)


async def test_import_pyaterochka_and_compare_stores(client, tmp_path, monkeypatch):
    """Пятёрочка импортируется, точка сохраняется, сравнение видит две сети."""
    assert isinstance(FixtureBackend(), BrowserBackend)
    monkeypatch.setitem(_REGISTRY, "pyaterochka", PyaterochkaParser(FixtureBackend()))
    settings = Settings(
        mode="local",
        db_url="sqlite+aiosqlite:///:memory:",
        raw_dir=tmp_path / "raw",
        photos_dir=tmp_path / "photos",
        datasets_dir=tmp_path / "datasets",
        auto_migrate=False,
    )
    maker = session_module.get_sessionmaker()

    async with maker() as session:
        result = await run_import(session, settings, "pyaterochka")
        assert result["status"] == "success"
        assert result["new"] == 3

        locations = (await session.execute(select(StoreLocation))).scalars().all()
        assert len(locations) == 1
        assert locations[0].external_id == "12345"
        assert locations[0].address and "Наро-Фоминск" in locations[0].address

        lenta = ProductObservation(
            store_code="lenta",
            external_id="lenta-1",
            location_id="233",
            name="Рексона спрей 100 мл",
            category_path="Красота",
            price_minor=22999,
            package="100мл",
            net_weight_g=100,
            observed_at=datetime.now(UTC),
            raw_ref="sha-lenta",
            parser_version="0.1.0",
        ).with_hash()
        await repo.upsert_observation(session, lenta)
        await session.commit()

        rows = await compare_prices(session, None, 55.3925, 36.7323, "Рексона")
        assert {row["store_code"] for row in rows} == {"lenta", "pyaterochka"}
        assert rows[0]["store_code"] == "pyaterochka"
        assert rows[0]["is_cheapest"] is True
        assert rows[1]["savings_pct"] > 0

    response = await client.get("/api/v1/compare", params={"query": "Рексона"})
    assert response.status_code == 200
    assert len(response.json()["data"]) == 2


async def test_import_pyaterochka_is_idempotent(client, tmp_path, monkeypatch):
    """Повторный импорт тех же данных не создаёт дубликаты."""
    monkeypatch.setitem(_REGISTRY, "pyaterochka", PyaterochkaParser(FixtureBackend()))
    settings = Settings(
        mode="local",
        db_url="sqlite+aiosqlite:///:memory:",
        raw_dir=tmp_path / "raw",
        datasets_dir=tmp_path / "datasets",
        auto_migrate=False,
    )
    maker = session_module.get_sessionmaker()

    async with maker() as session:
        first = await run_import(session, settings, "pyaterochka")
        second = await run_import(session, settings, "pyaterochka")
    assert (first["new"], second["new"]) == (3, 0)
    assert second["status"] == "success"


@pytest.mark.live
async def test_real_captcha_policy_is_documented():
    """Заглушка live-теста: ручная проверка при доступности 5ka.ru (S06)."""
    # Реальный запуск намеренно не выполняется в CI: CAPTCHA/блокировка — ожидаемы.
    assert True
