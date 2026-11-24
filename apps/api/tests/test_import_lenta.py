"""Интеграционный тест S03: импорт Ленты в SQLite через полный конвейер."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from pathlib import Path

import httpx
import pytest
from pricescope_api.config import Settings
from pricescope_api.db import models  # noqa: F401
from pricescope_api.db.base import Base
from pricescope_api.db.models import Observation, ParseRun
from pricescope_api.services import run_import
from pricescope_core import CaptchaDetectedError
from pricescope_parsers.base import ParseContext, ParserCapabilities
from pricescope_parsers.lenta.client import LentaConfig
from pricescope_parsers.lenta.parser import LentaParser
from pricescope_parsers.registry import _REGISTRY
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

FIXTURES = Path(__file__).parents[3] / "packages" / "parsers" / "tests" / "fixtures" / "lenta"


def fixture(name: str) -> bytes:
    """Загрузить фикстуру из единого источника."""
    return (FIXTURES / name).read_bytes()


def response(request: httpx.Request, payload: bytes, status: int = 200) -> httpx.Response:
    """JSON-ответ MockTransport."""
    return httpx.Response(
        status,
        content=payload,
        request=request,
        headers={"content-type": "application/json"},
    )


def lenta_handler(*, updated: bool = False) -> Callable[[httpx.Request], httpx.Response]:
    """Обработчик Ленты для интеграционного теста."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        params = request.url.params
        if path.endswith("/nearest/hub"):
            return response(request, fixture("hub.json"))
        if path.endswith("/categories"):
            return response(request, fixture("categories.json"))
        if path.endswith("/items"):
            category, offset = params.get("categoryId"), params.get("offset", "0")
            if category == "3509" and offset == "0":
                name = "items_3509_0_updated.json" if updated else "items_3509_0.json"
                return response(request, fixture(name))
            if category == "3509" and offset == "2":
                return response(request, fixture("items_3509_2.json"))
            if category == "3510" and offset == "0":
                return response(request, fixture("items_3510_0.json"))
            return response(request, b'{"items": []}')
        return response(request, b'{"images": []}')

    return handler


@pytest.fixture
async def db(tmp_path):
    """Изолированная SQLite БД и настройки с временными каталогами."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings(
        mode="local",
        db_url="sqlite+aiosqlite:///:memory:",
        raw_dir=tmp_path / "raw",
        photos_dir=tmp_path / "photos",
        datasets_dir=tmp_path / "datasets",
    )
    yield maker, settings, tmp_path
    await engine.dispose()


async def import_once(maker, settings, *, key: str, updated: bool = False) -> dict:
    """Один прогон импорта с фикстуровым HTTP-клиентом."""
    async with maker() as session:
        transport = httpx.MockTransport(lenta_handler(updated=updated))
        async with httpx.AsyncClient(transport=transport) as http:
            return await run_import(
                session,
                settings,
                "lenta",
                idempotency_key=key,
                http_client=http,
            )


async def test_import_lenta_is_idempotent_and_updates_prices(db, monkeypatch):
    """Полный цикл: импорт → повтор без дублей → изменение цены → обновление."""
    maker, settings, tmp_path = db
    monkeypatch.setitem(
        _REGISTRY,
        "lenta",
        LentaParser(LentaConfig(page_limit=2, page_delay=0.0)),
    )

    first = await import_once(maker, settings, key="run-1")
    assert first["status"] == "success"
    assert first["new"] == 4
    assert first["updated"] == 0

    async with maker() as session:
        count = await session.scalar(select(func.count()).select_from(Observation))
        assert count == 4
        raw_files = list((tmp_path / "raw" / "lenta").rglob("*.json"))
        assert raw_files  # lineage сохранён

    second = await import_once(maker, settings, key="run-2")
    assert second["new"] == 0
    assert second["status"] == "success"

    repeated = await import_once(maker, settings, key="run-1")
    assert repeated["idempotent"] is True  # один idempotency key → один ParseRun

    third = await import_once(maker, settings, key="run-3", updated=True)
    assert third["new"] == 0
    assert third["updated"] == 2  # изменились две цены на первой странице

    async with maker() as session:
        count = await session.scalar(select(func.count()).select_from(Observation))
        assert count == 4  # история не дублируется
        row = await session.scalar(
            select(Observation).where(Observation.external_id == "736811")
        )
        assert row is not None and row.price_minor == 19999

        runs = (await session.execute(select(ParseRun))).scalars().all()
        assert len(runs) == 3
        assert {run.status for run in runs} == {"success"}


class FailingCaptchaParser:
    """Парсер, имитирующий обнаружение CAPTCHA (ADR-006)."""

    name = "lenta"
    version = "test"

    def capabilities(self) -> ParserCapabilities:
        """Пустые capability."""
        return ParserCapabilities()

    async def health_check(self) -> bool:
        """Не используется."""
        return True

    async def parse(self, ctx: ParseContext) -> AsyncIterator[object]:
        """Сразу бросает CaptchaDetectedError."""
        raise CaptchaDetectedError("CAPTCHA", {"marker": "капча"})
        yield  # pragma: no cover — сделать async-генератор


async def test_captcha_failure_is_recorded_in_parse_run(db, monkeypatch):
    """CAPTCHA → ParseRun.failed с кодом, без попыток обхода."""
    maker, settings, _ = db
    monkeypatch.setitem(_REGISTRY, "lenta", FailingCaptchaParser())

    result = await import_once(maker, settings, key="captcha-run")

    assert result["status"] == "failed"
    assert result["error_code"] == "CAPTCHA_DETECTED"
    async with maker() as session:
        run = await session.scalar(select(ParseRun))
        assert run is not None and run.error_code == "CAPTCHA_DETECTED"
