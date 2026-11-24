"""Перечисления домена."""

from __future__ import annotations

from enum import StrEnum


class StoreCode(StrEnum):
    """Коды поддерживаемых магазинов."""

    LENTA = "lenta"
    PYATEROCHKA = "pyaterochka"
    MANUAL = "manual"


class ParseStatus(StrEnum):
    """Статусы запуска парсера."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MatchStatus(StrEnum):
    """Статусы сопоставления товара."""

    AUTO = "auto"
    REVIEW = "review"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class MatchMethod(StrEnum):
    """Метод сопоставления (используется как метрика качества)."""

    BARCODE = "barcode"
    EXACT_NAME = "exact_name"
    TEXT_EMBEDDING = "text_embedding"
    IMAGE_EMBEDDING = "image_embedding"
    LEXICAL = "lexical"
    MANUAL = "manual"
