"""Лексический entity resolution (ядро без внешних моделей).

Пороги и решения описаны в DESIGN_DATA_ML § 4. Версия модели фиксируется в
`ProductMatch.model_version`, чтобы метрики можно было сравнить после смены алгоритма.
"""

from __future__ import annotations

from dataclasses import dataclass

from pricescope_core.normalization import extract_measure, normalize_name, tokenize

AUTO_THRESHOLD = 0.90
REVIEW_THRESHOLD = 0.70
MODEL_VERSION = "lexical-v1"


@dataclass(frozen=True)
class MatchResult:
    """Результат сопоставления двух названий."""

    score: float
    method: str
    same_measure: bool


@dataclass(frozen=True)
class MatchCandidate:
    """Кандидат для сопоставления: товар в магазине."""

    name: str
    store_code: str = ""
    external_id: str = ""
    package: str | None = None
    price_minor: int = 0
    image_url: str | None = None
    observed_at: str = ""
    product_id: int | None = None


@dataclass(frozen=True)
class MatchingDecision:
    """Решение: auto-link, review или новый канонический товар."""

    status: str
    method: str
    score: float
    model_version: str = MODEL_VERSION


def score_pair(left: str, right: str) -> MatchResult:
    """Оценить сходство двух названий в [0, 1]."""
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
    elif lvalue is not None and rvalue is not None and not same_measure:
        jaccard = max(0.0, jaccard - 0.25)
    return MatchResult(round(jaccard, 3), "lexical", same_measure)


def score_candidates(left: MatchCandidate, right: MatchCandidate) -> MatchResult:
    """Сходство двух кандидатов с учётом фасовки."""
    result = score_pair(left.name, right.name)
    lvalue, lunit = extract_measure(left.package or left.name)
    rvalue, runit = extract_measure(right.package or right.name)
    if lvalue is not None and rvalue is not None:
        if lvalue == rvalue and lunit == runit:
            result = MatchResult(
                min(1.0, result.score + 0.05), result.method, True
            )
        else:
            result = MatchResult(max(0.0, result.score - 0.2), result.method, False)
    return result


def decide(result: MatchResult) -> MatchingDecision:
    """Применить пороги: ≥0.90 auto, 0.70…0.90 review, <0.70 новый товар."""
    if result.score >= AUTO_THRESHOLD:
        status = "auto"
    elif result.score >= REVIEW_THRESHOLD:
        status = "review"
    else:
        status = "new"
    return MatchingDecision(status, result.method, result.score)
