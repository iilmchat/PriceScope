"""Тесты адаптера Ленты на фикстурах (сеть не используется)."""

from __future__ import annotations

import asyncio

import pytest
from pricescope_core import StoreUnavailableError

from .conftest import make_context, make_http_client, make_lenta_handler


async def test_parse_all_categories_with_pagination(tmp_path, lenta_parser):
    """Две конечные категории, 2 страницы в первой: 4 товара, цены в копейках."""
    async with make_http_client(make_lenta_handler()) as http:
        ctx = make_context(tmp_path, http)
        items = [item async for item in lenta_parser.parse(ctx)]

    assert len(items) == 4
    assert items[0].external_id == "736811"
    assert items[0].price_minor == 22999
    assert items[0].old_price_minor == 28499
    assert items[0].category_path == "Красота/Дезодоранты"
    assert items[1].old_price_minor == 69900  # priceRegular, если costRegular=0
    assert items[-1].category_path == "Красота/Шампуни"
    assert all(len(item.raw_ref) == 64 for item in items)
    assert all(len(item.content_hash) == 64 for item in items)
    assert list((tmp_path / "raw" / "lenta").rglob("*.json"))


async def test_detail_fetch_adds_photo(tmp_path, lenta_parser):
    """При --details недостающее фото дозапрашивается карточкой товара."""
    async with make_http_client(make_lenta_handler()) as http:
        ctx = make_context(tmp_path, http, fetch_details=True)
        items = [item async for item in lenta_parser.parse(ctx)]

    second = next(item for item in items if item.external_id == "736812")
    assert second.image_urls and second.image_urls[0].endswith("/736812/detail.png")


async def test_category_filter_and_limit(tmp_path, lenta_parser):
    """Фильтр по пути категории и лимит товаров работают на уровне адаптера."""
    async with make_http_client(make_lenta_handler()) as http:
        ctx = make_context(tmp_path, http, categories=["Красота/Шампуни"])
        filtered = [item async for item in lenta_parser.parse(ctx)]

    assert len(filtered) == 1
    assert filtered[0].external_id == "800001"

    async with make_http_client(make_lenta_handler()) as http:
        limited = [item async for item in lenta_parser.parse(make_context(tmp_path, http, limit=2))]
    assert len(limited) == 2


async def test_empty_hub_fails_explicitly(tmp_path, lenta_parser):
    """Пустой ответ hub → StoreUnavailableError, а не тихий пустой результат."""
    async with make_http_client(make_lenta_handler(empty_hub=True)) as http:
        with pytest.raises(StoreUnavailableError):
            [item async for item in lenta_parser.parse(make_context(tmp_path, http))]


async def test_cancellation_propagates(tmp_path, lenta_parser):
    """Отмена останавливает парсер на первом же чеке."""
    async with make_http_client(make_lenta_handler()) as http:
        ctx = make_context(tmp_path, http)
        ctx.cancellation.set()
        with pytest.raises(asyncio.CancelledError):
            [item async for item in lenta_parser.parse(ctx)]


async def test_leaf_category_tree():
    """Дерево категорий строится локально, без дополнительных запросов."""
    import json

    from pricescope_parsers.lenta.parser import build_leaf_list

    from .conftest import load_fixture

    categories = json.loads(load_fixture("categories.json"))["categories"]
    assert build_leaf_list(categories) == [
        (3509, "Красота/Дезодоранты"),
        (3510, "Красота/Шампуни"),
    ]
