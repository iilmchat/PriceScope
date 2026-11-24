"""Ручной импорт CSV — легальная альтернатива при блокировке сайта."""

from __future__ import annotations

import csv
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

from pricescope_core import ProductObservation

from pricescope_parsers.base import ParseContext, ParserCapabilities

_REQUIRED = {"external_id", "name", "price_minor"}


def parse_csv_file(path: Path, store_code: str = "manual") -> list[ProductObservation]:
    """Прочитать CSV с колонками `external_id,name,price_minor[,...]`."""
    now = datetime.now(UTC)
    rows: list[ProductObservation] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = _REQUIRED - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"В CSV нет обязательных колонок: {sorted(missing)}")
        for row in reader:
            observation = ProductObservation(
                store_code=store_code,
                external_id=row["external_id"],
                name=row["name"],
                category_path=row.get("category_path"),
                price_minor=int(float(row["price_minor"])),
                old_price_minor=(
                    int(float(row["old_price_minor"])) if row.get("old_price_minor") else None
                ),
                package=row.get("package"),
                observed_at=now,
                raw_ref=f"manual:{path.name}",
                parser_version="0.1.0",
            )
            rows.append(observation.with_hash())
    return rows


class ManualCsvParser:
    """Адаптер ручного импорта (путь CSV берётся из `ctx.categories[0]`)."""

    name = "manual"
    version = "0.1.0"

    def capabilities(self) -> ParserCapabilities:
        """Браузер и сеть не нужны."""
        return ParserCapabilities(requires_browser=False, requires_location=False)

    async def health_check(self) -> bool:
        """Всегда доступен."""
        return True

    def parse(self, ctx: ParseContext) -> AsyncIterator[ProductObservation]:
        """Отдать строки CSV потоком."""
        return self._parse_impl(ctx)

    async def _parse_impl(self, ctx: ParseContext) -> AsyncIterator[ProductObservation]:
        if not ctx.categories:
            raise ValueError("Для manual-парсера укажите путь к CSV в --category")
        for observation in parse_csv_file(Path(ctx.categories[0])):
            yield observation
