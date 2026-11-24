"""Детерминированные хэши и канонический JSON (RULES § 4.4)."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any


def _default(value: Any) -> str:
    """Сериализация нестандартных типов для канонического JSON."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, set):
        return ", ".join(sorted(str(item) for item in value))
    raise TypeError(f"Неподдерживаемый тип для канонического JSON: {type(value)!r}")


def canonical_json(data: Any) -> str:
    """Возвращает детерминированный JSON: ключи отсортированы, без лишних пробелов."""
    return json.dumps(
        data,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=_default,
    )


def sha256_text(text: str) -> str:
    """SHA-256 от строки (UTF-8)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    """SHA-256 от байтов (используется для raw snapshot)."""
    return hashlib.sha256(data).hexdigest()


def canonical_hash(data: Any) -> str:
    """Хэш канонического представления — основа идемпотентности."""
    return sha256_text(canonical_json(data))
