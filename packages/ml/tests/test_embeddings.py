"""Тесты текстовых эмбеддингов и fallback-провайдера."""

from __future__ import annotations

from pricescope_ml.embeddings import (
    TrigramEmbedding,
    cosine,
    get_provider,
)


def test_trigram_embedding_is_deterministic():
    """Одинаковое название даёт одинаковый нормализованный вектор."""
    provider = TrigramEmbedding(dim=128)
    first = provider.embed("Кефир Простоквашино 2,5% 930г")
    second = provider.embed("Кефир Простоквашино 2,5% 930г")
    assert first == second
    assert abs(sum(value * value for value in first) - 1.0) < 1e-6


def test_similar_names_score_higher():
    """Похожие названия ближе, чем разные товары."""
    provider = TrigramEmbedding(dim=256)
    base = provider.embed("Кефир Простоквашино 2,5% 930г")
    similar = provider.embed("Кефир ПРОСТОКВАШИНО 2,5%, 930г")
    other = provider.embed("Шампунь ШАУМА для объёма 400мл")
    assert cosine(base, similar) > cosine(base, other)


def test_get_provider_falls_back_to_trigram(monkeypatch):
    """Неизвестный или недоступный провайдер → trigram (офлайн)."""
    monkeypatch.setenv("EMBEDDING_PROVIDER", "unknown-provider")
    provider = get_provider()
    assert provider.version == "trigram-v1"
