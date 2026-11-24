"""Доменное ядро PriceScope: контракты, деньги, нормализация, хэширование."""

from __future__ import annotations

from pricescope_core.enums import (
    MatchMethod,
    MatchStatus,
    ParseStatus,
    StoreCode,
)
from pricescope_core.errors import (
    CaptchaDetectedError,
    DomainError,
    ParserError,
    StoreUnavailableError,
    UnknownStoreError,
)
from pricescope_core.hashing import canonical_hash, canonical_json, sha256_bytes, sha256_text
from pricescope_core.money import format_rub, minor_to_major, to_minor
from pricescope_core.normalization import (
    extract_measure,
    normalize_name,
    tokenize,
)
from pricescope_core.observation import SCHEMA_VERSION, ProductObservation

__all__ = [
    "SCHEMA_VERSION",
    "CaptchaDetectedError",
    "DomainError",
    "MatchMethod",
    "MatchStatus",
    "ParserError",
    "ParseStatus",
    "ProductObservation",
    "StoreCode",
    "StoreUnavailableError",
    "UnknownStoreError",
    "canonical_hash",
    "canonical_json",
    "extract_measure",
    "format_rub",
    "minor_to_major",
    "normalize_name",
    "sha256_bytes",
    "sha256_text",
    "to_minor",
    "tokenize",
]
