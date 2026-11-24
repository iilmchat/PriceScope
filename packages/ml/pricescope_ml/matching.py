"""Лексический entity resolution (ядро без внешних моделей)."""

from __future__ import annotations

from dataclasses import dataclass

from pricescope_core.normalization import extract_measure, normalize_name, tokenize


@dataclass(frozen=True)
class MatchResult:
    """Результат сопоставления двух названий."""

    score: float
    method: str
    same_measure: bool


def score_pair(left: str, right: str) -> MatchResult:
    """Оценить сходство двух названий в [0, 1].

    Пороги find в DESIGN_DATA_ML § 4: ≥0.90 auto, 0.70…0.90 review.
    """
    lnorm, rnorm = normalize_name(left), normalize_name(right)
    if lnorm == rnorm:
        return MatchResult(1.0, "exact_name", True)

    ltokens, rtokens = set(tokenize(left)), set(tokenize(right))
    if not ltokens or not rtokens:
        return MatchResult(0.0, "lexical", False)
    jaccard = len(ltokens & rtokens) / len(ltokens | rtokens)
    lvalue, lunit = extract_measure(left)
    rvalue, runit = extract_measure(right)
    same_measure = lvalue == rvalue and lunit == runit
    if same_measure and lvalue is not None:
        jaccard = min(1.0, jaccard + 0.15)
    return MatchResult(round(jaccard, 3), "lexical", same_measure)
