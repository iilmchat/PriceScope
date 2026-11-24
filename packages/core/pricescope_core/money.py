"""Работа с деньгами только в минорных единицах (RULES § 4.1, ADR-001)."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def to_minor(rub: int | float | Decimal) -> int:
    """Рубли → копейки (целое число, без float-ошибок при округлении)."""
    value = rub if isinstance(rub, Decimal) else Decimal(str(rub))
    return int((value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def minor_to_major(minor: int) -> Decimal:
    """Копейки → рубли (Decimal, не float)."""
    return (Decimal(minor) / 100).quantize(Decimal("0.01"))


def format_rub(minor: int) -> str:
    """Форматирование для UI: `1 234,56 ₽`."""
    major = minor_to_major(minor)
    return f"{major:,.2f} ₽".replace(",", " ").replace(".", ",")
