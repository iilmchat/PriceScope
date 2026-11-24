"""Юнит-тесты retry / rate limit / circuit breaker (без реального ожидания)."""

from __future__ import annotations

import asyncio

import httpx
import pytest
from pricescope_parsers.resilience import (
    CircuitBreaker,
    RetryPolicy,
    TokenBucketRateLimiter,
)


class FakeClock:
    """Управляемое время для тестов."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        """Текущее время."""
        return self.now

    def advance(self, seconds: float) -> None:
        """Сдвинуть время вперёд."""
        self.now += seconds


def status_error(code: int) -> httpx.HTTPStatusError:
    """Искусственная HTTP-ошибка с кодом."""
    request = httpx.Request("GET", "https://example.test")
    return httpx.HTTPStatusError(
        f"HTTP {code}", request=request, response=httpx.Response(code, request=request)
    )


async def test_retry_transient_then_success():
    """503 → повтор → успех; задержки 1 и 2 с подставлены через fake sleep."""
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    policy = RetryPolicy(attempts=3, base_delay=1.0, sleep=fake_sleep, jitter=lambda: 1.0)
    attempts = 0

    async def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise status_error(503)
        return "ok"

    assert await policy.run(operation) == "ok"
    assert attempts == 3
    assert sleeps == [1.0, 2.0]


async def test_retry_does_not_repeat_client_error():
    """400 — не transient: одна попытка, ошибка пробрасывается."""
    attempts = 0

    async def operation() -> str:
        nonlocal attempts
        attempts += 1
        raise status_error(400)

    with pytest.raises(httpx.HTTPStatusError):
        await RetryPolicy(attempts=3).run(operation)
    assert attempts == 1


async def test_retry_does_not_swallow_cancellation():
    """Внешняя отмена пробрасывается немедленно (RULES § 4.5)."""
    attempts = 0

    async def operation() -> str:
        nonlocal attempts
        attempts += 1
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await RetryPolicy(attempts=3).run(operation)
    assert attempts == 1


async def test_circuit_breaker_opens_and_recovers():
    """3 ошибки → open; после cooldown → полуоткрытый probing."""
    clock = FakeClock()
    breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=10, clock=clock)

    for _ in range(3):
        breaker.record_failure()
    assert breaker.is_open is True

    clock.advance(5)
    assert breaker.is_open is True
    clock.advance(6)
    assert breaker.is_open is False  # погас после cooldown

    breaker.record_failure()
    breaker.record_success()
    assert breaker.is_open is False


async def test_rate_limiter_waits_when_tokens_exhausted():
    """Третий запрос при rate=2/мин ждёт 30 с (fake sleep)."""
    clock = FakeClock()
    waits: list[float] = []

    async def fake_sleep(delay: float) -> None:
        waits.append(delay)
        clock.advance(delay)

    limiter = TokenBucketRateLimiter(2, clock=clock, sleep=fake_sleep)
    await limiter.acquire()
    await limiter.acquire()
    await limiter.acquire()

    assert waits and round(waits[0], 2) == 30.0
