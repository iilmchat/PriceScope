"""Контрактные тесты REST API v1 (S04)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pricescope_api import repositories as repo
from pricescope_api.schemas import ImportRequest
from pricescope_core import ProductObservation
from pydantic import ValidationError


@pytest.fixture
async def seeded(client, tmp_path):
    """Три товара и четыре наблюдения двух магазинов."""
    import pricescope_api.db.session as session_module

    maker = session_module.get_sessionmaker()
    async with maker() as session:
        products = []
        for _index, name in enumerate(
            ("Дезодорант РЕКСОНА 100мл", "Шампунь ШАУМА 400мл", "Гель ДЮШ 250мл")
        ):
            products.append(await repo.upsert_product(session, name, brand="TEST"))
        now = datetime.now(UTC)
        for product, store, external_id, price_minor, days_ago in (
            (products[0], "lenta", "1", 22999, 0),
            (products[0], "pyaterochka", "2", 19990, 0),
            (products[1], "lenta", "3", 34990, 5),
            (products[2], "manual", "4", 12990, 10),
        ):
            observation = ProductObservation(
                store_code=store,
                external_id=external_id,
                location_id="233",
                name=product.canonical_name,
                category_path="Красота",
                price_minor=price_minor,
                package="100мл",
                net_weight_g=100,
                observed_at=now - timedelta(days=days_ago),
                raw_ref="sha-test",
                parser_version="0.1.0",
            ).with_hash()
            await repo.upsert_observation(session, observation, product_id=product.id)
        await session.commit()
        return [product.id for product in products], now


def test_import_request_forbids_extra_fields():
    """Входные DTO не принимают неизвестные поля."""
    with pytest.raises(ValidationError):
        ImportRequest(store_code="lenta", store_secret="hack")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        ImportRequest(store_code="lenta", limit=0)


async def test_error_envelope_404(client):
    """404 отдаётся в едином формате с trace_id."""
    response = await client.get("/api/v1/products/999999")
    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["trace_id"]


async def test_validation_error_envelope(client):
    """422 от FastAPI тоже в едином envelope."""
    response = await client.post("/api/v1/imports", json={"store_code": "lenta", "limit": 0})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"]["errors"]


async def test_product_pagination_and_sort(client, seeded):
    """Пагинация, фильтр, сортировка и метаданные страницы."""
    response = await client.get(
        "/api/v1/products", params={"query": "РЕКСОНА", "page": 1, "page_size": 2}
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 1
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert data["total_pages"] == 1
    assert data["has_next"] is False
    assert len(data["items"]) == 1

    response = await client.get("/api/v1/products", params={"page": 1, "page_size": 2})
    data = response.json()["data"]
    assert data["total"] == 3
    assert data["total_pages"] == 2
    assert data["has_next"] is True
    assert len(data["items"]) == 2


async def test_observation_filters(client, seeded):
    """Фильтры по магазину и дате сужают выборку."""
    response = await client.get(
        "/api/v1/observations", params={"store_code": "lenta", "page_size": 10}
    )
    data = response.json()["data"]
    assert data["total"] == 2
    assert all(item["store_code"] == "lenta" for item in data["items"])

    _, now = seeded
    response = await client.get(
        "/api/v1/observations",
        params={"date_from": (now - timedelta(days=1)).date().isoformat()},
    )
    assert response.json()["data"]["total"] == 2

    by_external = await client.get(
        "/api/v1/observations", params={"external_id": "1"}
    )
    assert by_external.json()["data"]["total"] == 1


async def test_compare_contract(client, seeded):
    """Сравнение: дешёвый вариант помечен, цена за литр и экономия рассчитаны."""
    product_id = seeded[0][0]
    response = await client.get(
        "/api/v1/compare", params={"product_id": product_id, "lat": 55.3925, "lon": 36.7323}
    )
    assert response.status_code == 200
    rows = response.json()["data"]
    assert len(rows) == 2
    assert rows[0]["store_code"] == "pyaterochka"  # 19990 < 22999
    assert rows[0]["is_cheapest"] is True
    assert rows[1]["savings_pct"] > 0
    assert rows[0]["price_per_l_minor"] == 19990 * 10  # 100мл → литр
    assert rows[0]["distance_m"] is None  # StoreLocation не засеян в этом тесте
    assert "observed_at" in rows[0]


async def test_compare_requires_target(client):
    """Без product_id/query — явная ошибка, а не пустой результат."""
    response = await client.get("/api/v1/compare")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_QUERY"


async def test_openapi_lists_new_routes(client):
    """Новые маршруты присутствуют в OpenAPI."""
    spec = (await client.get("/openapi.json")).json()
    paths = spec["paths"]
    assert "/api/v1/imports" in paths
    assert "/api/v1/observations" in paths
    assert "/api/v1/compare" in paths
