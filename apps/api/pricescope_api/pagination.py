"""Единая пагинация REST API (RULES § 4.25)."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Query


@dataclass(frozen=True)
class Pagination:
    """Параметры страницы: номер и размер."""

    page: int
    page_size: int

    @property
    def offset(self) -> int:
        """Смещение в SQL."""
        return (self.page - 1) * self.page_size

    def envelope(self, total: int, items: list) -> dict:
        """Обёртка с метаданными страницы."""
        total_pages = (total + self.page_size - 1) // self.page_size if total else 0
        return {
            "items": items,
            "total": total,
            "page": self.page,
            "page_size": self.page_size,
            "total_pages": total_pages,
            "has_next": self.page < total_pages,
        }


def paginate_params(
    page: int = Query(1, ge=1, description="Номер страницы (с 1)"),
    page_size: int = Query(50, ge=1, le=200, description="Размер страницы (≤ 200)"),
) -> Pagination:
    """FastAPI-зависимость для параметров пагинации."""
    return Pagination(page=page, page_size=page_size)
