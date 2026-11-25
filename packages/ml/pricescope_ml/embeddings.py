"""Текстовые эмбеддинги для сопоставления товаров.

По умолчанию используется дешёвый детерминированный провайдер на basic-триграммах
символов (`trigram-v1`) — он не требует моделей и работает офлайн. Если установлен
`sentence-transformers` и модель доступна локально, можно включить нейронный
провайдер через `EMBEDDING_PROVIDER=sentence-transformers`.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
from typing import Any, Protocol, runtime_checkable

from pricescope_core.normalization import normalize_name

DEFAULT_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
TRIGRAM_VERSION = "trigram-v1"
ST_VERSION = f"sentence-transformers:{DEFAULT_MODEL}"


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Порт: название товара → нормализованный вектор."""

    @property
    def version(self) -> str: ...
    def embed(self, text: str) -> list[float]: ...


class TrigramEmbedding:
    """Хэш-эмбеддинг по символам и триграммам (без внешних зависимостей)."""

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    @property
    def version(self) -> str:
        """Версия модели для ProductMatch.model_version."""
        return TRIGRAM_VERSION

    def embed(self, text: str) -> list[float]:
        """Вектор из токенов и триграмм нормализованного названия."""
        vector = [0.0] * self.dim
        normalized = normalize_name(text)
        features = normalized.split() + [
            normalized[i : i + 3] for i in range(max(0, len(normalized) - 2))
        ]
        for feature in features:
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        return _normalize(vector)


class SentenceTransformerEmbedding:
    """Нейронный провайдер; импорт и загрузка модели — ленивые."""

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        self.model_name = model_name
        self._model: Any | None = None

    @property
    def version(self) -> str:
        """Версия модели."""
        return f"sentence-transformers:{self.model_name}"

    def embed(self, text: str) -> list[float]:
        """Вектор через локальную модель (должна быть доступна офлайн)."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError(
                    "Установите extras: pip install -e '.[ml]' "
                    "и скачайте модель для офлайн-использования"
                ) from exc
            self._model = SentenceTransformer(self.model_name)
        vector = self._model.encode(text, normalize_embeddings=True)
        return [float(value) for value in vector]


def _normalize(vector: list[float]) -> list[float]:
    """L2-нормализация вектора."""
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else vector


def cosine(left: list[float], right: list[float]) -> float:
    """Косинусное сходство нормализованных векторов."""
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True))


def get_provider(kind: str | None = None) -> EmbeddingProvider:
    """Фабрика провайдеров с fallback на trigram."""
    chosen = (kind or os.getenv("EMBEDDING_PROVIDER") or "trigram").lower()
    if chosen in ("sentence-transformers", "st"):
        return SentenceTransformerEmbedding()
    return TrigramEmbedding()


def clean_text(text: str) -> str:
    """Очистка текста перед эмбеддингом."""
    return re.sub(r"\s+", " ", normalize_name(text)).strip()
