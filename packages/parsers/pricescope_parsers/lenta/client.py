"""HTTP-клиент Integration API Ленты."""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx
from pricescope_core import StoreUnavailableError

from pricescope_parsers.base import ParseContext
from pricescope_parsers.resilience import CircuitBreaker, RetryPolicy, TokenBucketRateLimiter

BASE_URL = "https://integration.api.lenta.com"


@dataclass(frozen=True)
class LentaConfig:
    """Конфигурация витрины — только из env/CLI, без хардкода."""

    brand: str = "lo"
    channel: str = "lo"
    page_limit: int = 50
    page_delay: float = 0.3  # задержка между страницами (0 в тестах)
    request_timeout: float = 20.0

    @classmethod
    def from_env(cls) -> LentaConfig:
        """Считать конфигурацию из переменных окружения."""
        return cls(
            brand=os.getenv("PRICESCOPE_LENTA_BRAND", "lo"),
            channel=os.getenv("PRICESCOPE_LENTA_CHANNEL", "lo"),
            page_limit=int(os.getenv("PRICESCOPE_LENTA_PAGE_LIMIT", "50")),
            page_delay=float(os.getenv("PRICESCOPE_LENTA_PAGE_DELAY", "0.3")),
        )


class LentaClient:
    """Обёртка над httpx с retry/rate limit/circuit breaker и raw snapshot.

    Если `ctx.http` не задан, клиент создаёт и закрывает свой собственный
    `httpx.AsyncClient` — по одному на прогон, а не на запрос.
    """

    def __init__(self, ctx: ParseContext, config: LentaConfig | None = None) -> None:
        self.ctx = ctx
        self.config = config or LentaConfig.from_env()
        self._retry = RetryPolicy()
        self._limiter = TokenBucketRateLimiter(120)
        self._breaker = CircuitBreaker()
        self._own_client: httpx.AsyncClient | None = None
        self.last_items_sha = ""  # sha страницы каталога — raw_ref товаров

    def _params(self, store_id: str | None = None) -> dict[str, str | int]:
        params: dict[str, str | int] = {
            "channel": self.config.channel,
            "retailBrand": self.config.brand,
        }
        if store_id:
            params["stores"] = store_id
        return params

    def _http(self) -> httpx.AsyncClient:
        """Вернуть общий HTTP-клиент (внешний или созданный этим адаптером)."""
        if self.ctx.http is not None:
            return self.ctx.http
        if self._own_client is None:
            self._own_client = httpx.AsyncClient(
                timeout=self.config.request_timeout, follow_redirects=True
            )
        return self._own_client

    async def aclose(self) -> None:
        """Закрыть собственный клиент, если он создавался."""
        if self._own_client is not None:
            await self._own_client.aclose()
            self._own_client = None

    async def _get(self, path: str, params: dict) -> dict:
        """Запрос с общей политикой надёжности и сохранением raw snapshot."""
        self.ctx.check_cancelled()
        if self._breaker.is_open:
            raise StoreUnavailableError("Circuit breaker открыт для Ленты")

        async def operation() -> httpx.Response:
            await self._limiter.acquire()
            response = await self._http().get(f"{BASE_URL}{path}", params=params)
            response.raise_for_status()
            return response

        try:
            response = await self._retry.run(operation)
            self._breaker.record_success()
        except Exception:
            self._breaker.record_failure()
            raise

        payload = response.content
        self.last_sha = await self.ctx.save_raw(
            "lenta", payload, str(response.request.url), "application/json"
        )
        return response.json()

    async def nearest_hub(self) -> dict:
        """Ближайший хаб по координатам."""
        return await self._get(
            "/v1/stores/nearest/hub",
            {
                "latitude": self.ctx.lat,
                "longitude": self.ctx.lon,
                "retailBrand": self.config.brand,
            },
        )

    async def categories(self, store_id: str) -> list[dict]:
        """Все категории каталога (одним запросом)."""
        data = await self._get("/catalog/v1/categories", self._params(store_id))
        return data.get("categories") or []

    async def items(self, store_id: str, category_id: int, offset: int) -> list[dict]:
        """Страница товаров категории."""
        params = self._params(store_id)
        params.update(
            {"categoryId": category_id, "limit": self.config.page_limit, "offset": offset}
        )
        data = await self._get("/catalog/v1/items", params)
        self.last_items_sha = getattr(self, "last_sha", "")
        return data.get("items") or data.get("data") or []

    async def item_detail(self, store_id: str, item_id: int) -> dict:
        """Детальная карточка товара (фото, доп. поля)."""
        return await self._get(
            f"/catalog/v1/items/{item_id}",
            self._params(store_id),
        )
