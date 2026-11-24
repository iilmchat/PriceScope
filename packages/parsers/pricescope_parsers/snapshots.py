"""Хранилище исходных ответов (raw snapshots) для lineage."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from pricescope_core.hashing import sha256_bytes


class RawSnapshotStore:
    """Пишет исходные байты в `data/raw/{store}/{date}/{sha}.{ext}`.

    Файл сохраняется один раз (по sha256); повторная запись — no-op.
    """

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir)

    async def save_async(
        self,
        store_code: str,
        payload: bytes,
        uri: str,
        content_type: str = "application/json",
    ) -> str:
        """Асинхронно сохранить снапшот и вернуть его sha256."""
        return await asyncio.to_thread(self.save, store_code, payload, uri, content_type)

    def save(
        self,
        store_code: str,
        payload: bytes,
        uri: str,
        content_type: str = "application/json",
    ) -> str:
        """Сохранить снапшот (синхронная версия для CLI/тестов)."""
        sha = sha256_bytes(payload)
        day = datetime.now(UTC).date().isoformat()
        ext = "html" if "html" in content_type else "json"
        directory = self.base_dir / store_code / day
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{sha}.{ext}"
        if not path.exists():
            path.write_bytes(payload)
            (directory / f"{sha}.{ext}.uri.txt").write_text(uri, encoding="utf-8")
        return sha
