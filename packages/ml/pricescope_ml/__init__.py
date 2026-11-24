"""ML-подсистема PriceScope: сопоставление и экспорт датасетов."""

from __future__ import annotations

from pricescope_ml.export import build_export
from pricescope_ml.matching import MatchResult, score_pair

__all__ = ["MatchResult", "build_export", "score_pair"]
