"""Адаптер Пятёрочки: снимок каталога → нормализованные observation.

Браузерный доступ спроектирован за портом `BrowserBackend`: тесты подставляют
фикстуровый backend, а CAPTCHA всегда приводит к остановке (ADR-006).
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from pricescope_core import ProductObservation, extract_measure

from pricescope_parsers.base import ParseContext, ParserCapabilities
from pricescope_parsers.pyaterochka.browser import BrowserBackend, CamoufoxBackend
from pricescope_parsers.pyaterochka.captcha_policy import ensure_no_captcha


class PyaterochkaParser:
    """Адаптер 5ka.ru. CAPTCHA → останов без попыток обхода."""

    name = "pyaterochka"
    version = "0.1.0"

    def __init__(self, backend: BrowserBackend | None = None) -> None:
        self._backend = backend or CamoufoxBackend()

    def capabilities(self) -> ParserCapabilities:
        """Нужен браузер и выбранная точка доставки."""
        return ParserCapabilities(
            requires_browser=True,
            requires_location=True,
            supports_images=True,
            max_requests_per_minute=30,
        )

    async def health_check(self) -> bool:
        """Проверка конфигурации (без сети): задан ли путь к Camoufox."""
        if isinstance(self._backend, CamoufoxBackend):
            return bool(os.getenv("CAMOUFOX_EXECUTABLE_PATH"))
        return True

    def parse(self, ctx: ParseContext) -> AsyncIterator[ProductObservation]:
        """Сбор товаров каталога 5ka.ru."""
        return self._parse_impl(ctx)

    async def _parse_impl(self, ctx: ParseContext) -> AsyncIterator[ProductObservation]:
        snapshot = await self._backend.fetch_snapshot(ctx)
        ensure_no_captcha(
            snapshot.get("title", ""),
            snapshot.get("url", ""),
            snapshot.get("body_text", ""),
        )
        location = snapshot.get("location") or {}
        location_id = str(location.get("external_id") or "")
        if not location_id:
            location_id = "unknown"
        ctx.location_info = {
            "external_id": location_id,
            "name": location.get("name"),
            "address": location.get("address"),
        }
        now = datetime.now(UTC)
        products_by_category = snapshot.get("products") or {}

        for category_id, path in snapshot.get("categories") or []:
            for product in products_by_category.get(str(category_id), []):
                ctx.check_cancelled()
                observation = self._to_observation(product, path, location_id, ctx, now)
                if observation is not None:
                    yield observation.with_hash()

    @staticmethod
    def _to_observation(
        product: dict,
        category_path: str,
        location_id: str,
        ctx: ParseContext,
        now: datetime,
    ) -> ProductObservation | None:
        """Маппинг JSON 5ka в контракт v1 (копейки, UTC, lineage)."""
        prices = product.get("prices") or {}
        external_id = _first_present(product.get("plu"), product.get("id"))
        name = _first_present(product.get("name"), product.get("title"))
        if external_id is None or name is None:
            return None
        price = _price_minor(
            _first_present(
                prices.get("current"),
                prices.get("price"),
                prices.get("discount"),
                prices.get("salePrice"),
                product.get("price"),
                prices.get("regular"),
            )
        )
        if price is None:
            return None
        image = _first_image_url(
            _first_present(
                product.get("image_links"),
                product.get("image"),
                product.get("image_link"),
                (product.get("media") or {}).get("image_links"),
            )
        )
        package = _first_present(
            product.get("package"), product.get("measure"), product.get("weight")
        )
        value, unit = extract_measure(f"{name} {package or ''}")
        return ProductObservation(
            store_code="pyaterochka",
            external_id=str(external_id),
            location_id=location_id,
            name=str(name),
            category_path=category_path,
            price_minor=price,
            old_price_minor=_price_minor(
                _first_present(
                    prices.get("regular"), prices.get("priceRegular"), product.get("oldPrice")
                )
            ),
            package=str(package) if package else None,
            net_weight_g=(
                value
                if value is not None and unit == "г"
                else (value * 1000 if value is not None and unit == "кг" else None)
            ),
            image_urls=[image] if image else [],
            available=bool(product.get("is_available", True)),
            observed_at=now,
            raw_ref=ctx.last_raw_sha or "pyaterochka:snapshot",
            parser_version=ctx.parser_version,
        )


def _first_present(*values: Any) -> Any:
    """Первое значение, не равное None или пустой строке."""
    for value in values:
        if value is not None and value != "":
            return value
    return None


def _price_minor(value: Any) -> int | None:
    """Цена 5ka → копейки. Числа — копейки, строки — рубли."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(round(value))
    if isinstance(value, str):
        cleaned = (
            value.replace("\u00a0", "")
            .replace(" ", "")
            .replace(",", ".")
            .replace("₽", "")
            .strip()
        )
        if not cleaned:
            return None
        try:
            return int((Decimal(cleaned) * 100).to_integral_value())
        except InvalidOperation:
            return None
    return None


def _first_image_url(value: Any) -> str | None:
    """Рекурсивно достать URL из строки, списка или image_links.normal/small."""
    if isinstance(value, str):
        return value or None
    if isinstance(value, (list, tuple)):
        for item in value:
            found = _first_image_url(item)
            if found:
                return found
    if isinstance(value, dict):
        for key in ("normal", "small", "link", "src", "url"):
            if key in value:
                found = _first_image_url(value[key])
                if found:
                    return found
    return None
