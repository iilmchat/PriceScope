"""Реестр адаптеров магазинов (RULES § 1.15)."""

from __future__ import annotations

from pricescope_core import UnknownStoreError

from pricescope_parsers.base import StoreParser

_REGISTRY: dict[str, StoreParser] = {}


def register_parser(parser: StoreParser) -> None:
    """Зарегистрировать адаптер по его имени."""
    _REGISTRY[parser.name] = parser


def get_parser(name: str) -> StoreParser:
    """Вернуть адаптер; при первом обращении — ленивый импорт встроенных."""
    if name not in _REGISTRY:
        _load_builtin(name)
    if name not in _REGISTRY:
        raise UnknownStoreError(
            f"Неизвестный магазин: {name!r}. Доступны: {', '.join(list_parsers())}"
        )
    return _REGISTRY[name]


def list_parsers() -> list[str]:
    """Список зарегистрированных и встроенных кодов магазинов."""
    return sorted(set(_REGISTRY) | {"lenta", "pyaterochka", "manual"})


def _load_builtin(name: str) -> None:
    """Лениво загрузить встроенный адаптер, чтобы не требовать браузер всегда."""
    if name == "lenta":
        from pricescope_parsers.lenta.parser import LentaParser

        register_parser(LentaParser())
    elif name == "pyaterochka":
        from pricescope_parsers.pyaterochka.parser import PyaterochkaParser

        register_parser(PyaterochkaParser())
    elif name == "manual":
        from pricescope_parsers.manual.csv_parser import ManualCsvParser

        register_parser(ManualCsvParser())
