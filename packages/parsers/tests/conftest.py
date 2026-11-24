"""Фикстуры тестов парсеров: только локальные JSON, без сети."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
from pricescope_parsers.base import ParseContext
from pricescope_parsers.snapshots import RawSnapshotStore

FIXTURES = Path(__file__).parent / "fixtures" / "lenta"


def load_fixture(name: str) -> bytes:
    """Прочитать JSON-фикстуру как байты (важно для sha raw snapshot)."""
    return (FIXTURES / name).read_bytes()


def json_response(request: httpx.Request, payload: bytes, status: int = 200) -> httpx.Response:
    """Собрать httpx-ответ с JSON-телом."""
    return httpx.Response(
        status,
        content=payload,
        headers={"content-type": "application/json"},
        request=request,
    )


def make_lenta_handler(
    *, updated_prices: bool = False, empty_hub: bool = False
) -> Callable[[httpx.Request], httpx.Response]:
    """Обработчик MockTransport для каталога Ленты."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        params = request.url.params
        if path.endswith("/nearest/hub"):
            if empty_hub:
                return json_response(request, b'{"hubs": []}')
            return json_response(request, load_fixture("hub.json"))
        if path.endswith("/categories"):
            return json_response(request, load_fixture("categories.json"))
        if path.endswith("/items"):
            category = params.get("categoryId")
            offset = params.get("offset", "0")
            if category == "3509" and offset == "0":
                name = (
                    "items_3509_0_updated.json" if updated_prices else "items_3509_0.json"
                )
                return json_response(request, load_fixture(name))
            if category == "3509" and offset == "2":
                return json_response(request, load_fixture("items_3509_2.json"))
            if category == "3510" and offset == "0":
                return json_response(request, load_fixture("items_3510_0.json"))
            return json_response(request, b'{"items": []}')
        if path.startswith("/catalog/v1/items/"):
            if path.endswith("/736812"):
                return json_response(request, load_fixture("item_detail_736812.json"))
            return json_response(request, b'{"images": []}')
        return json_response(request, b'{"error": "not found"}', status=404)

    return handler


def make_http_client(
    handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.AsyncClient:
    """HTTP-клиент с MockTransport вместо реальной сети."""
    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://integration.api.lenta.com",
    )


def make_context(tmp_path: Path, http: httpx.AsyncClient, **overrides: object) -> ParseContext:
    """ParseContext с временным хранилищем raw snapshots."""
    values: dict[str, object] = {
        "lat": 55.3925,
        "lon": 36.7323,
        "http": http,
        "raw_store": RawSnapshotStore(tmp_path / "raw"),
        "trace_id": "test-trace",
        "parser_version": "0.1.0",
    }
    values.update(overrides)
    return ParseContext(**values)  # type: ignore[arg-type]


@pytest.fixture
def lenta_parser():
    """Адаптер Ленты с page_limit=2 (проверка пагинации) и без задержек."""
    from pricescope_parsers.lenta.client import LentaConfig
    from pricescope_parsers.lenta.parser import LentaParser

    return LentaParser(LentaConfig(page_limit=2, page_delay=0.0))
