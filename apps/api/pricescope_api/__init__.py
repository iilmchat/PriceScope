"""FastAPI-приложение PriceScope."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("pricescope")
except PackageNotFoundError:  # исходная копия без установки
    __version__ = "0.1.0"
