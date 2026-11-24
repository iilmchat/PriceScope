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
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Собрать train/val/test split по времени и записать манифест."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)

    # Time-based split: обучаемся на старых observation, проверяем на новых.
    ordered = sorted(pairs, key=lambda row: str(row.get("observed_at", "")))
    if len(ordered) < 3:
        splits = {"train": ordered, "val": [], "test": []}
    else:
        n_val = max(1, int(len(ordered) * 0.15))
        n_test = max(1, int(len(ordered) * 0.15))
        train_end = len(ordered) - n_val - n_test
        splits = {
            "train": ordered[:train_end],
            "val": ordered[train_end : len(ordered) - n_test],
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
        "split_boundaries": {
            "val_from": splits["val"][0].get("observed_at") if splits["val"] else None,
            "test_from": splits["test"][0].get("observed_at") if splits["test"] else None,
        },
        "rows": {split: len(rows) for split, rows in splits.items()},
        "source_count": len(pairs),
        "sha256": checksums,
        "parsers": {"lenta": "0.1.0", "pyaterochka": "0.1.0"},
        "models": {"lexical": "builtin-v1", "text": "not-configured", "image": "not-configured"},
        **(extra or {}),
    }
    (out_dir / "manifest.json").write_text(
        canonical_json(manifest) + "\n", encoding="utf-8"
    )
    (out_dir / "checksums.sha256").write_text(
        "\n".join(f"{digest}  {filename}" for filename, digest in checksums.items()) + "\n",
        encoding="utf-8",
    )
    return manifest
