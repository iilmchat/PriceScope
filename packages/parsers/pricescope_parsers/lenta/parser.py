"""Адаптер Ленты: hub → категории → товары → нормализованные observation."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx
from pricescope_core import ProductObservation, StoreUnavailableError

from pricescope_parsers.base import ParseContext, ParserCapabilities
from pricescope_parsers.lenta.client import BASE_URL, LentaClient, LentaConfig


def build_leaf_list(categories: list[dict]) -> list[tuple[int, str]]:
    """Построить список конечных категорий `[(id, путь)]` локально."""
    by_parent: dict[int | None, list[dict]] = {}
    for category in categories:
        by_parent.setdefault(category.get("parentId"), []).append(category)

    leaves: list[tuple[int, str]] = []

    def walk(parent_id: int | None, prefix: str) -> None:
        for category in by_parent.get(parent_id, []):
            path = f"{prefix}/{category['name']}" if prefix else category["name"]
            children = by_parent.get(category["id"])
            if children:
                walk(category["id"], path)
            else:
                leaves.append((category["id"], path))

    walk(0, "")
    if not leaves:
        for category in categories:
            if not by_parent.get(category["id"]):
                leaves.append((category["id"], category["name"]))
    return leaves


class LentaParser:
    """Адаптер Integration API Ленты.

    Конфигурация injecting через конструктор — тесты передают `LentaConfig`
    с маленьким `page_limit` и нулевой задержкой.
    """

    name = "lenta"
    version = "0.1.0"

    def __init__(self, config: LentaConfig | None = None) -> None:
        self._config = config

    def capabilities(self) -> ParserCapabilities:
        """Лента не требует браузера, но требует координат точки."""
        return ParserCapabilities(
            requires_browser=False,
            requires_location=True,
            supports_images=True,
            max_requests_per_minute=120,
        )

    async def health_check(self) -> bool:
        """Проверка доступности API Ленты."""
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{BASE_URL}/v1/stores/nearest/hub")
            return response.status_code < 500

    def parse(self, ctx: ParseContext) -> AsyncIterator[ProductObservation]:
        """Потоковый сбор товаров выбранной точки."""
        return self._parse_impl(ctx)

    async def _parse_impl(self, ctx: ParseContext) -> AsyncIterator[ProductObservation]:
        client = LentaClient(ctx, self._config or LentaConfig.from_env())
        try:
            hub = await client.nearest_hub()
            hubs = hub.get("hubs") or []
            if not hubs:
                raise StoreUnavailableError("Лента не вернула ближайший магазин")
            location_id = str(hubs[0]["id"])
            ctx.location_info = {
                "external_id": location_id,
                "name": hubs[0].get("name"),
                "address": hubs[0].get("address"),
            }
            now = datetime.now(UTC)

            leaves = build_leaf_list(await client.categories(location_id))
            if ctx.categories:
                wanted = set(ctx.categories)
                leaves = [(cid, path) for cid, path in leaves if path in wanted]

            seen: set[int] = set()
            for category_id, path in leaves:
                offset = 0
                while True:
                    ctx.check_cancelled()
                    items = await client.items(location_id, category_id, offset)
                    if not items:
                        break

                    limit_reached = False
                    for item in items:
                        raw_id = item.get("id")
                        if raw_id is None:
                            continue
                        item_id = int(raw_id)
                        if item_id in seen:
                            continue
                        seen.add(item_id)
                        observation = self._to_observation(
                            item, location_id, path, now, ctx, client.last_items_sha
                        )
                        if ctx.fetch_details and not observation.image_urls:
                            detail = await self._try_detail(client, location_id, item_id)
                            image = _first_image(detail)
                            if image:
                                observation = observation.model_copy(
                                    update={"image_urls": [image]}
                                )
                        yield observation.with_hash()
                        if ctx.limit is not None and len(seen) >= ctx.limit:
                            limit_reached = True
                            break

                    offset += client.config.page_limit
                    if limit_reached or len(items) < client.config.page_limit:
                        break
                    if client.config.page_delay:
                        await asyncio.sleep(client.config.page_delay)
                if ctx.limit is not None and len(seen) >= ctx.limit:
                    break
        finally:
            await client.aclose()

    @staticmethod
    async def _try_detail(
        client: LentaClient, location_id: str, item_id: int
    ) -> dict:
        """Детальная карточка; ошибка одной карточки не роняет прогон."""
        try:
            return await client.item_detail(location_id, item_id)
        except Exception:
            return {}

    @staticmethod
    def _to_observation(
        item: dict,
        location_id: str,
        category_path: str,
        now: datetime,
        ctx: ParseContext,
        raw_sha: str,
    ) -> ProductObservation:
        """Маппинг JSON Ленты в контракт v1."""
        prices = item.get("prices") or {}
        weight = item.get("weight") or {}
        images = item.get("images") or []
        regular = prices.get("costRegular") or prices.get("priceRegular")
        image = _first_image({"images": images})
        return ProductObservation(
            store_code="lenta",
            external_id=str(item["id"]),
            location_id=location_id,
            name=item.get("name") or "",
            category_path=category_path,
            price_minor=int(prices.get("cost") or prices.get("price") or 0),
            old_price_minor=int(regular) if regular else None,
            package=weight.get("package"),
            net_weight_g=weight.get("net"),
            gross_weight_g=weight.get("gross"),
            image_urls=[image] if image else [],
            observed_at=now,
            raw_ref=raw_sha or "pending",
            parser_version=ctx.parser_version,
        )


def _first_image(detail: dict) -> str | None:
    """Выбрать лучшее фото из карточки товара."""
    images = detail.get("images") or []
    if not images:
        return None
    first = images[0]
    for key in ("pathLarge", "pathOriginal", "pathMedium", "pathPreview", "pathIcon"):
        url = first.get(key)
        if url:
            return str(url)
    return None
