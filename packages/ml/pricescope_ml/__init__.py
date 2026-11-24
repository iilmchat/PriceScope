"""ML-подсистема PriceScope: сопоставление и экспорт датасетов."""

from __future__ import annotations

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
    "MatchResult",
    "MatchingDecision",
    "build_export",
    "decide",
    "score_candidates",
    "score_pair",
]
