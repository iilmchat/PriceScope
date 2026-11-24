"""Слой парсеров PriceScope: порты, адаптеры и общая надёжность."""

from __future__ import annotations

from pricescope_parsers.base import ParseContext, ParserCapabilities, StoreParser
from pricescope_parsers.registry import get_parser, list_parsers, register_parser

__all__ = [
    "ParseContext",
    "ParserCapabilities",
    "StoreParser",
    "get_parser",
    "list_parsers",
    "register_parser",
]
