"""ML-подсистема PriceScope: сопоставление и экспорт датасетов."""

from __future__ import annotations

from pricescope_ml.embeddings import (
    EmbeddingProvider,
    SentenceTransformerEmbedding,
    TrigramEmbedding,
    cosine,
    get_provider,
)
from pricescope_ml.export import build_export
from pricescope_ml.matching import (
    AUTO_THRESHOLD,
    MODEL_VERSION,
    REVIEW_THRESHOLD,
    MatchCandidate,
    MatchingDecision,
    MatchResult,
    decide,
    score_candidates,
    score_pair,
)

__all__ = [
    "AUTO_THRESHOLD",
    "MODEL_VERSION",
    "REVIEW_THRESHOLD",
    "MatchCandidate",
    "EmbeddingProvider",
    "MatchResult",
    "MatchingDecision",
    "SentenceTransformerEmbedding",
    "TrigramEmbedding",
    "build_export",
    "cosine",
    "decide",
    "get_provider",
    "score_candidates",
    "score_pair",
]
