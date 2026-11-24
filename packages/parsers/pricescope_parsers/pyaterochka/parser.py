"""Адаптер Пятёрочки (S06): браузерный сбор с жёсткой captcha-политикой.

В v0.1 адаптер работает вручную. Браузерный стек (Camoufox/human_requests)
опционален и импортируется лениво; для тестов используется фикстура
`ctx.browser_snapshot` со списком товаров.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

from pricescope_core import ParserError, ProductObservation

from pricescope_parsers.base import ParseContext, ParserCapabilities
from pricescope_parsers.pyaterochka.captcha_policy import ensure_no_captcha


class PyaterochkaParser:
    """Адаптер 5ka.ru. CAPTCHA → останов (ADR-006)."""

    name = "pyaterochka"
    version = "0.1.0"

    def capabilities(self) -> ParserCapabilities:
        """Нужен браузер и выбранная точка доставки."""
        return ParserCapabilities(
            requires_browser=True,
            requires_location=True,
            supports_images=True,
            max_requests_per_minute=30,
        )

    async def health_check(self) -> bool:
        """Проверка доступности сайта (базовая)."""
        import httpx

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get("https://5ka.ru/")
            ensure_no_captcha(str(response.url), "", response.text[:5000])
            return response.status_code < 500

    def parse(self, ctx: ParseContext) -> AsyncIterator[ProductObservation]:
        """Сбор товаров; при отсутствии браузерного стека — явная ошибка S06."""
        return self._parse_impl(ctx)

    async def _parse_impl(self, ctx: ParseContext) -> AsyncIterator[ProductObservation]:
        snapshot = getattr(ctx, "browser_snapshot", None)
        if snapshot is None:
            raise ParserError(
                "Браузерный адаптер Пятёрочки будет реализован в спринте S06. "
                "Сейчас используйте Pricescope CLI parse --store manual --file <csv> "
                "или fixture browser_snapshot в тестах."
            )
        ensure_no_captcha(
            snapshot.get("title", ""),
            snapshot.get("url", ""),
            snapshot.get("body_text", ""),
        )
        now = datetime.now(UTC)
        for item in snapshot.get("items", []):
            ctx.check_cancelled()
            prices = item.get("prices") or {}
            price = prices.get("cost") or prices.get("price") or item.get("price_minor") or 0
            observation = ProductObservation(
                store_code="pyaterochka",
                external_id=str(item["id"]),
                location_id=item.get("location_id"),
                name=item.get("name") or "",
                category_path=item.get("category_path"),
                price_minor=int(price),
                old_price_minor=prices.get("old_price_minor"),
                package=item.get("package"),
                net_weight_g=item.get("net_weight_g"),
                image_urls=item.get("image_urls") or [],
                observed_at=now,
                raw_ref="pending",
                parser_version=ctx.parser_version,
            )
            yield observation.with_hash()
