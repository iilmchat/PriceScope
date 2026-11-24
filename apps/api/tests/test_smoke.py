"""Smoke-тесты API и домена."""

from __future__ import annotations

from datetime import UTC, datetime

from pricescope_core import (
    CaptchaDetectedError,
    ProductObservation,
    format_rub,
    normalize_name,
    to_minor,
)
from pricescope_core.hashing import canonical_hash
from pricescope_parsers.pyaterochka.captcha_policy import detect_captcha, ensure_no_captcha


def test_money_minor_units():
    """Деньги хранятся в копейках без float-ошибок."""
    assert to_minor(229.99) == 22999
    assert format_rub(22999) == "229,99 ₽"


def test_content_hash_is_stable():
    """Хэш наблюдения детерминирован и не зависит от времени внутри дня."""
    base = ProductObservation(
        store_code="lenta",
        external_id="736811",
        name="Дезодорант РЕКСОНА",
        price_minor=22999,
        observed_at=datetime(2026, 11, 24, 10, 0, tzinfo=UTC),
        raw_ref="sha",
        parser_version="0.1.0",
    )
    other = base.model_copy(
        update={"observed_at": datetime(2026, 11, 24, 18, 30, tzinfo=UTC)}
    )
    assert base.with_hash().content_hash == other.with_hash().content_hash
    assert canonical_hash({"b": 2, "a": 1}) == canonical_hash({"a": 1, "b": 2})


def test_normalize():
    """Нормализация названия убирает пунктуацию и регистр."""
    assert normalize_name("Дезодорант-спрей РЕКСОНА, 100мл!") == "дезодорант спрей рексона 100мл"


def test_captcha_policy():
    """CAPTCHA детектится и приводит к явной ошибке (без обхода)."""
    diagnostics = detect_captcha("Подтвердите, что вы не робот", "https://5ka.ru", "")
    assert diagnostics is not None
    try:
        ensure_no_captcha("Captcha", "", "")
    except CaptchaDetectedError as exc:
        assert exc.code == "CAPTCHA_DETECTED"
    else:
        raise AssertionError("Ожидалась CaptchaDetectedError")


async def test_health(client):
    """GET /health возвращает версию и режим."""
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["mode"] == "local"


async def test_stores_empty(client):
    """Список магазинов доступен без данных."""
    response = await client.get("/api/v1/stores")
    assert response.status_code == 200
    assert response.json()["success"] is True
