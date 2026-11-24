"""Интеграция S07: matching → review → экспорт датасета."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pricescope_api.db.session as session_module
import pytest
from pricescope_api import repositories as repo
from pricescope_api.config import get_settings
from pricescope_api.db.models import Observation, Product, ProductMatch
from pricescope_api.services import run_matching
from pricescope_core import ProductObservation
from sqlalchemy import select

NAME_A = "Дезодорант Рексона 100мл спрей женский"
NAME_B = "Дезодорант Рексона 100мл мужской"


def observation(store: str, external_id: str, name: str, price: int, days_ago: int):
    """Создать observation без канонического товара."""
    return ProductObservation(
        store_code=store,
        external_id=external_id,
        name=name,
        category_path="Красота",
        price_minor=price,
        package="100мл",
        net_weight_g=100,
        observed_at=datetime.now(UTC) - timedelta(days=days_ago),
        raw_ref="sha-matching",
        parser_version="0.1.0",
    ).with_hash()


@pytest.fixture
async def matched(client, tmp_path, monkeypatch):
    """Три наблюдения, затем запуск matching."""

    monkeypatch.setattr(
        get_settings(), "datasets_dir", tmp_path / "datasets", raising=False
    )
    maker = session_module.get_sessionmaker()
    async with maker() as session:
        for obs in (
            observation("lenta", "a1", NAME_A, 22999, 0),
            observation("pyaterochka", "b1", NAME_B, 19990, 1),
            observation("pyaterochka", "c1", NAME_A, 18990, 2),
        ):
            await repo.upsert_observation(session, obs)
        await session.commit()
        result = await run_matching(session)
    return result


async def test_matching_creates_auto_review_and_new(client, matched):
    """Первое название → новый товар, похожее → review, точное → auto."""
    counts = matched["counts"]
    assert counts["new"] == 1
    assert counts["review"] == 1
    assert counts["auto"] == 1
    assert matched["model_version"] == "lexical-v1"

    async with session_module.get_sessionmaker()() as session:
        products = (await session.execute(select(Product))).scalars().all()
        assert len(products) == 1
        linked = (
            await session.execute(
                select(Observation).where(Observation.product_id.is_not(None))
            )
        ).scalars().all()
        assert len(linked) == 2


async def test_review_queue_and_decision(client, matched):
    """Очередь содержит названия и цены; подтверждение связывает observation."""
    response = await client.get("/api/v1/matches/review")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 1
    row = data["items"][0]
    assert row["left_name"] in (NAME_A, NAME_B)
    assert row["right_name"]
    assert row["left_price_minor"] > 0

    response = await client.post(
        f"/api/v1/matches/{row['id']}/decide",
        json={"confirm": True, "actor": "tester"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "confirmed"

    async with session_module.get_sessionmaker()() as session:
        match = await session.get(ProductMatch, row["id"])
        assert match is not None
        observation = await session.get(Observation, match.observation_id)
        assert observation is not None and observation.product_id == match.product_id


async def test_metrics(client, matched):
    """Метрики отражают покрытие и долю auto-решений."""
    response = await client.get("/api/v1/metrics")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["observations"] == 3
    assert data["linked_observations"] == 2
    assert data["coverage"] == round(2 / 3, 3)
    assert data["matches_by_status"]["review"] == 1


async def test_export_and_download(client, matched, tmp_path):
    """Экспорт создаёт JSONL + manifest; скачивание доступно только для его файлов."""
    response = await client.post(
        "/api/v1/exports",
        json={"name": "product-matching", "version": "1"},
    )
    assert response.status_code == 200
    body = response.json()["data"]
    manifest = body["manifest"]
    assert manifest["split_policy"] == "time-based"
    assert manifest["pair_count"] >= 1
    assert sum(manifest["rows"].values()) == manifest["pair_count"]
    assert len(manifest["sha256"]) == 3
    dataset_dir = tmp_path / "datasets" / "product-matching-v1"
    assert (dataset_dir / "train.jsonl").exists()
    on_disk = json.loads((dataset_dir / "manifest.json").read_text())
    assert on_disk["pair_count"] == manifest["pair_count"]

    file_response = await client.get(
        f"/api/v1/exports/{body['id']}/download", params={"file": "train.jsonl"}
    )
    assert file_response.status_code == 200
    first_line = json.loads(file_response.text.splitlines()[0])
    assert first_line["label"] == "match"
    assert first_line["left"]["store"] != first_line["right"]["store"]

    invalid = await client.get(
        f"/api/v1/exports/{body['id']}/download", params={"file": "../secret.txt"}
    )
    assert invalid.status_code == 404
