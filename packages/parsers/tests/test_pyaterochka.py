"""Тесты адаптера Пятёрочки на фикстурах (браузер не нужен)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from pricescope_core import CaptchaDetectedError, ParserError
from pricescope_parsers.base import ParseContext, StoreParser
from pricescope_parsers.manual.csv_parser import parse_csv_file
from pricescope_parsers.pyaterochka.browser import (
    _get_local_storage_item,
    collect_leaves,
)
from pricescope_parsers.pyaterochka.parser import (
    PyaterochkaParser,
    _first_image_url,
    _price_minor,
)

from .conftest import make_context

FIXTURES = Path(__file__).parent / "fixtures" / "pyaterochka"


def fixture(name: str) -> dict:
    """Загрузить JSON-фикстуру 5ka."""
    return json.loads((FIXTURES / name).read_bytes())


class FakeBackend:
    """Детерминированный источник снимка каталога."""

    def __init__(self, snapshot: dict) -> None:
        self.snapshot = snapshot

    async def fetch_snapshot(self, ctx: ParseContext) -> dict:
        """Сохранить raw snapshot и вернуть фикстуру."""
        ctx.last_raw_sha = await ctx.save_raw(
            "pyaterochka",
            json.dumps(self.snapshot, ensure_ascii=False).encode("utf-8"),
            "https://5ka.ru/fixture",
        )
        return self.snapshot


@pytest.fixture
def parser() -> PyaterochkaParser:
    """Адаптер с фикстуровым браузерным backend."""
    return PyaterochkaParser(FakeBackend(fixture("snapshot.json")))


async def test_parser_contract_and_fields(tmp_path, parser):
    """Снимок каталога → валидные Observation v1 с ценами в копейках."""
    assert isinstance(parser, StoreParser)
    ctx = make_context(tmp_path, None)
    items = [item async for item in parser.parse(ctx)]

    assert len(items) == 3
    assert items[0].store_code == "pyaterochka"
    assert items[0].external_id == "500001"
    assert items[0].price_minor == 19990
    assert items[0].old_price_minor == 24990
    assert items[0].category_path == "Красота"
    assert items[0].package == "100мл"
    assert items[0].image_urls == ["https://cdn.5ka.ru/500001.png"]
    assert items[0].available is True
    assert items[2].available is False
    assert items[1].price_minor == 24990  # строка "249.90" → копейки
    assert all(len(item.raw_ref) == 64 for item in items)
    assert all(len(item.content_hash) == 64 for item in items)
    assert ctx.location_info and ctx.location_info["external_id"] == "12345"
    assert list((tmp_path / "raw" / "pyaterochka").rglob("*.json"))


async def test_captcha_stops_parser(tmp_path):
    """CAPTCHA → CaptchaDetectedError, без обхода и без товаров."""
    parser = PyaterochkaParser(FakeBackend(fixture("captcha_snapshot.json")))
    ctx = make_context(tmp_path, None)
    with pytest.raises(CaptchaDetectedError) as caught:
        [item async for item in parser.parse(ctx)]
    assert caught.value.code == "CAPTCHA_DETECTED"
    assert caught.value.diagnostics["markers"]


async def test_cancellation_and_health(tmp_path, parser, monkeypatch):
    """Отмена пробрасывается; health_check не требует сети для fake backend."""
    assert await parser.health_check() is True
    ctx = make_context(tmp_path, None)
    ctx.cancellation.set()
    with pytest.raises(asyncio.CancelledError):
        [item async for item in parser.parse(ctx)]

    monkeypatch.delenv("CAMOUFOX_EXECUTABLE_PATH", raising=False)
    real_backend_parser = PyaterochkaParser()
    assert await real_backend_parser.health_check() is False
    with pytest.raises(ParserError, match="CAMOUFOX_EXECUTABLE_PATH"):
        [item async for item in real_backend_parser.parse(make_context(tmp_path, None))]


def test_price_helpers():
    """Разбор цен и URL изображений из разных форм ответа API."""
    assert _price_minor(19990) == 19990
    assert _price_minor("249.90 ₽") == 24990
    assert _price_minor("1 299,50") == 129950
    assert _price_minor(None) is None
    assert _first_image_url({"normal": "u1", "small": "u2"}) == "u1"
    assert _first_image_url(["", {"url": "u3"}]) == "u3"


def test_collect_leaves():
    """Дерево категорий 5ka обходится рекурсивно."""
    tree = [
        {
            "id": 1,
            "name": "Красота",
            "categories": [{"id": 2, "name": "Уход"}],
        }
    ]
    assert collect_leaves(tree) == [("2", "Красота/Уход")]


class _FakeStorage:
    """Имитация localStorage старого и нового API Playwright."""

    def __init__(self, value: str, *, awaitable: bool = False) -> None:
        self.value = value
        self.awaitable = awaitable

    def get_item(self, key: str):
        """Вернуть значение (иногда awaitable)."""
        async def _await() -> str:
            return self.value

        return _await() if self.awaitable else self.value


class _FakePage:
    """Страница с имитацией localStorage."""

    def __init__(self, storage: _FakeStorage) -> None:
        self.local_storage = storage


async def test_local_storage_compat():
    """Поддерживаются оба варианта API localStorage."""
    old = _FakePage(_FakeStorage("sap-1"))
    new = _FakePage(_FakeStorage("sap-2", awaitable=True))
    assert await _get_local_storage_item(old, "DeliveryPanelStore") == "sap-1"
    assert await _get_local_storage_item(new, "DeliveryPanelStore") == "sap-2"


def test_manual_csv_import():
    """Ручной импорт CSV: BOM, обязательные колонки, копейки."""
    path = FIXTURES / "products.csv"
    rows = parse_csv_file(path)
    assert len(rows) == 2
    assert rows[0].external_id == "700001"
    assert rows[0].price_minor == 12345
    assert rows[0].name == "Товар из CSV A"
    assert rows[1].category_path == "Тест/CSV"
