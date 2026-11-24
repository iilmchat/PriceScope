"""Тесты импорта legacy Excel (PL-015)."""

from __future__ import annotations

from pathlib import Path

import pricescope_api.db.session as session_module
from openpyxl import Workbook
from pricescope_api.db.models import Observation, RawSnapshot
from pricescope_api.legacy_import import import_legacy_excel
from sqlalchemy import select

HEADER = (
    "id", "категория_id", "название", "цена, ₽", "обычная цена, ₽",
    "скидка, ₽", "скидка, %", "промо", "фасовка", "вес брутто, г",
    "вес нетто, г", "фото", "категория",
)


def make_excel(path: Path) -> Path:
    """Мини-копия lenta_prices.xlsx."""
    wb = Workbook()
    ws = wb.active
    ws.append(HEADER)
    ws.append((
        1, 3509, "Пена DEONICA 240мл", 196.99, 332.99, 136, 41, "да",
        "240мл", 294, 240, "https://cdn.test/1.png", "Красота/Бритье",
    ))
    ws.append((
        2, 3509, "Спрей AKC 100мл", 272.99, 445.99, 173, 39, "да",
        "100мл", 141, 100, None, "Красота/Бритье",
    ))
    ws.append((3, 3509, "Без цены", None, None, None, None, "", None, None, None, None, None))
    wb.save(path)
    return path


async def test_import_excel_and_photos(client, tmp_path):
    """Строки Excel попадают в БД, локальное фото подключается без копирования."""
    excel = make_excel(tmp_path / "lenta_prices.xlsx")
    photos = tmp_path / "photos"
    photos.mkdir()
    (photos / "1.png").write_bytes(b"png")

    maker = session_module.get_sessionmaker()
    async with maker() as session:
        result = await import_legacy_excel(
            session, excel_path=excel, photos_dir=photos
        )

    assert result["new"] == 2
    assert result["skipped"] == 1  # строка без цены
    assert len(result["raw_ref"]) == 64

    async with maker() as session:
        rows = (
            (await session.execute(select(Observation).order_by(Observation.external_id)))
            .scalars()
            .all()
        )
        assert len(rows) == 2
        assert rows[0].price_minor == 19699
        assert rows[0].old_price_minor == 33299
        assert rows[0].category_path == "Красота/Бритье"
        assert rows[0].image_urls_json[0] == "/legacy-photos/1.png"
        assert rows[1].image_urls_json == []
        snapshots = (await session.execute(select(RawSnapshot))).scalars().all()
        assert len(snapshots) == 1


async def test_import_is_idempotent(client, tmp_path):
    """Повторный импорт того же файла не создаёт дубликаты."""
    excel = make_excel(tmp_path / "lenta_prices.xlsx")
    photos = tmp_path / "photos"
    photos.mkdir()
    maker = session_module.get_sessionmaker()

    async with maker() as session:
        first = await import_legacy_excel(session, excel_path=excel, photos_dir=photos)
        second = await import_legacy_excel(session, excel_path=excel, photos_dir=photos)

    assert first["new"] == 2
    assert second["new"] == 0
    assert second["unchanged"] == 2
