"""Тесты локального просмотровщика (S05)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pricescope_api.db.session as session_module
import pytest
from pricescope_api import repositories as repo
from pricescope_api.db import models  # noqa: F401
from pricescope_api.db.models import ProductMatch
from pricescope_core import ProductObservation


@pytest.fixture
async def viewer_data(client):
    """Два наблюдения одного товара и спорное совпадение."""
    maker = session_module.get_sessionmaker()
    async with maker() as session:
        product = await repo.upsert_product(session, "Дезодорант РЕКСОНА 100мл", brand="TEST")
        now = datetime.now(UTC)
        for store, external_id, price_minor, days_ago in (
            ("lenta", "736811", 22999, 3),
            ("lenta", "736811", 19999, 0),
            ("pyaterochka", "9001", 18990, 0),
        ):
            observation = ProductObservation(
                store_code=store,
                external_id=external_id,
                location_id="233",
                name=product.canonical_name,
                category_path="Красота/Дезодоранты",
                price_minor=price_minor,
                package="100мл",
                net_weight_g=100,
                observed_at=now - timedelta(days=days_ago),
                raw_ref="sha-viewer-test",
                parser_version="0.1.0",
            ).with_hash()
            await repo.upsert_observation(session, observation, product_id=product.id)
        match = ProductMatch(
            observation_id=1,
            product_id=product.id,
            method="lexical",
            score=0.82,
            model_version="builtin-v1",
            status="review",
        )
        session.add(match)
        await session.commit()
        return product.id, match.id


async def test_index_page(client, viewer_data):
    """Главная открывается и показывает счётчики."""
    response = await client.get("/")
    assert response.status_code == 200
    assert "Наблюдений цен" in response.text
    assert "Импортов" in response.text


async def test_products_page_and_fragment(client, viewer_data):
    """Каталог и HTMX-фрагмент фильтруют по названию."""
    catalog = await client.get("/products")
    assert catalog.status_code == 200
    assert "Все категории" in catalog.text  # выпадающий список категорий

    response = await client.get("/viewer/fragments/products", params={"query": "РЕКСОНА"})
    assert response.status_code == 200
    assert "Дезодорант РЕКСОНА" in response.text
    assert "Всего: 3" in response.text

    # кириллица, смешанный регистр, подстрока
    mixed = await client.get("/viewer/fragments/products", params={"query": "рЕкСоН"})
    assert "Всего: 3" in mixed.text

    empty = await client.get("/viewer/fragments/products", params={"store_code": "unknown"})
    assert "Нет данных" in empty.text


async def test_product_card_with_history_and_chart(client, viewer_data):
    """Карточка показывает историю цен и SVG-график."""
    response = await client.get(
        "/product", params={"external_id": "736811", "store_code": "lenta"}
    )
    assert response.status_code == 200
    assert "История цен" in response.text
    assert "price-chart" in response.text
    assert "199,99" in response.text

    missing = await client.get("/product", params={"external_id": "no-such-id"})
    assert missing.status_code == 404


async def test_compare_page(client, viewer_data):
    """Сравнение рендерит строки и помечает самое дешёвое предложение."""
    response = await client.get("/compare", params={"query": "РЕКСОНА"})
    assert response.status_code == 200
    assert "Сравнение цен" in response.text
    assert "дешевле" in response.text
    assert "Пятёрочка" in response.text


async def test_imports_settings_pages(client, viewer_data):
    """Журнал импортов и настройки доступны."""
    assert (await client.get("/imports")).status_code == 200
    assert "Политика парсинга" in (await client.get("/settings")).text


async def test_bulk_apply_fragment(client, viewer_data):
    """Массовая обработка через viewer возвращает обновлённый список."""
    response = await client.post(
        "/viewer/matches/apply",
        params={"min_score": 0.0, "max_score": 1.0, "confirm": "true", "limit": 10},
    )
    assert response.status_code == 200
    assert "Обработано" in response.text
    assert "Очередь пуста" in response.text


async def test_match_decision_flow(client, viewer_data):
    """Решение по совпадению обновляет строку через HTMX-фрагмент."""
    _, match_id = viewer_data
    page = await client.get("/matches")
    assert page.status_code == 200
    assert "Один товар" in page.text

    response = await client.post(
        f"/viewer/matches/{match_id}/decide", params={"confirm": "true"}
    )
    assert response.status_code == 200
    assert "confirmed" in response.text

    async with session_module.get_sessionmaker()() as session:
        match = await session.get(ProductMatch, match_id)
        assert match is not None and match.status == "confirmed"
        assert match.decided_by == "viewer"
