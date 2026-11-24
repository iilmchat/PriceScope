"""Импорт наследуемых Excel-файлов Ленты в БД (PL-015).

Старые скрипты писали `.xlsx` и скачивали фото в `photos/{id}.png`.
Этот модуль переносит строки в `Observation`, сохраняя lineage через `RawSnapshot`,
но **не копирует фото** (их ~23 тыс. / ~10 ГБ) — viewer отдаёт их напрямую
через смонтированный каталог `/legacy-photos`.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from pricescope_core import ProductObservation
from sqlalchemy.ext.asyncio import AsyncSession

from pricescope_api import repositories as repo
from pricescope_api.logging import current_trace_id, get_logger

logger = get_logger(__name__)

HEADERS = {
    "id": "id",
    "категория_id": "category_id",
    "название": "name",
    "цена, ₽": "price_rub",
    "обычная цена, ₽": "old_price_rub",
    "скидка, ₽": "discount_rub",
    "скидка, %": "discount_pct",
    "промо": "promo",
    "фасовка": "package",
    "вес брутто, г": "gross",
    "вес нетто, г": "net",
    "фото": "image",
    "категория": "category",
    "цена": "price_minor",
    "старая_цена": "old_price_minor",
    "вес/объём": "measures",
    "бренд": "brand",
}


def _file_sha256(path: Path) -> str:
    """SHA-256 файла без загрузки целиком в память."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _minor(value: Any, *, rubles: bool) -> int | None:
    """Рубли → копейки; уже копейки — без конвертации."""
    if value is None or isinstance(value, bool) or value == "":
        return None
    try:
        number = float(str(value).replace(",", ".").replace(" ", ""))
    except ValueError:
        return None
    return int(round(number * 100)) if rubles else int(round(number))


def _row_to_observation(
    row: dict[str, Any], *, location_id: str, now: datetime, raw_ref: str,
    photos_dir: Path,
) -> ProductObservation | None:
    """Строка Excel → контракт v1."""
    external_id = row.get("id")
    name = row.get("name")
    price = _minor(row.get("price_rub"), rubles=True)
    if price is None:
        price = _minor(row.get("price_minor"), rubles=False)
    if external_id is None or not name or price is None:
        return None

    external_id = str(external_id)
    local_photo = photos_dir / f"{external_id}.png"
    images: list[str] = []
    if local_photo.is_file():
        images.append(f"/legacy-photos/{external_id}.png")
    remote = row.get("image")
    if remote and str(remote) not in images:
        images.append(str(remote))

    net = row.get("net")
    gross = row.get("gross")
    return ProductObservation(
        store_code="lenta",
        external_id=external_id,
        location_id=location_id,
        name=str(name),
        category_path=row.get("category"),
        price_minor=price,
        old_price_minor=(
            _minor(row.get("old_price_rub"), rubles=True)
            or _minor(row.get("old_price_minor"), rubles=False)
        ),
        package=row.get("package"),
        net_weight_g=int(net) if net not in (None, "") else None,
        gross_weight_g=int(gross) if gross not in (None, "") else None,
        image_urls=images,
        available=True,
        observed_at=now,
        raw_ref=raw_ref,
        parser_version="legacy-excel-v1",
    ).with_hash()


async def import_legacy_excel(
    session: AsyncSession,
    *,
    excel_path: Path,
    photos_dir: Path,
    store_code: str = "lenta",
) -> dict[str, Any]:
    """Импортировать legacy Excel в observations."""
    excel_path = Path(excel_path)
    photos_dir = Path(photos_dir)
    if not excel_path.is_file():
        raise FileNotFoundError(f"Excel-файл не найден: {excel_path}")

    sha = _file_sha256(excel_path)
    fetched_at = datetime.fromtimestamp(excel_path.stat().st_mtime, UTC)
    await repo.create_raw_snapshot(
        session,
        sha256=sha,
        store_code=store_code,
        uri=f"legacy://{excel_path.name}",
        path=str(excel_path),
        parser_version="legacy-excel-v1",
        fetched_at=fetched_at,
    )
    await session.commit()

    workbook = load_workbook(excel_path, read_only=True, data_only=True)
    sheet = workbook.active
    rows = sheet.iter_rows(values_only=True)
    try:
        raw_header = next(rows)
    except StopIteration:
        workbook.close()
        return {"new": 0, "updated": 0, "unchanged": 0, "skipped": 0, "raw_ref": sha}

    header = [HEADERS.get(str(cell).strip() if cell is not None else "", "") for cell in raw_header]
    location_id = "legacy-excel"
    counts = {"new": 0, "updated": 0, "unchanged": 0, "skipped": 0}

    for values in rows:
        row = {key: value for key, value in zip(header, values, strict=False) if key}
        observation = _row_to_observation(
            row, location_id=location_id, now=fetched_at, raw_ref=sha, photos_dir=photos_dir
        )
        if observation is None:
            counts["skipped"] += 1
            continue
        try:
            async with session.begin_nested():
                result, _ = await repo.upsert_observation(session, observation)
            counts[result] += 1
        except Exception as exc:  # одна строка не роняет весь файл
            counts["skipped"] += 1
            logger.warning("legacy_row_skipped", error=str(exc), trace_id=current_trace_id())
        if sum(counts.values()) % 500 == 0:
            await session.commit()
    workbook.close()
    await session.commit()
    await repo.audit(
        session,
        "legacy.import",
        current_trace_id(),
        excel=str(excel_path),
        counts=counts,
    )
    await session.commit()
    return {**counts, "raw_ref": sha}
