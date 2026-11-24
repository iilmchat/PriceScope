"""Слой доступа к данным."""

from __future__ import annotations

from pricescope_api.db.base import Base
from pricescope_api.db.session import get_session, init_db

__all__ = ["Base", "get_session", "init_db"]
