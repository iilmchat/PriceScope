"""Нормализация названий и извлечение мер (вес/объём) для entity resolution."""

from __future__ import annotations

import re
import unicodedata

_MEASURE_RE = re.compile(
    r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>мл| л|л|г|кг|мг|шт|уп)\b",
    re.IGNORECASE,
)
_PUNCT_RE = re.compile(r"[^\w\s]+", re.UNICODE)

_UNIT_TO_G = {"г": 1, "кг": 1000, "мг": 0.001}
_UNIT_TO_ML = {"мл": 1, "л": 1000}


def normalize_name(name: str) -> str:
    """NFKC + нижний регистр + удаление пунктуации + схлопывание пробелов."""
    text = unicodedata.normalize("NFKC", name).lower()
    text = _PUNCT_RE.sub(" ", text)
    return " ".join(text.split())


def tokenize(name: str) -> list[str]:
    """Токены названия (для-blocking и lexical scoring)."""
    return [token for token in normalize_name(name).split() if len(token) > 1]


def extract_measure(text: str) -> tuple[int | None, str | None]:
    """Возвращает `(значение, единица)` первой найденной меры.

    `100мл` → `(100, "мл")`, `1кг` → `(1, "кг")`. Для сравнения цены за кг
    используйте `_UNIT_TO_G` / `_UNIT_TO_ML` в matching-сервисе.
    """
    match = _MEASURE_RE.search(text)
    if not match:
        return None, None
    raw = match.group("value").replace(",", ".")
    value = float(raw)
    unit = match.group("unit").strip().lower()
    return (int(value) if value.is_integer() else int(round(value * 1000)), unit)


def to_grams(value: float, unit: str) -> float | None:
    """Перевод меры в граммы (для цены за кг)."""
    factor = _UNIT_TO_G.get(unit)
    return value * factor if factor is not None else None


def to_milliliters(value: float, unit: str) -> float | None:
    """Перевод меры в миллилитры (для цены за литр)."""
    factor = _UNIT_TO_ML.get(unit)
    return value * factor if factor is not None else None
