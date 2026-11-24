"""Экспорт датасета: JSONL + manifest + checksums (DESIGN_DATA_ML § 5)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pricescope_core.hashing import canonical_json


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """Записать строки в JSONL."""
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(canonical_json(row) + "\n")


def _sha256(path: Path) -> str:
    """SHA-256 файла."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_export(
    pairs: list[dict[str, Any]],
    out_dir: Path,
    *,
    name: str = "product-matching",
    version: str = "1",
) -> dict[str, Any]:
    """Собрать train/val/test split по времени и записать манифест."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)

    # Простая time-based симуляция: каждая пара несёт observed_at (если есть).
    ordered = sorted(pairs, key=lambda row: row.get("observed_at", ""))
    n_val = max(1, int(len(ordered) * 0.15))
    n_test = max(1, int(len(ordered) * 0.15))
    splits = {
        "train": ordered[: max(0, len(ordered) - n_val - n_test)],
        "val": ordered[max(0, len(ordered) - n_val - n_test) : len(ordered) - n_test],
        "test": ordered[len(ordered) - n_test :],
    }

    checksums: dict[str, str] = {}
    for split, rows in splits.items():
        path = out_dir / f"{split}.jsonl"
        _write_jsonl(path, rows)
        checksums[path.name] = _sha256(path)

    manifest = {
        "dataset": name,
        "version": version,
        "schema_version": 1,
        "created_at": now.isoformat(),
        "split_policy": "time-based",
        "rows": {split: len(rows) for split, rows in splits.items()},
        "source_count": len(pairs),
        "sha256": checksums,
        "parsers": {"lenta": "0.1.0", "pyaterochka": "0.1.0"},
        "models": {"lexical": "builtin-v1", "text": "not-configured", "image": "not-configured"},
    }
    (out_dir / "manifest.json").write_text(
        canonical_json(manifest) + "\n", encoding="utf-8"
    )
    (out_dir / "checksums.sha256").write_text(
        "\n".join(f"{digest}  {filename}" for filename, digest in checksums.items()) + "\n",
        encoding="utf-8",
    )
    return manifest
