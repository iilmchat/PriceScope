"""Браузерный слой Пятёрочки: порт `BrowserBackend` и Camoufox-адаптер.

Опциональные зависимости (camoufox, human_requests, pyaterochka_api) импортируются
лениво: ядро и тесты работают без них. Путь к браузеру — только из env
`CAMOUFOX_EXECUTABLE_PATH`, прокси — из `PRICESCOPE_PROXY`.
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import json
import os
from typing import Any, Protocol, runtime_checkable

from pricescope_core import ParserError

from pricescope_parsers.base import ParseContext
from pricescope_parsers.pyaterochka.captcha_policy import ensure_no_captcha

SITE_URL = "https://5ka.ru"
_COMPAT_INSTALLED = False


@runtime_checkable
class BrowserBackend(Protocol):
    """Порт источника снимка каталога 5ka.ru."""

    async def fetch_snapshot(self, ctx: ParseContext) -> dict:
        """Вернуть снимок: метаданные точки, категории и товары по категориям."""
        ...


class CamoufoxBackend:
    """Реальный адаптер на Camoufox + human_requests + pyaterochka_api."""

    def __init__(self, *, timeout_ms: int = 60_000, category_delay: float = 0.8) -> None:
        self.timeout_ms = timeout_ms
        self.category_delay = category_delay

    async def fetch_snapshot(self, ctx: ParseContext) -> dict:
        """Загрузить страницу, дерево категорий и товары по категориям."""
        mgr, api_class = self._load_dependencies()
        self._install_compat(mgr, api_class)

        async with api_class() as api:
            page = getattr(api, "page", None)
            if page is not None:
                await self._ensure_no_captcha_on_page(page)

            store_info = await api.delivery_panel_store()
            selected = store_info.get("selectedStore") or {}
            sap_code = selected.get("sapCode")
            if not sap_code:
                raise ParserError(
                    "5ka.ru не вернул selectedStore.sapCode — выберите магазин "
                    "доставки в браузере и повторите позже",
                    {"store_info": str(store_info)[:1000]},
                )
            await _save_json(ctx, store_info, f"{SITE_URL}/delivery-panel-store")

            tree_response = await api.Catalog.tree(sap_code_store_id=sap_code)
            tree = tree_response.json()
            await _save_json(ctx, tree, f"{SITE_URL}/api/catalog/tree")
            leaves = collect_leaves(tree)

            products: dict[str, list[dict]] = {}
            for index, (category_id, _path) in enumerate(leaves, start=1):
                ctx.check_cancelled()
                try:
                    response = await api.Catalog.products_list(
                        category_id=category_id,
                        sap_code_store_id=sap_code,
                        limit=200,
                    )
                    data = response.json()
                    await _save_json(ctx, data, f"{SITE_URL}/api/catalog/{category_id}")
                    products[str(category_id)] = data.get("products") or data.get("data") or []
                except Exception as exc:
                    # Одна категория не роняет весь прогон
                    ctx.check_cancelled()
                    products[str(category_id)] = []
                    if page is not None:
                        await self._ensure_no_captcha_on_page(page)
                    if index == len(leaves):
                        raise ParserError(f"Не удалось прочитать каталог 5ka.ru: {exc}") from exc
                if self.category_delay:
                    await asyncio.sleep(self.category_delay)

            return {
                "title": "Каталог 5ka.ru",
                "url": SITE_URL,
                "body_text": "",
                "location": {
                    "external_id": str(sap_code),
                    "name": selected.get("name") or selected.get("storeName"),
                    "address": selected.get("address") or selected.get("shortAddress"),
                },
                "categories": leaves,
                "products": products,
            }

    @staticmethod
    def _load_dependencies() -> tuple[Any, Any]:
        """Ленивая загрузка опционального браузерного стека."""
        executable = os.getenv("CAMOUFOX_EXECUTABLE_PATH")
        if not executable:
            raise ParserError(
                "Для парсера Пятёрочки задайте CAMOUFOX_EXECUTABLE_PATH "
                "и установите extras: pip install -e '.[parser5ka]'"
            )
        try:
            # human_requests 0.2.x ожидает typing.override (появился в Python 3.12)
            import typing

            if not hasattr(typing, "override"):
                from typing_extensions import override as _override

                typing.override = _override  # type: ignore[attr-defined]

            import pyaterochka_api.manager as mgr
            from camoufox.async_api import AsyncCamoufox
            from human_requests import HumanBrowser, HumanContext, HumanPage
            from human_requests.abstraction import Proxy
            from human_requests.network_analyzer.anomaly_sniffer import (
                HeaderAnomalySniffer,
                WaitHeader,
                WaitSource,
            )
            from pyaterochka_api import PyaterochkaAPI
        except ImportError as exc:
            raise ParserError(
                f"Браузерный стек не установлен: {exc}. "
                "Выполните pip install -e '.[parser5ka]'"
            ) from exc

        # Camoufox читает переменную окружения при старте драйвера
        os.environ.setdefault("CAMOUFOX_EXECUTABLE_PATH", executable)
        globals().update(
            {
                "_AsyncCamoufox": AsyncCamoufox,
                "_HumanBrowser": HumanBrowser,
                "_HumanContext": HumanContext,
                "_HumanPage": HumanPage,
                "_Proxy": Proxy,
                "_HeaderAnomalySniffer": HeaderAnomalySniffer,
                "_WaitHeader": WaitHeader,
                "_WaitSource": WaitSource,
            }
        )
        return mgr, PyaterochkaAPI

    @staticmethod
    def _install_compat(mgr: Any, api_class: Any) -> None:
        """Адаптация библиотеки к текущим Playwright/human-requests API."""
        global _COMPAT_INSTALLED
        if _COMPAT_INSTALLED:
            return

        async def delivery_panel_store(self: Any) -> dict:
            raw = await _get_local_storage_item(self.page, "DeliveryPanelStore")
            if raw is None:
                raise ParserError(
                    "В localStorage нет DeliveryPanelStore — выберите магазин доставки"
                )
            return json.loads(raw) if isinstance(raw, (str, bytes, bytearray)) else raw

        async def device_id(self: Any) -> str:
            value = await _get_local_storage_item(self.page, "deviceId")
            return str(value) if value is not None else ""

        async def shutdown(
            self: Any,
            exc_type: Any = None,
            exc: Any = None,
            tb: Any = None,
        ) -> None:
            runner = getattr(self, "_camoufox_runner", None)
            self._camoufox_runner = None
            if runner is not None:
                await runner.__aexit__(exc_type, exc, tb)
            elif getattr(self, "session", None) is not None:
                await self.session.close()

        async def close(self: Any) -> None:
            await shutdown(self)

        async def aexit(self: Any, *exc: Any) -> None:
            args = exc or (None, None, None)
            await shutdown(self, *args)

        async def warmup(self: Any) -> None:
            proxy = os.getenv("PRICESCOPE_PROXY")
            self._camoufox_runner = globals()["_AsyncCamoufox"](
                headless=True,
                proxy=globals()["_Proxy"](proxy).as_dict() if proxy else None,
            )
            browser = await self._camoufox_runner.__aenter__()
            self.session = globals()["_HumanBrowser"].replace(browser)
            raw_context = await self.session.new_context()
            self.ctx = globals()["_HumanContext"].replace(raw_context)
            raw_page = await self.ctx.new_page()
            self.page = globals()["_HumanPage"].replace(raw_page)

            sniffer = globals()["_HeaderAnomalySniffer"](
                extra_request_allow=["x-forwarded-for", "x-real-ip"],
                extra_response_allow=[],
                include_subresources=True,
                url_filter=lambda url: url.startswith("https://5d.5ka.ru/"),
            )
            await sniffer.start(self.ctx)
            for attempt in range(3):
                await self.page.goto(SITE_URL, wait_until="load", timeout=self.timeout_ms)
                # Site — SPA: localStorage заполняется после загрузки роута/сети
                with contextlib.suppress(Exception):
                    await self.page.wait_for_selector(
                        "next-route-announcer", state="attached", timeout=5000
                    )
                with contextlib.suppress(Exception):
                    await self.page.wait_for_load_state("networkidle", timeout=5000)
                await self._ensure_no_captcha_on_page(self.page)
                try:
                    raw_store = await _get_local_storage_item(self.page, "DeliveryPanelStore")
                except Exception:
                    raw_store = None
                if raw_store:
                    break
                if attempt == 2:
                    raise ParserError(
                        "5ka.ru не отдал DeliveryPanelStore: выберите магазин доставки "
                        "в браузере или проверьте, не появилась ли проверка"
                    )

            observed = await sniffer.complete()
            headers: dict[str, set[str]] = {}
            for entries in (observed.get("request") or {}).values():
                for name, values in entries.items():
                    headers.setdefault(name.lower(), set()).update(values)
            self.unstandard_headers = {name: list(values) for name, values in headers.items()}

        async def request(
            self: Any,
            method: str,
            url: str,
            *,
            json_body: Any = None,
            add_unstandard_headers: bool = True,
            credentials: bool = True,
        ) -> Any:
            headers = {"Accept": "application/json, text/plain, */*"}
            if add_unstandard_headers:
                for name, values in (getattr(self, "unstandard_headers", None) or {}).items():
                    first = (
                        next(iter(values), None)
                        if isinstance(values, (list, tuple, set))
                        else values
                    )
                    if first is not None:
                        headers[name] = str(first)
            for attempt in range(3):
                try:
                    return await self.page.fetch(
                        url=url,
                        method=method,
                        body=json_body,
                        mode="cors",
                        credentials="include" if credentials else "omit",
                        timeout_ms=self.timeout_ms,
                        referrer=self.MAIN_SITE_URL,
                        headers=headers,
                    )
                except Exception:
                    if attempt == 2:
                        raise
                    await asyncio.sleep(2 ** (attempt + 1))

        api_class.delivery_panel_store = delivery_panel_store
        api_class.device_id = device_id
        api_class.close = close
        api_class.__aexit__ = aexit
        api_class._warmup = warmup
        api_class._request = request
        async def check_captcha(self: Any, page: Any) -> None:
            """Метод-обёртка для вызова через экземпляр PyaterochkaAPI."""
            await _check_page_captcha(page)

        api_class._ensure_no_captcha_on_page = check_captcha
        _COMPAT_INSTALLED = True

    async def _ensure_no_captcha_on_page(self, page: Any) -> None:
        """Проверить видимый текст страницы; CAPTCHA → останов без обхода."""
        await _check_page_captcha(page)


async def _check_page_captcha(page: Any) -> None:
    """Прочитать видимый текст страницы и остановиться при CAPTCHA."""
    title = url = body = ""
    with contextlib.suppress(Exception):
        title = await page.title()
    with contextlib.suppress(Exception):
        url = str(page.url or "")
    with contextlib.suppress(Exception):
        body = await page.locator("body").inner_text(timeout=2500)
    ensure_no_captcha(title, url, body)


async def _save_json(ctx: ParseContext, data: dict, uri: str) -> None:
    """Сохранить JSON-ответ и запомнить его sha для lineage."""
    payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
    ctx.last_raw_sha = await ctx.save_raw("pyaterochka", payload, uri)


def collect_leaves(categories: list[dict], prefix: str = "") -> list[tuple[str, str]]:
    """Конечные категории дерева 5ka: `[(SAP-код, путь)]`.

    Идентификаторы категорий 5ka — строки вида `251C17046`, не целые числа.
    """
    leaves: list[tuple[str, str]] = []
    for category in categories:
        path = f"{prefix}/{category.get('name')}" if prefix else category.get("name", "")
        children = category.get("categories") or []
        if children:
            leaves.extend(collect_leaves(children, path))
        else:
            leaves.append((str(category["id"]), path))
    return leaves


async def _get_local_storage_item(page: Any, key: str) -> Any:
    """Совместимость со старым/new API Playwright localStorage."""
    storage = page.local_storage
    if callable(storage):
        storage = storage()
        if inspect.isawaitable(storage):
            storage = await storage
    getter = getattr(storage, "get_item", None) or getattr(storage, "get", None)
    if getter is None:
        raise ParserError(f"Неизвестный API localStorage: {type(storage).__name__}")
    value = getter(key)
    return await value if inspect.isawaitable(value) else value
