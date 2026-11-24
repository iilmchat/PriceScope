"""Юнит-тесты entity resolution (S07)."""

from __future__ import annotations

from pricescope_ml.matching import (
    AUTO_THRESHOLD,
    REVIEW_THRESHOLD,
    MatchCandidate,
    MatchResult,
    decide,
    score_candidates,
    score_pair,
)


def test_exact_name_is_auto():
    """Полное совпадение названий → score 1.0 и auto."""
    result = score_pair("Дезодорант РЕКСОНА 100мл", "Дезодорант РЕКСОНА 100мл")
    assert result.score == 1.0
    assert result.method == "exact_name"
    assert decide(result).status == "auto"


def test_lexical_same_measure_boosts_score():
    """Одинаковая фасовка повышает оценку, различная — понижает."""
    same = score_pair("Рексона спрей 100 мл", "Дезодорант Рексона 100мл")
    diff = score_pair("Рексона спрей 100 мл", "Дезодорант Рексона 50мл")
    assert same.score > diff.score


def test_review_and_new_thresholds():
    """Пороги 0.70 / 0.90 разделяют auto, review и новый товар."""
    def result(score: float) -> MatchResult:
        """Результат с заданной оценкой."""
        return MatchResult(score=score, method="lexical", same_measure=True)

    assert decide(result(0.95)).status == "auto"
    assert decide(result(0.80)).status == "review"
    assert decide(result(0.40)).status == "new"
    assert AUTO_THRESHOLD == 0.90
    assert REVIEW_THRESHOLD == 0.70


def test_score_candidates_with_package():
    """Кандидаты сравниваются с учётом фасовки."""
    left = MatchCandidate(name="Рексона 100 мл", package="100мл", store_code="lenta")
    same = MatchCandidate(name="Рексона 100мл", package="100мл", store_code="pyaterochka")
    other = MatchCandidate(name="Рексона 50мл", package="50мл", store_code="pyaterochka")
    assert score_candidates(left, same).score > score_candidates(left, other).score
